
from django.contrib.auth import authenticate, login, logout
from django.db.models import F, Min, Prefetch

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from .models import User, Etudiant, Enseignant, Cours, Inscription, Categorie, Quiz, Question, Choix, SessionVisio, Conversation, Message, Notification, SoumissionQuiz, Paiement, Livre, AchatLivre, TransactionSimulee, Chapitre, ChapitreDebloque, ChapitreVu, LogActivite, RessourceCours, Module, RessourceChapitre, PaiementPayGate
import json
import uuid
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import os
import requests


def _gemini_generer_json(prompt, model='gemini-flash-latest', timeout=60):
    """Appelle l'API REST de Gemini directement (sans la librairie
    `google.generativeai`, dépréciée et extrêmement lente à importer sur Windows).
    Retourne le texte brut de la réponse, censé être du JSON valide.
    Lève une exception en cas d'erreur HTTP ou de réponse vide."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    response = requests.post(
        url,
        params={"key": settings.GEMINI_API_KEY},
        json=body,
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


# Vues de base
def index(request):
    return render(request, 'index.html')

from django.core.paginator import Paginator

def course(request):
    cours_list = Cours.objects.select_related('categorie', 'enseignant').order_by('-date_publication', '-id')
    
    # Pagination: 6 courses per page
    paginator = Paginator(cours_list, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    inscriptions_existantes = set()

    if request.user.is_authenticated and request.user.is_etudiant:
        inscriptions_existantes = set(
            Inscription.objects.filter(etudiant=request.user.etudiant).values_list('cours_id', flat=True)
        )

    context = {
        'cours_list': page_obj,
        'inscriptions_existantes': inscriptions_existantes,
    }
    return render(request, 'course.html', context)

def contact(request):
    return render(request, 'contact.html')

def apropos(request):
    return render(request, 'a_propos.html')


def admin_login(request):
    if request.user.is_authenticated:
        return get_dashboard_redirect(request.user)
        
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, email=email, password=password)
        if user is not None:
            login(request, user)
            return get_dashboard_redirect(user)
        else:
            messages.error(request, 'Identifiants invalides')
    return render(request, 'login.html')

def admin_logout(request):
    logout(request)
    return redirect('index')

def admin_register(request):
    cours_disponibles = Cours.objects.all()
    if request.method == 'POST':
        nom = request.POST.get('nom')
        prenom = request.POST.get('prenom')
        email = request.POST.get('email')
        age = request.POST.get('age')
        role = request.POST.get('role')
        adresse = request.POST.get('adresse')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        selected_courses = request.POST.getlist('courses')

        # Validation basique
        if password1 != password2:
            messages.error(request, "Les mots de passe ne correspondent pas.")
            return render(request, 'register.html', {'cours_disponibles': cours_disponibles})

        if User.objects.filter(email=email).exists():
            messages.error(request, "Cet email existe déjà.")
            return render(request, 'register.html', {'cours_disponibles': cours_disponibles})

        try:
            if role == 'etudiant':
                user = Etudiant.objects.create_user(
                    email=email,
                    password=password1,
                    nom=nom,
                    prenom=prenom,
                    age=age,
                    adresse=adresse,
                    role = role
                )
                # Enregistrement des cours choisis
                for cours_id in selected_courses:
                    try:
                        cours_obj = Cours.objects.get(id=cours_id)
                        Inscription.objects.create(etudiant=user, cours=cours_obj, statut='validee')
                    except Cours.DoesNotExist:
                        continue
            elif role == 'enseignant':
                user = Enseignant.objects.create_user(
                    email=email,
                    password=password1,
                    nom=nom,
                    prenom=prenom,
                    age=age,
                    adresse=adresse,
                    role = role
                )
            
            login(request, user)
            messages.success(request, "Inscription réussie !")
            return get_dashboard_redirect(user)

        except Exception as e:
            messages.error(request, f"Une erreur est survenue lors de l'inscription : {e}")
            return render(request, 'register.html', {'cours_disponibles': cours_disponibles})

    return render(request, 'register.html', {'cours_disponibles': cours_disponibles})

@login_required
def dashboard(request):
    return get_dashboard_redirect(request.user)


def calculer_progression(etudiant, cours):
    """Progression réelle d'un étudiant sur un cours, en pourcentage (0-100).

    Un chapitre compte comme "acquis" si l'étudiant l'a consulté (ChapitreVu)
    OU acheté s'il est premium (ChapitreDebloque). On prend l'union des deux.
    """
    total_chapitres = cours.chapitres.count()
    if total_chapitres == 0:
        return 0
    ids_vus = set(
        ChapitreVu.objects.filter(etudiant=etudiant, chapitre__cours=cours)
        .values_list('chapitre_id', flat=True)
    )
    ids_debloques = set(
        ChapitreDebloque.objects.filter(etudiant=etudiant, chapitre__cours=cours)
        .values_list('chapitre_id', flat=True)
    )
    nb_acquis = len(ids_vus | ids_debloques)
    return min(int((nb_acquis / total_chapitres) * 100), 100)

# Dashboards (Version "Nue" sans contextes)
@login_required
def dashboard_etudiant_view(request):

    if not request.user.is_etudiant:
        messages.error(request, 'Accès refusé. Réservé aux étudiants.')
        return redirect('index')
    
    etudiant = request.user.etudiant
    
    # === CALCUL DES STATS RÉELLES ===
    # 1. Inscriptions et Progression par cours
    inscriptions = Inscription.objects.filter(etudiant=etudiant).select_related('cours').prefetch_related('cours__chapitres')
    
    # On calcule la progression pour chaque inscription
    for insc in inscriptions:
        insc.progression = calculer_progression(etudiant, insc.cours)

    nb_cours_suivis = inscriptions.filter(statut='validee').count()
    
    # 2. Moyenne Quiz
    soumissions = SoumissionQuiz.objects.filter(etudiant=etudiant, est_corrige=True)
    moyenne_quiz = 0
    if soumissions.exists():
        total_pourcentage = 0
        count_valid = 0
        for s in soumissions:
            if s.quiz.note_max > 0:
                total_pourcentage += (s.note_obtenue / s.quiz.note_max) * 100
                count_valid += 1
        if count_valid > 0:
            moyenne_quiz = round((total_pourcentage / count_valid) * 20 / 100, 1) # Note sur 20
    
    # 3. Temps d'apprentissage (Simulation basée sur les chapitres débloqués : 2h par chapitre)
    nb_chapitres = ChapitreDebloque.objects.filter(etudiant=etudiant).count()
    temps_apprentissage = f"{nb_chapitres * 2}h" if nb_chapitres > 0 else "0h"

    # === CHARTS DATA RÉELLES ===
    # 1. Activité Hebdomadaire (Chapitres débloqués par jour sur 7 jours)
    activite_labels = []
    activite_data = []
    today = timezone.now().date()
    for i in range(6, -1, -1):
        day = today - timezone.timedelta(days=i)
        activite_labels.append(day.strftime('%a')) # Nom du jour court (Lun, Mar...)
        count = ChapitreDebloque.objects.filter(etudiant=etudiant, date_deblocage__date=day).count()
        activite_data.append(count)

    # 2. Répartition du Temps (Basé sur le nombre de chapitres débloqués par cours)
    # Cela représente mieux "l'effort" ou le temps passé sur chaque matière
    reussite_labels = []
    reussite_data = []
    
    # On compte les chapitres débloqués par cours pour cet étudiant
    from django.db.models import Count
    efforts = ChapitreDebloque.objects.filter(etudiant=etudiant)\
                .values('chapitre__cours__titre')\
                .annotate(count=Count('id'))\
                .order_by('-count')[:3]
                
    for effort in efforts:
        reussite_labels.append(effort['chapitre__cours__titre'])
        reussite_data.append(effort['count'])
    
    # Si pas de chapitres débloqués, on met les cours inscrits par défaut
    if not efforts:
        for insc in inscriptions[:3]:
            reussite_labels.append(insc.cours.titre)
            reussite_data.append(1) # Valeur symbolique
    
    # Remplissage pour avoir au moins 3 segments si nécessaire
    while len(reussite_labels) < 3:
        reussite_labels.append("Autres matières")
        reussite_data.append(0)


    # Notifications non lues
    notifs_non_lues = Notification.objects.filter(
        destinataire=request.user,
        lue=False
    ).select_related('cours', 'cours__categorie').order_by('-date_creation')[:10]

    context = {
        'mes_inscriptions': inscriptions,
        'notifs_non_lues': notifs_non_lues,
        'stats': {
            'cours_suivis': nb_cours_suivis,
            'moyenne': moyenne_quiz,
            'temps': temps_apprentissage,
        },
        'activite_labels': activite_labels,
        'activite_data': activite_data,
        'reussite_labels': reussite_labels,
        'reussite_data': reussite_data,
    }

    return render(request, 'admin/index.html', context)




@login_required
def dashboard_enseignant(request):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé. Réservé aux enseignants.')
        return redirect('index')
    
    enseignant = request.user.enseignant
    
    # === CALCUL DES STATS RÉELLES ===
    # 1. Nombre de cours
    nb_cours = Cours.objects.filter(enseignant=enseignant).count()
    
    # 2. Nombre d'apprenants uniques
    total_apprenants = Etudiant.objects.filter(
        inscriptions__cours__enseignant=enseignant,
        inscriptions__statut='validee'
    ).distinct().count()
    
    # 3. Taux de réussite Quiz
    soumissions = SoumissionQuiz.objects.filter(
        quiz__cours__enseignant=enseignant,
        est_corrige=True
    )
    
    reussite_moyenne = 0
    nb_succes = 0
    nb_echec = 0
    
    if soumissions.exists():
        total_pourcentage = 0
        count_valid = 0
        for s in soumissions:
            if s.quiz.note_max > 0:
                pourcentage = (s.note_obtenue / s.quiz.note_max) * 100
                total_pourcentage += pourcentage
                count_valid += 1
                if pourcentage >= 50:
                    nb_succes += 1
                else:
                    nb_echec += 1
        
        if count_valid > 0:
            reussite_moyenne = int(total_pourcentage / count_valid)

    # === STATS POUR LES GRAPHIQUES (Données Réelles) ===
    # 1. Progression : Inscriptions sur les 7 derniers jours
    from datetime import timedelta
    today = timezone.now().date()
    activite_data = []
    activite_labels = []
    
    days_map = {'Mon': 'Lun', 'Tue': 'Mar', 'Wed': 'Mer', 'Thu': 'Jeu', 'Fri': 'Ven', 'Sat': 'Sam', 'Sun': 'Dim'}
    
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        count = Inscription.objects.filter(
            cours__enseignant=enseignant,
            date_inscription__date=date
        ).count()
        activite_data.append(count)
        activite_labels.append(days_map.get(date.strftime('%a'), date.strftime('%a')))
    
    # 2. Données pour le graphique circulaire (Réussite)
    reussite_labels = ["Succès", "Moyen", "Échec"]
    if not soumissions.exists():
        reussite_data = [0, 0, 0] 
    else:
        reussite_data = [nb_succes, 0, nb_echec]

    
    # 3. Cours les plus populaires (Top 5)
    from django.db.models import Count
    cours_populaires = Cours.objects.filter(enseignant=enseignant).annotate(
        nb_inscrits=Count('inscriptions')
    ).order_by('-nb_inscrits')[:5]
    
    if total_apprenants > 0:
        for c in cours_populaires:
            c.popularite = min(int((c.nb_inscrits / total_apprenants) * 100), 100)
    else:
        for c in cours_populaires:
            c.popularite = 0

    context = {
        'activite_data': activite_data,
        'activite_labels': activite_labels,
        'reussite_data': reussite_data,
        'reussite_labels': reussite_labels,
        'cours_populaires': cours_populaires,
        'stats': {
            'mes_cours': nb_cours,
            'total_eleves': total_apprenants,
            'reussite_quiz': reussite_moyenne,
        }
    }


    
    return render(request, 'admin/index.html', context)



@login_required
def dashboard_admin(request):
    if not request.user.is_administrateur:
        messages.error(request, 'Accès refusé. Réservé aux administrateurs.')
        return redirect('index')

    from django.db.models import Sum, Q
    from django.utils import timezone

    maintenant = timezone.now()
    mois_en_cours = maintenant.month
    annee_en_cours = maintenant.year
    trente_jours = maintenant - timezone.timedelta(days=30)

    total_users = User.objects.count()
    total_courses = Cours.objects.count()

    # Revenus du mois : achats de cours, chapitres et livres via le portefeuille
    # (les paiements PayGate créent aussi une TransactionSimulee, donc déjà inclus)
    revenu_mois = TransactionSimulee.objects.filter(
        type_transaction__in=['achat_cours', 'achat_chapitre', 'achat_livre'],
        date_transaction__month=mois_en_cours,
        date_transaction__year=annee_en_cours
    ).aggregate(total=Sum('montant'))['total'] or 0

    # Engagement : % d'étudiants actifs dans les 30 derniers jours
    # (actif = a consulté au moins 1 chapitre OU soumis au moins 1 quiz)
    total_etudiants = Etudiant.objects.count()
    etudiants_actifs = Etudiant.objects.filter(
        Q(chapitres_vus__date_consultation__gte=trente_jours) |
        Q(soumissions__date_soumission__gte=trente_jours)
    ).distinct().count()
    engagement = round((etudiants_actifs / total_etudiants) * 100) if total_etudiants > 0 else 0

    import calendar
    activite_labels = []
    activite_data = []

    for i in range(5, -1, -1):
        d = maintenant - timezone.timedelta(days=i*30)
        m = d.month
        y = d.year
        count = User.objects.filter(date_joined__month=m, date_joined__year=y).count()
        activite_data.append(count)
        mois_nom = calendar.month_abbr[m]
        activite_labels.append(mois_nom)

    context = {
        'stats': {
            'total_users': total_users,
            'total_courses': total_courses,
            'revenu_mois': revenu_mois,
            'engagement': engagement,
        },
        'activite_labels': activite_labels,
        'activite_data': activite_data,
    }

    return render(request, 'admin/index.html', context)

@login_required
def profil(request):
    user = request.user
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_info':
            user.nom = request.POST.get('nom')
            user.prenom = request.POST.get('prenom')
            user.email = request.POST.get('email')
            user.adresse = request.POST.get('adresse')
            age = request.POST.get('age')
            if age:
                user.age = int(age)
            else:
                user.age = None
            user.save()
            messages.success(request, "Profil mis à jour avec succès.")
            
        elif action == 'update_photo':
            if 'photo' in request.FILES:
                user.photo_profil = request.FILES['photo']
                user.save()
                messages.success(request, "Photo de profil mise à jour.")
                
        elif action == 'delete_photo':
            if user.photo_profil:
                # Supprimer le fichier physiquement (optionnel mais propre)
                if os.path.isfile(user.photo_profil.path):
                    os.remove(user.photo_profil.path)
                user.photo_profil = None
                user.save()
                messages.success(request, "Photo de profil supprimée.")
                
        return redirect('profil')
        
    historique = []
    
    # Événements communs
    historique.append({'date': user.date_joined, 'action': 'Création du compte'})
    if user.last_login:
        historique.append({'date': user.last_login, 'action': 'Dernière connexion'})
        
    # Événements spécifiques Étudiant
    if user.is_etudiant:
        inscriptions = Inscription.objects.filter(etudiant=user.etudiant).select_related('cours').order_by('-date_inscription')[:50]
        for insc in inscriptions:
            historique.append({
                'date': insc.date_inscription,
                'action': f'Inscription au cours "{insc.cours.titre}"'
            })
            
        soumissions = SoumissionQuiz.objects.filter(etudiant=user.etudiant).select_related('quiz').order_by('-date_soumission')[:50]
        for soum in soumissions:
            action_text = f'A soumis le quiz "{soum.quiz.titre}"'
            if soum.est_corrige and soum.note_obtenue is not None:
                action_text += f' (Note : {soum.note_obtenue}/{soum.quiz.note_max})'
            historique.append({
                'date': soum.date_soumission,
                'action': action_text
            })
            
    # Événements spécifiques Enseignant
    elif user.is_enseignant:
        visios = SessionVisio.objects.filter(enseignant=user.enseignant).order_by('-date_creation')[:50]
        for v in visios:
            historique.append({
                'date': v.date_creation,
                'action': f'A programmé la visioconférence "{v.titre}"'
            })
            
        from datetime import datetime, time
        cours = Cours.objects.filter(enseignant=user.enseignant).order_by('-date_publication')[:50]
        for c in cours:
            dt = timezone.make_aware(datetime.combine(c.date_publication, time.min))
            historique.append({
                'date': dt,
                'action': f'A publié le cours "{c.titre}"'
            })

    # Messages envoyés (commun)
    messages_envoyes = Message.objects.filter(expediteur=user).order_by('-date_envoi')[:20]
    for msg in messages_envoyes:
        historique.append({
            'date': msg.date_envoi,
            'action': 'A envoyé un message'
        })

    # Conversion de toutes les dates en datetime pour éviter l'erreur de formatage "H" dans le template
    import datetime
    for item in historique:
        d = item['date']
        if type(d) is datetime.date:
            dt = datetime.datetime.combine(d, datetime.time.min)
            item['date'] = timezone.make_aware(dt) if timezone.is_naive(dt) else dt

    # Tri du plus récent au plus ancien
    historique.sort(key=lambda x: x['date'], reverse=True)
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(historique, 5) # 5 éléments par page
    page_number = request.GET.get('page')
    historique_page = paginator.get_page(page_number)
    
    # Statistiques basiques si étudiant (sinon valeurs par défaut)
    stats = {}
    progression_reelle = []
    if user.is_etudiant:
        etudiant = user.etudiant
        # 1. Temps passé (estimation : 2h par chapitre consulté ou acheté)
        ids_vus = set(ChapitreVu.objects.filter(etudiant=etudiant).values_list('chapitre_id', flat=True))
        ids_deb = set(ChapitreDebloque.objects.filter(etudiant=etudiant).values_list('chapitre_id', flat=True))
        nb_chapitres = len(ids_vus | ids_deb)
        stats['temps_passe'] = f"{nb_chapitres * 2}h"
        
        # 2. Cours terminés
        inscriptions = Inscription.objects.filter(etudiant=etudiant).select_related('cours').prefetch_related('cours__chapitres')
        nb_termines = 0
        
        # 3. Calcul progression par cours
        for insc in inscriptions:
            pourcentage = calculer_progression(etudiant, insc.cours)
            if pourcentage == 100:
                nb_termines += 1

            if 0 < pourcentage < 100: # On n'affiche que les cours réellement entamés (1-99%)
                css_class = "bg-danger"
                if pourcentage > 70: css_class = "bg-success"
                elif pourcentage > 30: css_class = "bg-warning"
                
                progression_reelle.append({
                    'cours': insc.cours,
                    'pourcentage': pourcentage,
                    'css_class': css_class
                })
        
        stats['cours_termines'] = nb_termines

    context = {
        'historique': historique_page,
        'stats': stats,
        'progression': progression_reelle
    }
    
    return render(request, 'admin/profil.html', context)


@login_required
def toggle_theme(request):
    if request.method == 'POST':
        theme = request.POST.get('theme')
        if theme in ['light', 'dark']:
            request.user.theme = theme
            request.user.save()
            return JsonResponse({'status': 'success', 'theme': theme})
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def liste_utilisateurs(request):
    if not request.user.is_administrateur:
        messages.error(request, 'Accès refusé.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')
        
        if action == 'create' or action == 'update':
            email = request.POST.get('email')
            nom = request.POST.get('nom')
            prenom = request.POST.get('prenom')
            role = request.POST.get('role')
            password = request.POST.get('password')
            
            if action == 'create':
                if User.objects.filter(email=email).exists():
                    messages.error(request, "Cet email est déjà utilisé.")
                else:
                    # Création via la classe correspondante pour avoir l'héritage correct
                    if role == 'etudiant':
                        new_user = Etudiant.objects.create_user(email=email, nom=nom, prenom=prenom, password=password, role=role)
                    elif role == 'enseignant':
                        new_user = Enseignant.objects.create_user(email=email, nom=nom, prenom=prenom, password=password, role=role)
                    else:
                        new_user = User.objects.create_user(email=email, nom=nom, prenom=prenom, password=password, role=role)
                        if role == 'administrateur':
                            new_user.is_staff = True
                            new_user.save()
                    messages.success(request, f"Utilisateur {email} créé avec succès.")
            
            elif action == 'update':
                user_to_edit = get_object_or_404(User, id=user_id)
                user_to_edit.email = email
                user_to_edit.nom = nom
                user_to_edit.prenom = prenom
                # On ne change pas le rôle ici pour éviter les problèmes d'héritage complexe
                if password:
                    user_to_edit.set_password(password)
                user_to_edit.save()
                messages.success(request, f"Utilisateur {email} mis à jour.")

        elif action == 'delete':
            user_to_delete = get_object_or_404(User, id=user_id)
            if user_to_delete == request.user:
                messages.error(request, "Vous ne pouvez pas supprimer votre propre compte.")
            else:
                email = user_to_delete.email
                user_to_delete.delete()
                messages.success(request, f"Utilisateur {email} supprimé.")
                
        return redirect('liste_utilisateurs')

    utilisateurs = User.objects.all().order_by('-date_joined')
    return render(request, 'admin/utilisateurs.html', {'utilisateurs': utilisateurs})


@login_required
def gestion_cours(request):
    if not request.user.is_administrateur:
        messages.error(request, 'Accès refusé.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        cours_id = request.POST.get('cours_id')
        
        if action == 'update':
            cours_to_edit = get_object_or_404(Cours, id=cours_id)
            cours_to_edit.titre = request.POST.get('titre')
            cours_to_edit.description = request.POST.get('description')
            cours_to_edit.prix = request.POST.get('prix', 0)
            cours_to_edit.est_premium = request.POST.get('est_premium') == 'on'
            
            # Gestion de l'image
            if 'image' in request.FILES:
                cours_to_edit.image = request.FILES['image']
            elif request.POST.get('delete_image') == 'on':
                cours_to_edit.image = None
            
            categorie_id = request.POST.get('categorie')
            if categorie_id:
                cours_to_edit.categorie = get_object_or_404(Categorie, id=categorie_id)
            
            cours_to_edit.save()
            messages.success(request, f"Cours '{cours_to_edit.titre}' mis à jour.")

        elif action == 'delete':
            cours_to_delete = get_object_or_404(Cours, id=cours_id)
            titre = cours_to_delete.titre
            cours_to_delete.delete()
            messages.success(request, f"Cours '{titre}' supprimé.")
            
        return redirect('gestion_cours')

    tous_les_cours_list = Cours.objects.all().select_related('enseignant', 'categorie').order_by('-date_publication')
    
    # Pagination : 6 cours par page
    paginator = Paginator(tous_les_cours_list, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    categories = Categorie.objects.all()
    return render(request, 'admin/cours_admin.html', {
        'tous_les_cours': page_obj,
        'categories': categories
    })


@login_required
def paiements(request):
    from django.db.models import Sum

    if request.user.is_etudiant:
        etudiant = request.user.etudiant

        # Source unique : PaiementPayGate (réel ou simulé, statut=paye)
        pg_paye = PaiementPayGate.objects.filter(
            etudiant=etudiant, statut='paye'
        ).select_related('cours').order_by('-date_paiement')

        total_recharge = pg_paye.filter(type_paiement='recharge').aggregate(t=Sum('montant'))['t'] or 0
        total_depense  = pg_paye.filter(type_paiement='achat_cours').aggregate(t=Sum('montant'))['t'] or 0

        transactions = []
        for p in pg_paye:
            if p.type_paiement == 'achat_cours':
                desc  = f"Achat cours : {p.cours.titre}" if p.cours else "Achat de cours"
                ttype = 'achat_cours'
            else:
                desc  = "Recharge PayGate (TMoney / Flooz)"
                ttype = 'recharge'
            transactions.append({
                'type':        ttype,
                'description': desc,
                'montant':     p.montant,
                'date':        p.date_paiement,
                'reference':   p.tx_reference or p.identifier[:12],
            })

        return render(request, 'admin/paiements.html', {
            'etudiant':       etudiant,
            'transactions':   transactions,
            'total_depense':  total_depense,
            'total_recharge': total_recharge,
        })

    # ── Vue Admin / Enseignant ─────────────────────────────────────────────
    from .models import Etudiant as EtudiantModel

    # Toutes les transactions PayGate (paye) triées les plus récentes en premier
    toutes_transactions = PaiementPayGate.objects.filter(
        statut='paye'
    ).select_related('etudiant', 'cours').order_by('-date_paiement')

    total_achats    = toutes_transactions.filter(type_paiement='achat_cours').aggregate(t=Sum('montant'))['t'] or 0
    total_recharges = toutes_transactions.filter(type_paiement='recharge').aggregate(t=Sum('montant'))['t'] or 0
    nb_etudiants_actifs = toutes_transactions.values('etudiant').distinct().count()

    etudiants_data = []
    for e in EtudiantModel.objects.all():
        pg = PaiementPayGate.objects.filter(etudiant=e, statut='paye')
        recharges = pg.filter(type_paiement='recharge').aggregate(t=Sum('montant'))['t'] or 0
        depenses  = pg.filter(type_paiement='achat_cours').aggregate(t=Sum('montant'))['t'] or 0
        etudiants_data.append({
            'user':           e,
            'solde':          e.solde,
            'total_recharge': recharges,
            'total_depense':  depenses,
            'nb_transactions': pg.count(),
        })

    return render(request, 'admin/paiements.html', {
        'toutes_transactions': toutes_transactions,
        'etudiants_data':      etudiants_data,
        'stats': {
            'revenu_total':       total_achats,
            'total_recharges':    total_recharges,
            'nb_etudiants_actifs': nb_etudiants_actifs,
            'nb_transactions':    toutes_transactions.count(),
        },
    })


@login_required
def acheter_cours_premium(request, cours_id):
    """Achat d'un cours premium par paiement réel PayGate (TMoney / Flooz).

    On NE débite plus le portefeuille : l'étudiant est redirigé vers la page de
    paiement PayGate où il saisit son compte mobile money. L'accès au cours est
    accordé après confirmation du paiement.
    """
    if not request.user.is_etudiant:
        messages.error(request, "Seuls les étudiants peuvent acheter des cours.")
        return redirect('index')

    cours = get_object_or_404(Cours, id=cours_id, est_premium=True)
    etudiant = request.user.etudiant

    # Déjà payé ?
    inscription = Inscription.objects.filter(etudiant=etudiant, cours=cours).first()
    if inscription and inscription.est_paye:
        messages.info(request, "Vous avez déjà débloqué ce cours.")
        return redirect('mes_courses')

    if not cours.prix or cours.prix < 100:
        messages.error(request, "Le prix de ce cours est invalide.")
        return redirect('liste_cours_premium')

    identifier = uuid.uuid4().hex
    PaiementPayGate.objects.create(
        etudiant=etudiant,
        identifier=identifier,
        montant=cours.prix,
        type_paiement='achat_cours',
        cours=cours,
        statut='en_attente',
    )

    # Simulation locale si pas de clé ou mode simulation forcé
    if not settings.PAYGATE_API_KEY or getattr(settings, 'PAYGATE_SIMULATION', False):
        return redirect(reverse('paygate_simulation') + f'?ref={identifier}')

    chemin_retour = reverse('paygate_retour') + f'?ref={identifier}'
    retour_url = (settings.SITE_BASE_URL + chemin_retour) if settings.SITE_BASE_URL else request.build_absolute_uri(chemin_retour)

    from urllib.parse import urlencode
    params = urlencode({
        'token': settings.PAYGATE_API_KEY,
        'amount': int(cours.prix),
        'description': f"Achat cours {cours.titre[:60]} ({request.user.email})",
        'identifier': identifier,
        'url': retour_url,
    })
    return redirect(f"{PAYGATE_PAGE_URL}?{params}")

# ──────────────────────────────────────────────────────────────────────────
#  PAIEMENT RÉEL via PayGate Global (TMoney / Flooz)
# ──────────────────────────────────────────────────────────────────────────
PAYGATE_PAGE_URL = "https://paygateglobal.com/v1/page"
PAYGATE_STATUS_URL = "https://paygateglobal.com/api/v1/status"


def _paygate_verifier_paiement(paiement):
    """Interroge l'API PayGate sur le statut d'un paiement (par identifier).

    Crédite le solde de l'étudiant si le paiement est confirmé (statut 0),
    de façon idempotente (ne crédite qu'une seule fois).

    Retourne une chaîne :
      - 'paye'       : paiement confirmé (solde crédité)
      - 'echoue'     : paiement expiré / annulé
      - 'en_attente' : paiement encore en cours (il faut réessayer plus tard)
      - 'erreur'     : impossible de contacter PayGate / clé absente
    """
    import requests
    if paiement.statut == 'paye':
        return 'paye'
    if paiement.statut == 'echoue':
        return 'echoue'
    if not settings.PAYGATE_API_KEY:
        return 'erreur'

    try:
        resp = requests.post(
            PAYGATE_STATUS_URL,
            json={'auth_token': settings.PAYGATE_API_KEY, 'identifier': paiement.identifier},
            timeout=20,
        )
        data = resp.json()
    except Exception:
        return 'erreur'

    code = data.get('status')

    # status == 0 => paiement réussi côté PayGate
    if code == 0:
        from django.utils import timezone as _tz
        from django.db import transaction as _db_tx
        with _db_tx.atomic():
            # On recharge le verrou sur le paiement pour éviter un double crédit concurrent.
            p = PaiementPayGate.objects.select_for_update().get(id=paiement.id)
            if p.statut == 'paye':
                return 'paye'
            p.statut = 'paye'
            p.tx_reference = str(data.get('tx_reference', ''))[:100]
            p.date_paiement = _tz.now()
            p.save(update_fields=['statut', 'tx_reference', 'date_paiement'])

            etudiant = p.etudiant
            ref = p.tx_reference or p.identifier

            if p.type_paiement == 'achat_cours' and p.cours_id:
                # Paiement direct d'un cours premium : on accorde l'accès (sans toucher au solde).
                inscription, _ = Inscription.objects.get_or_create(
                    etudiant=etudiant, cours=p.cours,
                    defaults={'statut': 'validee', 'est_paye': True},
                )
                if not inscription.est_paye:
                    inscription.statut = 'validee'
                    inscription.est_paye = True
                    inscription.save(update_fields=['statut', 'est_paye'])
                Paiement.objects.create(
                    montant=float(p.montant),
                    date_paiement=_tz.now().date(),
                    moyen_paiement="PayGate (TMoney/Flooz)",
                    etudiant=etudiant,
                )
                TransactionSimulee.objects.create(
                    etudiant=etudiant,
                    montant=p.montant,
                    type_transaction='achat_cours',
                    description=f"Achat cours « {p.cours.titre} » via PayGate (réf. {ref})",
                )
            else:
                # Recharge du portefeuille : on crédite le solde.
                etudiant.solde += p.montant
                etudiant.save(update_fields=['solde'])
                TransactionSimulee.objects.create(
                    etudiant=etudiant,
                    montant=p.montant,
                    type_transaction='recharge',
                    description=f"Recharge PayGate (réf. {ref})",
                )
        return 'paye'

    # status 4 = expiré, 6 = annulé (selon PayGate) => échec définitif
    if code in (4, 6):
        if paiement.statut == 'en_attente':
            paiement.statut = 'echoue'
            paiement.save(update_fields=['statut'])
        return 'echoue'

    # status 2 (en cours) ou transaction pas encore enregistrée => on réessaiera
    return 'en_attente'


@login_required
def recharger_solde(request):
    """Initie une recharge réelle via la page de paiement hébergée PayGate."""
    if not request.user.is_etudiant:
        return redirect('index')

    if request.method != 'POST':
        return redirect('paiements')

    from decimal import Decimal, InvalidOperation
    try:
        montant = Decimal(request.POST.get('montant', '0'))
    except (InvalidOperation, TypeError):
        montant = Decimal('0')

    if montant < 100:
        messages.error(request, "Montant invalide (minimum 100 FCFA).")
        return redirect('paiements')

    identifier = uuid.uuid4().hex
    PaiementPayGate.objects.create(
        etudiant=request.user.etudiant,
        identifier=identifier,
        montant=montant,
        statut='en_attente',
    )

    # Simulation locale si pas de clé ou mode simulation forcé
    if not settings.PAYGATE_API_KEY or getattr(settings, 'PAYGATE_SIMULATION', False):
        return redirect(reverse('paygate_simulation') + f'?ref={identifier}')

    chemin_retour = reverse('paygate_retour') + f'?ref={identifier}'
    if settings.SITE_BASE_URL:
        retour_url = settings.SITE_BASE_URL + chemin_retour
    else:
        retour_url = request.build_absolute_uri(chemin_retour)

    from urllib.parse import urlencode
    params = urlencode({
        'token': settings.PAYGATE_API_KEY,
        'amount': int(montant),
        'description': f"Recharge compte OpenEdu ({request.user.email})",
        'identifier': identifier,
        'url': retour_url,
    })
    return redirect(f"{PAYGATE_PAGE_URL}?{params}")


@login_required
def paygate_retour(request):
    """Page de retour après paiement PayGate : on vérifie et on crédite."""
    if not request.user.is_etudiant:
        return redirect('index')

    identifier = request.GET.get('ref', '')
    paiement = PaiementPayGate.objects.filter(
        identifier=identifier, etudiant=request.user.etudiant
    ).first()

    if not paiement:
        messages.error(request, "Transaction introuvable.")
        return redirect('paiements')

    est_achat_cours = (paiement.type_paiement == 'achat_cours')
    destination = 'mes_courses' if est_achat_cours else 'paiements'

    statut = _paygate_verifier_paiement(paiement)
    if statut == 'paye':
        if est_achat_cours and paiement.cours:
            messages.success(request, f"Paiement confirmé ! Vous avez débloqué le cours « {paiement.cours.titre} ».")
        else:
            messages.success(request, f"Paiement confirmé ! Votre compte a été rechargé de {int(paiement.montant)} FCFA.")
        return redirect(destination)
    if statut == 'echoue':
        messages.error(request, "Le paiement a échoué ou a été annulé. Aucun montant n'a été débité.")
        return redirect(destination)

    # 'en_attente' ou 'erreur' : on affiche une page qui sonde le statut automatiquement.
    return render(request, 'paygate_attente.html', {
        'paiement': paiement,
        'ref': identifier,
    })


@login_required
def paygate_statut_json(request):
    """Endpoint AJAX : renvoie l'état d'un paiement (sondé par la page d'attente)."""
    ref = request.GET.get('ref', '')
    paiement = PaiementPayGate.objects.filter(
        identifier=ref, etudiant=request.user.etudiant
    ).first() if request.user.is_etudiant else None
    if not paiement:
        return JsonResponse({'statut': 'introuvable'}, status=404)
    statut = _paygate_verifier_paiement(paiement)
    return JsonResponse({'statut': statut, 'montant': int(paiement.montant)})


@csrf_exempt
def paygate_callback(request):
    """Webhook appelé par PayGate lorsqu'un paiement est confirmé (production).

    PayGate envoie notamment : identifier, tx_reference, payment_reference, amount.
    On crédite le solde de façon idempotente.
    """
    if request.method != 'POST':
        return HttpResponse(status=405)

    identifier = request.POST.get('identifier') or request.GET.get('identifier')
    if not identifier:
        # Certains appels envoient du JSON
        try:
            import json as _json
            identifier = _json.loads(request.body.decode('utf-8')).get('identifier')
        except Exception:
            identifier = None

    if not identifier:
        return HttpResponse(status=400)

    paiement = PaiementPayGate.objects.filter(identifier=identifier).first()
    if paiement:
        _paygate_verifier_paiement(paiement)
    return HttpResponse("OK")


# ──────────────────────────────────────────────────────────────────────────
#  SIMULATION PAYGATE (mode développement – pas de clé API réelle)
# ──────────────────────────────────────────────────────────────────────────

@login_required
def paygate_simulation(request):
    """Fausse page PayGate pour les tests sans clé API."""
    if not request.user.is_etudiant:
        return redirect('index')

    identifier = request.GET.get('ref', '')
    paiement = PaiementPayGate.objects.filter(
        identifier=identifier, etudiant=request.user.etudiant
    ).first()

    if not paiement or paiement.statut != 'en_attente':
        messages.error(request, "Transaction introuvable ou déjà traitée.")
        return redirect('paiements')

    return render(request, 'paygate_simulation.html', {'paiement': paiement})


@login_required
def paygate_simulation_envoyer_otp(request):
    """Génère un OTP, l'enregistre en session, et tente d'envoyer un SMS via TextBelt."""
    if request.method != 'POST' or not request.user.is_etudiant:
        return JsonResponse({'status': 'error'}, status=400)

    import random

    ref = request.POST.get('ref', '')
    telephone = request.POST.get('telephone', '').replace(' ', '')
    operateur = request.POST.get('operateur', 'tmoney')

    paiement = PaiementPayGate.objects.filter(
        identifier=ref, etudiant=request.user.etudiant, statut='en_attente'
    ).first()

    if not paiement:
        return JsonResponse({'status': 'error', 'message': 'Transaction introuvable.'}, status=404)

    otp = str(random.randint(100000, 999999))
    request.session[f'paygate_otp_{ref}'] = otp
    request.session.modified = True

    numero_complet = f'+228{telephone}'
    montant_str = int(paiement.montant)
    operateur_nom = 'T-Money' if operateur == 'tmoney' else 'Flooz'
    sms_texte = (
        f"[OpenEdu] Code de confirmation : {otp}\n"
        f"Paiement {operateur_nom} de {montant_str} FCFA.\n"
        f"Valable 10 min. Ne partagez pas ce code."
    )

    sms_envoye = False
    try:
        import requests as _req
        resp = _req.post(
            'https://textbelt.com/text',
            data={'phone': numero_complet, 'message': sms_texte, 'key': 'textbelt'},
            timeout=10,
        )
        result = resp.json()
        sms_envoye = bool(result.get('success', False))
    except Exception:
        sms_envoye = False

    if not sms_envoye:
        print(f'[PAYGATE SIM] OTP pour {numero_complet} : {otp}')

    return JsonResponse({
        'status': 'ok',
        'sms_envoye': sms_envoye,
        'numero': numero_complet,
        'otp_dev': otp if not sms_envoye else None,
    })


@login_required
def paygate_simulation_action(request, action):
    """Confirme ou annule un paiement simulé (action = 'confirmer' ou 'annuler')."""
    if request.method != 'POST' or not request.user.is_etudiant:
        return redirect('index')

    identifier = request.POST.get('ref', '')
    paiement = PaiementPayGate.objects.filter(
        identifier=identifier, etudiant=request.user.etudiant, statut='en_attente'
    ).first()

    if not paiement:
        messages.error(request, "Transaction introuvable.")
        return redirect('paiements')

    from django.utils import timezone as _tz

    if action == 'confirmer':
        # Vérifier l'OTP si une session existe pour cette transaction
        session_key = f'paygate_otp_{identifier}'
        otp_attendu = request.session.get(session_key)
        if otp_attendu:
            otp_fourni = request.POST.get('otp', '').strip()
            if otp_fourni != otp_attendu:
                messages.error(request, "Code OTP incorrect. Veuillez réessayer.")
                dest = 'mes_courses' if paiement.type_paiement == 'achat_cours' else 'paiements'
                return redirect(reverse('paygate_simulation') + f'?ref={identifier}')
            del request.session[session_key]
            request.session.modified = True

        ref = f'SIM-{uuid.uuid4().hex[:10].upper()}'
        paiement.statut = 'paye'
        paiement.tx_reference = ref
        paiement.date_paiement = _tz.now()
        paiement.save(update_fields=['statut', 'tx_reference', 'date_paiement'])

        etudiant = paiement.etudiant

        if paiement.type_paiement == 'achat_cours' and paiement.cours_id:
            insc, _ = Inscription.objects.get_or_create(
                etudiant=etudiant, cours=paiement.cours,
                defaults={'statut': 'validee', 'est_paye': True},
            )
            if not insc.est_paye:
                insc.statut = 'validee'
                insc.est_paye = True
                insc.save(update_fields=['statut', 'est_paye'])
            messages.success(request, f"Paiement confirmé ! Vous avez débloqué « {paiement.cours.titre} ».")
            return redirect('mes_courses')
        else:
            etudiant.solde = (etudiant.solde or 0) + paiement.montant
            etudiant.save(update_fields=['solde'])
            messages.success(request, f"Recharge de {int(paiement.montant)} FCFA créditée sur votre compte.")
            return redirect('paiements')

    else:  # annuler
        paiement.statut = 'echoue'
        paiement.save(update_fields=['statut'])
        messages.error(request, "[SIMULATION] Paiement annulé. Aucun montant débité.")
        dest = 'mes_courses' if paiement.type_paiement == 'achat_cours' else 'paiements'
        return redirect(dest)


@login_required
def suivi_activite(request):
    if not request.user.is_administrateur and not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('dashboard')
        
    from django.utils import timezone
    from datetime import timedelta
    import json
    
    # Réussite aux évaluations
    soumissions = SoumissionQuiz.objects.filter(est_corrige=True, note_obtenue__isnull=False)
    succes = 0
    moyen = 0
    echec = 0
    for s in soumissions:
        note_max = s.quiz.note_max
        if note_max == 0: continue
        pourcentage = (s.note_obtenue / note_max) * 100
        if pourcentage >= 70:
            succes += 1
        elif pourcentage >= 50:
            moyen += 1
        else:
            echec += 1
    
    reussite_data = [succes, moyen, echec]

    # Temps d'apprentissage par jour de la semaine en cours
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday()) # Monday
    jours = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    temps_par_jour = []
    
    for i in range(7):
        current_day = start_of_week + timedelta(days=i)
        # on compte 2h par chapitre débloqué ce jour-là
        deblocages = ChapitreDebloque.objects.filter(date_deblocage__date=current_day).count()
        temps_par_jour.append(deblocages * 2)

    # Dernières activités (LogActivite)
    dernieres_activites = LogActivite.objects.all().select_related('utilisateur')[:15]

    context = {
        'reussite_data': json.dumps(reussite_data),
        'jours_labels': json.dumps(jours),
        'temps_data': json.dumps(temps_par_jour),
        'activites': dernieres_activites,
    }
    return render(request, 'admin/suivi_activite.html', context)

def get_dashboard_redirect(user):
    if user.role == 'administrateur':
        return redirect('dashboard_admin')
    elif user.role == 'enseignant':
        return redirect('dashboard_enseignant')
    else:
        return redirect('dashboard_etudiant')


@login_required
def creer_cours_complet(request):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé. Réservé aux enseignants.')
        return redirect('index')

    if request.method == 'POST':
        try:
            cours_id = request.POST.get('cours_id', '').strip()
            titres_finaux = request.POST.getlist('entree_titres')
            contenus_finaux = request.POST.getlist('entree_contenus')

            # Ce formulaire sert à ajouter un module à un cours existant : le lien est obligatoire.
            if not cours_id:
                messages.error(request, 'Veuillez choisir un cours dans la liste « Lier à un cours existant ».')
                return redirect('creer_cours_complet')

            target_cours = get_object_or_404(Cours, id=cours_id)

            # Option premium : si la case est cochée, le cours devient payant
            # et apparaît dans /premium-courses/ (la liste premium se base sur est_premium).
            if request.POST.get('est_premium') == 'on':
                from decimal import Decimal, InvalidOperation
                target_cours.est_premium = True
                try:
                    target_cours.prix = Decimal(request.POST.get('prix') or 0)
                except (InvalidOperation, TypeError):
                    target_cours.prix = 0
                target_cours.save(update_fields=['est_premium', 'prix'])

            titre_module = request.POST.get('titre_module', '').strip()
            if not titre_module:
                messages.error(request, 'Le titre du module est obligatoire.')
                return redirect('creer_cours_complet')

            # Créer un VRAI module pour ce lot de sections (placé après les modules existants)
            from django.db.models import Max
            ordre_module = (Module.objects.filter(cours=target_cours).aggregate(Max('ordre'))['ordre__max'] or 0) + 1
            module = Module.objects.create(
                cours=target_cours,
                titre=titre_module,
                ordre=ordre_module,
            )

            # Créer les sections (chapitres) rattachées à ce module
            nb_crees = 0
            for i, (t, c) in enumerate(zip(titres_finaux, contenus_finaux)):
                if t.strip():
                    Chapitre.objects.create(
                        cours=target_cours,
                        module=module,
                        titre=t.strip(),
                        contenu=c,
                        ordre=i + 1,
                    )
                    nb_crees += 1

            if nb_crees == 0:
                module.delete()  # pas de section : on ne garde pas un module vide
                messages.warning(request, 'Aucune section reçue — le module n\'a pas été créé.')
            else:
                messages.success(request, f'Module « {titre_module} » ajouté ({nb_crees} section(s)) au cours « {target_cours.titre} ».')
            return redirect('gerer_cours_enseignant', cours_id=target_cours.id)

        except Exception as e:
            import traceback
            messages.error(request, f'Erreur : {e} — {traceback.format_exc()}')

    # Tous les cours : on peut lier un nouveau module à n'importe quel cours existant
    # (y compris ceux qui ont déjà du contenu), sans afficher leurs chapitres.
    tous_les_cours = Cours.objects.all().order_by('titre')
    categories = Categorie.objects.all()
    return render(request, 'admin/creer_cours.html', {
        'categories': categories,
        'tous_les_cours': tous_les_cours,
    })

@login_required
def mes_cours_enseignant(request):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé. Réservé aux enseignants.')
        return redirect('index')
    
    # Tous les cours sont gérables par l'enseignant (plateforme mono-équipe).
    mes_cours = Cours.objects.all().select_related('categorie').order_by('titre')

    return render(request, 'admin/mes_cours.html', {'mes_cours': mes_cours})
@login_required
def gerer_cours_enseignant(request, cours_id):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')

    enseignant = request.user.enseignant

    # Ne pas laisser un 404 "no course matches" si le cours existe mais n'est pas
    # visible pour l'enseignant courant : on redirige proprement.
    try:
        cours = Cours.objects.select_related('enseignant').get(id=cours_id)
    except Cours.DoesNotExist:
        messages.error(
            request,
            "Le cours demandé est introuvable ou ne vous appartient pas."
        )
        return redirect('mes_cours_enseignant')

    modules = Module.objects.filter(cours=cours).prefetch_related(
        'chapitres',
        'chapitres__ressources'
    ).order_by('ordre')
    chapitres_sans_module = Chapitre.objects.filter(cours=cours, module=None).order_by('ordre')
    ressources_cours = cours.ressources_annexes.all()
    quiz_list = cours.quiz.all()

    context = {
        'cours': cours,
        'modules': modules,
        'chapitres_sans_module': chapitres_sans_module,
        'ressources_cours': ressources_cours,
        'quiz_list': quiz_list,
    }
    return render(request, 'admin/gerer_cours.html', context)


@login_required
def modifier_cours_complet(request, cours_id):
    """Édition style 'créer cours' : met à jour le cours et ses sections (chapitres sans module)."""
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')

    cours = get_object_or_404(Cours, id=cours_id)

    if request.method == 'POST':
        titre = request.POST.get('titre', '').strip()
        if titre:
            cours.titre = titre
        cours.titre_module = request.POST.get('titre_module', '').strip()
        cours.objectif = request.POST.get('objectif', cours.objectif)
        cours.est_premium = request.POST.get('est_premium') == 'on'
        cours.prix = request.POST.get('prix', 0) or 0
        cours.save()

        ids = request.POST.getlist('entree_ids')
        titres = request.POST.getlist('entree_titres')
        contenus = request.POST.getlist('entree_contenus')

        for cid, t, c in zip(ids, titres, contenus):
            if not t.strip():
                continue
            if cid:
                ch = Chapitre.objects.filter(id=cid, cours=cours).first()
                if ch:
                    ch.titre = t.strip()
                    ch.contenu = c
                    ch.save(update_fields=['titre', 'contenu'])
            else:
                Chapitre.objects.create(
                    cours=cours,
                    titre=t.strip(),
                    contenu=c,
                    ordre=Chapitre.objects.filter(cours=cours).count() + 1,
                )

        messages.success(request, 'Le cours a été mis à jour avec succès.')

    return redirect('gerer_cours_enseignant', cours_id=cours.id)


@login_required
def ajouter_module(request, cours_id):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')
    
    cours = get_object_or_404(Cours, id=cours_id)
    if request.method == 'POST':
        titre = request.POST.get('titre')
        description = request.POST.get('description', '')
        ordre = request.POST.get('ordre', 0)
        
        try:
            nouveau_module = Module.objects.create(
                cours=cours,
                titre=titre,
                description=description,
                ordre=int(ordre) if ordre else 0
            )
            
            # Optional resource file upload
            ressource = request.FILES.get('ressource')
            if ressource:
                ext = os.path.splitext(ressource.name)[1].lower()
                allowed_extensions = ['.pdf', '.txt', '.doc', '.docx', '.ppt', '.pptx']
                if ext in allowed_extensions:
                    RessourceCours.objects.create(
                        cours=cours,
                        titre=f"Ressource Module: {titre}",
                        fichier=ressource
                    )
                    messages.success(request, 'Module créé avec sa ressource.')
                else:
                    messages.warning(request, 'Module créé, mais le format de fichier de la ressource n\'est pas supporté (seuls .pdf, .txt, .doc, .docx, .ppt, .pptx sont acceptés).')
            else:
                messages.success(request, 'Module créé avec succès.')
        except Exception as e:
            messages.error(request, f"Erreur lors de la création du module : {e}")
            
    return redirect('gerer_cours_enseignant', cours_id=cours.id)

@login_required
def supprimer_module(request, module_id):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')
        
    module = get_object_or_404(Module, id=module_id)
    cours_id = module.cours.id
    try:
        module.delete()
        messages.success(request, 'Module supprimé avec succès.')
    except Exception as e:
        messages.error(request, f"Erreur lors de la suppression du module : {e}")

    return redirect('gerer_cours_enseignant', cours_id=cours_id)

@login_required
def basculer_module_premium(request, module_id):
    """Active/désactive le statut premium d'un module (réservé à l'enseignant)."""
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')

    module = get_object_or_404(Module, id=module_id)
    module.est_premium = not module.est_premium
    module.save(update_fields=['est_premium'])
    etat = "Premium" if module.est_premium else "Gratuit"
    messages.success(request, f'Module « {module.titre} » est maintenant : {etat}.')
    return redirect('gerer_cours_enseignant', cours_id=module.cours.id)


@login_required
def modifier_premium_cours(request, cours_id):
    """Réglage rapide du statut premium + prix d'un cours (depuis la page Gérer)."""
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')

    cours = get_object_or_404(Cours, id=cours_id)
    if request.method == 'POST':
        from decimal import Decimal, InvalidOperation
        cours.est_premium = request.POST.get('est_premium') == 'on'
        try:
            cours.prix = Decimal(request.POST.get('prix') or 0)
        except (InvalidOperation, TypeError):
            cours.prix = 0
        cours.save(update_fields=['est_premium', 'prix'])
        etat = f"Premium — {int(cours.prix)} FCFA" if cours.est_premium else "Gratuit"
        messages.success(request, f"Statut du cours mis à jour : {etat}.")
    return redirect('gerer_cours_enseignant', cours_id=cours.id)

@login_required
def ajouter_chapitre_cours(request, cours_id):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')
        
    cours = get_object_or_404(Cours, id=cours_id)
    
    if request.method == 'POST':
        titre = request.POST.get('titre')
        description = request.POST.get('description', '')
        contenu = request.POST.get('contenu', '')
        est_premium = request.POST.get('est_premium') == 'on'
        prix = request.POST.get('prix', 0)
        lien_youtube = request.POST.get('lien_youtube', '')
        ordre = request.POST.get('ordre', cours.chapitres.count() + 1)
        ressource = request.FILES.get('ressource')
        module_id = request.POST.get('module_id')
        
        module = None
        if module_id:
            try:
                module = Module.objects.get(id=module_id, cours=cours)
            except Module.DoesNotExist:
                pass
        
        try:
            chapitre_obj = Chapitre.objects.create(
                cours=cours,
                module=module,
                titre=titre,
                description=description,
                contenu=contenu,
                est_premium=est_premium,
                prix=prix,
                lien_youtube=lien_youtube,
                ordre=ordre,
                ressource=ressource
            )
            
            # Optional resource file upload
            if ressource:
                ext = os.path.splitext(ressource.name)[1].lower()
                allowed_extensions = ['.pdf', '.txt', '.doc', '.docx', '.ppt', '.pptx']
                if ext in allowed_extensions:
                    RessourceChapitre.objects.create(
                        chapitre=chapitre_obj,
                        titre=f"Ressource: {ressource.name}",
                        fichier=ressource
                    )
                    messages.success(request, 'Le chapitre et sa ressource ont été ajoutés avec succès.')
                else:
                    messages.warning(request, 'Le chapitre a été ajouté, mais le format de la ressource n\'est pas supporté (seuls .pdf, .txt, .doc, .docx, .ppt, .pptx sont acceptés).')
            else:
                messages.success(request, 'Le chapitre a été ajouté avec succès.')
        except Exception as e:
            messages.error(request, f"Erreur lors de l'ajout du chapitre: {e}")
            
    return redirect('gerer_cours_enseignant', cours_id=cours.id)

@login_required
def modifier_chapitre_cours(request, chapitre_id):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')
        
    chapitre = get_object_or_404(Chapitre, id=chapitre_id)
    cours_id = chapitre.cours.id
    
    if request.method == 'POST':
        chapitre.titre = request.POST.get('titre')
        chapitre.description = request.POST.get('description', '')
        chapitre.contenu = request.POST.get('contenu', '')
        chapitre.est_premium = request.POST.get('est_premium') == 'on'
        chapitre.prix = request.POST.get('prix', 0)
        chapitre.lien_youtube = request.POST.get('lien_youtube', '')
        chapitre.ordre = request.POST.get('ordre', chapitre.ordre)
        
        module_id = request.POST.get('module_id')
        if module_id:
            try:
                chapitre.module = Module.objects.get(id=module_id, cours=chapitre.cours)
            except Module.DoesNotExist:
                pass
        
        nouvelle_ressource = request.FILES.get('ressource')
        if nouvelle_ressource:
            chapitre.ressource = nouvelle_ressource
            
        try:
            chapitre.save()
            
            # Optional resource file upload
            if nouvelle_ressource:
                ext = os.path.splitext(nouvelle_ressource.name)[1].lower()
                allowed_extensions = ['.pdf', '.txt', '.doc', '.docx', '.ppt', '.pptx']
                if ext in allowed_extensions:
                    RessourceChapitre.objects.create(
                        chapitre=chapitre,
                        titre=f"Ressource: {nouvelle_ressource.name}",
                        fichier=nouvelle_ressource
                    )
            
            messages.success(request, 'Le chapitre a été modifié avec succès.')
        except Exception as e:
            messages.error(request, f'Erreur lors de la modification du chapitre: {e}')
            
    return redirect('gerer_cours_enseignant', cours_id=cours_id)

@login_required
def supprimer_chapitre_cours(request, chapitre_id):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')
        
    chapitre = get_object_or_404(Chapitre, id=chapitre_id)
    cours_id = chapitre.cours.id
    
    try:
        chapitre.delete()
        messages.success(request, 'Le chapitre a été supprimé.')
    except Exception as e:
        messages.error(request, f'Erreur lors de la suppression du chapitre: {e}')
        
    return redirect('gerer_cours_enseignant', cours_id=cours_id)

@login_required
def ajouter_ressource_cours(request, cours_id):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')
        
    cours = get_object_or_404(Cours, id=cours_id)
    
    if request.method == 'POST':
        titre = request.POST.get('titre')
        fichier = request.FILES.get('fichier')
        
        if titre and fichier:
            try:
                RessourceCours.objects.create(
                    cours=cours,
                    titre=titre,
                    fichier=fichier
                )
                messages.success(request, 'La ressource a été ajoutée avec succès.')
            except Exception as e:
                messages.error(request, f"Erreur lors de l'ajout de la ressource: {e}")
        else:
            messages.error(request, 'Le titre et le fichier sont obligatoires.')
            
    return redirect('gerer_cours_enseignant', cours_id=cours.id)

@login_required
def supprimer_ressource_cours(request, ressource_id):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')
        
    ressource = get_object_or_404(RessourceCours, id=ressource_id)
    cours_id = ressource.cours.id
    
    try:
        ressource.delete()
        messages.success(request, 'La ressource a été supprimée.')
    except Exception as e:
        messages.error(request, f'Erreur lors de la suppression de la ressource: {e}')
        
    return redirect('gerer_cours_enseignant', cours_id=cours_id)

@login_required
def ajouter_ressource_chapitre(request, chapitre_id):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')
        
    chapitre = get_object_or_404(Chapitre, id=chapitre_id)
    if request.method == 'POST':
        titre = request.POST.get('titre')
        fichier = request.FILES.get('fichier')
        
        if titre and fichier:
            ext = os.path.splitext(fichier.name)[1].lower()
            allowed_extensions = ['.pdf', '.txt', '.doc', '.docx', '.ppt', '.pptx']
            if ext in allowed_extensions:
                try:
                    RessourceChapitre.objects.create(
                        chapitre=chapitre,
                        titre=titre,
                        fichier=fichier
                    )
                    messages.success(request, 'Ressource ajoutée au chapitre.')
                except Exception as e:
                    messages.error(request, f"Erreur lors de l'ajout de la ressource : {e}")
            else:
                messages.error(request, "Format de fichier non accepté (seuls .pdf, .txt, .doc, .docx, .ppt, .pptx sont acceptés).")
        else:
            messages.error(request, 'Le titre et le fichier sont obligatoires.')
            
    return redirect('gerer_cours_enseignant', cours_id=chapitre.cours.id)

@login_required
def supprimer_ressource_chapitre(request, ressource_id):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')
        
    ressource = get_object_or_404(RessourceChapitre, id=ressource_id)
    cours_id = ressource.chapitre.cours.id
    try:
        ressource.delete()
        messages.success(request, 'Ressource du chapitre supprimée.')
    except Exception as e:
        messages.error(request, f"Erreur lors de la suppression de la ressource : {e}")
        
    return redirect('gerer_cours_enseignant', cours_id=cours_id)


@login_required
def modifier_cours_enseignant(request, id):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')
    
    cours = get_object_or_404(Cours, id=id)
    
    if request.method == 'POST':
        cours.titre = request.POST.get('titre')
        cours.niveau = request.POST.get('niveau')
        cours.objectif = request.POST.get('objectif')
        cours.description = request.POST.get('description')
        
        # Gestion du fichier (ne pas écraser si vide)
        nouvelle_ressource = request.FILES.get('ressource')
        ressource_mise_a_jour = False
        if nouvelle_ressource:
            cours.ressource = nouvelle_ressource
            ressource_mise_a_jour = True
            
        categorie_id = request.POST.get('categorie')
        if categorie_id:
            try:
                cours.categorie = Categorie.objects.get(id=categorie_id)
            except Categorie.DoesNotExist:
                pass
        
        cours.est_premium = request.POST.get('est_premium') == 'on'
        cours.prix = request.POST.get('prix', 0)
        cours.lien_youtube = request.POST.get('lien_youtube')
        
        cours.save()

        # ── Notifications automatiques si ressource mise à jour ──
        if ressource_mise_a_jour:
            etudiants_a_notifier = Etudiant.objects.filter(
                inscriptions__cours=cours,
                inscriptions__statut='validee'
            ).distinct()

            notifs = [
                Notification(
                    destinataire=etudiant,
                    type_notif='nouvelle_ressource',
                    cours=cours,
                )
                for etudiant in etudiants_a_notifier
            ]
            Notification.objects.bulk_create(notifs)
        
        messages.success(request, 'Le cours a été mis à jour.')
        return redirect('mes_cours_enseignant')
    
    categories = Categorie.objects.all()
    return render(request, 'admin/modifier_cours.html', {'cours': cours, 'categories': categories})

@login_required
def supprimer_cours_enseignant(request, id):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')
    
    cours = get_object_or_404(Cours, id=id)
    cours.delete()
    messages.success(request, 'Le cours a été supprimé.')
    return redirect('mes_cours_enseignant')


# ============================================================
# GESTION DES QUIZ (avec génération IA via Claude)
# ============================================================

@login_required
def liste_quiz_enseignant(request):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')
    quiz_list = Quiz.objects.all().select_related('cours').order_by('-id')
    return render(request, 'admin/liste_quiz.html', {'quiz_list': quiz_list})


@login_required
def generer_quiz_ia(request):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')

    # Récupérer TOUS les cours de la base + leurs modules (pour le menu déroulant en cascade)
    mes_cours = Cours.objects.all().order_by('titre')
    mes_modules = Module.objects.select_related('cours').order_by('cours__titre', 'ordre')

    if request.method == 'POST':
        cours_id    = request.POST.get('cours')
        module_id   = request.POST.get('module')
        chapitres   = request.POST.get('chapitres', '').strip()
        nb_questions = int(request.POST.get('nb_questions', 5))
        niveau      = request.POST.get('niveau', 'intermédiaire')
        duree       = request.POST.get('duree', '15')
        instructions_ia = request.POST.get('instructions_ia', '').strip()
        type_correction = request.POST.get('type_correction', 'manuelle')

        if not chapitres:
            messages.error(request, 'Veuillez décrire les chapitres à couvrir.')
            return render(request, 'admin/generer_quiz.html', {'mes_cours': mes_cours, 'mes_modules': mes_modules})

        try:
            cours_obj = Cours.objects.get(id=cours_id)
        except Cours.DoesNotExist:
            messages.error(request, 'Cours introuvable.')
            return render(request, 'admin/generer_quiz.html', {'mes_cours': mes_cours, 'mes_modules': mes_modules})

        # ── Prompt envoyé à Claude ──
        prompt = f"""Tu es un professeur expert en "{cours_obj.titre}".
Génère un quiz pédagogique en JSON pour les chapitres/sujets suivants :

{chapitres}

CONSIGNES DE STYLE ET DE TON DE L'ENSEIGNANT (À RESPECTER PRIORITAIREMENT) :
{instructions_ia if instructions_ia else "Rédige de manière claire, pédagogique et professionnelle."}

INSTRUCTIONS STRICTES :
- Génère exactement {nb_questions} questions à choix multiples (QCM)
- Niveau de difficulté : {niveau}
- Chaque question a exactement 4 choix de réponse (A, B, C, D)
- Une seule réponse correcte par question
- Les questions doivent couvrir tous les chapitres mentionnés de façon équilibrée
- Questions variées : définitions, applications, analyse, comparaison
- Réponds UNIQUEMENT avec du JSON valide, sans texte avant ou après

FORMAT JSON REQUIS (respecte exactement cette structure) :
{{
  "titre": "Quiz - [résumé du sujet]",
  "questions": [
    {{
      "texte": "La question ici ?",
      "points": 1.0,
      "choix": [
        {{"texte": "Réponse A", "est_correct": true}},
        {{"texte": "Réponse B", "est_correct": false}},
        {{"texte": "Réponse C", "est_correct": false}},
        {{"texte": "Réponse D", "est_correct": false}}
      ]
    }}
  ]
}}"""

        try:
            # ── Appel à Gemini (Google) via l'API REST directe ──
            response_text = _gemini_generer_json(prompt)
            quiz_data = json.loads(response_text)

            # ── Créer le Quiz, ses Questions et Choix dans une transaction ──
            # Si quoi que ce soit échoue, RIEN n'est enregistré (pas de quiz à moitié créé).
            from django.db import transaction
            with transaction.atomic():
                module_obj = Module.objects.filter(id=module_id, cours=cours_obj).first() if module_id else None
                quiz = Quiz.objects.create(
                    titre=quiz_data['titre'][:100],
                    duree=f"{duree} min",
                    note_max=float(nb_questions),
                    type_correction=type_correction,
                    cours=cours_obj,
                    module=module_obj
                )

                for q_data in quiz_data['questions']:
                    question = Question.objects.create(
                        quiz=quiz,
                        texte=q_data['texte'],
                        points=q_data.get('points', 1.0),
                        est_ouverte=False
                    )
                    for c_data in q_data['choix']:
                        Choix.objects.create(
                            question=question,
                            texte=c_data['texte'],
                            est_correct=c_data.get('est_correct', False)
                        )

            messages.success(
                request,
                f'✅ Quiz "{quiz.titre}" préparé avec succès — {nb_questions} questions créées !'
            )
            return redirect('detail_quiz_enseignant', id=quiz.id)

        except json.JSONDecodeError:
            messages.error(request, '❌ L\'IA a retourné un format invalide. Réessayez.')
        except Exception as e:
            messages.error(request, f'❌ Erreur lors de la préparation automatique : {str(e)}')

    return render(request, 'admin/generer_quiz.html', {'mes_cours': mes_cours, 'mes_modules': mes_modules})


@login_required
def creer_quiz_manuel(request):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')

    if request.method == 'POST':
        import json as _json
        titre          = request.POST.get('titre', '').strip()
        cours_id       = request.POST.get('cours')
        module_id      = request.POST.get('module')
        duree          = request.POST.get('duree', '30')
        type_correction = request.POST.get('type_correction', 'manuelle')
        questions_json = request.POST.get('questions_json', '[]')
        ressource      = request.FILES.get('ressource_sujet')

        try:
            cours_obj = Cours.objects.get(id=cours_id)
            module_obj = Module.objects.filter(id=module_id, cours=cours_obj).first() if module_id else None
            questions_data = _json.loads(questions_json)

            # Calcul automatique de la note max depuis les questions
            note_max = sum(float(q.get('points', 1)) for q in questions_data) if questions_data else 0.0

            quiz = Quiz.objects.create(
                titre=titre,
                cours=cours_obj,
                module=module_obj,
                duree=f"{duree} min",
                note_max=note_max,
                type_correction=type_correction,
                fichier_quiz=ressource,
            )

            # Créer toutes les questions + choix en une passe
            for q_data in questions_data:
                question = Question.objects.create(
                    quiz=quiz,
                    texte=q_data.get('texte', ''),
                    points=float(q_data.get('points', 1.0)),
                    est_ouverte=q_data.get('est_ouverte', True),
                )
                for c_data in q_data.get('choix', []):
                    if c_data.get('texte', '').strip():
                        Choix.objects.create(
                            question=question,
                            texte=c_data['texte'],
                            est_correct=c_data.get('est_correct', False),
                        )

            nb_q = len(questions_data)
            messages.success(request, f'Quiz « {quiz.titre} » créé avec {nb_q} question{"s" if nb_q > 1 else ""} !')
            return redirect('detail_quiz_enseignant', id=quiz.id)

        except Exception as e:
            messages.error(request, f'Erreur lors de la création : {e}')

    mes_cours = Cours.objects.all().order_by('titre')
    mes_modules = Module.objects.select_related('cours').order_by('cours__titre', 'ordre')
    cours_preselect = request.GET.get('cours_id', '')
    return render(request, 'admin/creer_quiz_manuel.html', {
        'mes_cours': mes_cours,
        'mes_modules': mes_modules,
        'cours_preselect': cours_preselect,
    })


@login_required
def ajouter_question_quiz(request, quiz_id):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')

    quiz = get_object_or_404(Quiz, id=quiz_id)

    if request.method == 'POST':
        texte_question = request.POST.get('texte_question')
        points = float(request.POST.get('points', 1.0))
        media = request.FILES.get('media')

        if not texte_question and not media:
            messages.error(request, 'Veuillez saisir une question ou joindre un fichier.')
            return render(request, 'admin/ajouter_question.html', {'quiz': quiz})
        
        # Création de la question
        question = Question.objects.create(
            quiz=quiz,
            texte=texte_question,
            points=points,
            media=media  # Enregistrement du fichier
        )

        # Récupération des choix
        choix_textes = request.POST.getlist('choix_texte')
        choix_corrects = request.POST.getlist('choix_correct')
        
        has_choices = False
        for i, texte in enumerate(choix_textes):
            if texte.strip():
                has_choices = True
                est_correct = str(i) in choix_corrects
                Choix.objects.create(
                    question=question,
                    texte=texte,
                    est_correct=est_correct
                )
        
        # Si aucun choix n'est saisi, on considère que c'est une question ouverte
        if not has_choices:
            question.est_ouverte = True
            question.save()
        
        # Mettre à jour la note max du quiz (le total des points)
        questions_quiz = quiz.questions.all()
        quiz.note_max = sum(q.points for q in questions_quiz)
        quiz.save()

        if 'enregistrer_et_finir' in request.POST:
            messages.success(request, 'Quiz finalisé avec succès !')
            return redirect('detail_quiz_enseignant', id=quiz.id)
        else:
            messages.success(request, 'Question ajoutée ! Vous pouvez en ajouter une autre.')
            return redirect('ajouter_question_quiz', quiz_id=quiz.id)

    return render(request, 'admin/ajouter_question.html', {'quiz': quiz})


@login_required
def detail_quiz_enseignant(request, id):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')
    quiz = get_object_or_404(Quiz, id=id)

    # Rattacher / détacher le quiz d'un module
    if request.method == 'POST' and request.POST.get('action') == 'set_module':
        module_id = request.POST.get('module')
        quiz.module = Module.objects.filter(id=module_id, cours=quiz.cours).first() if module_id else None
        quiz.save(update_fields=['module'])
        messages.success(request, "Module du quiz mis à jour.")
        return redirect('detail_quiz_enseignant', id=quiz.id)

    questions = quiz.questions.prefetch_related('choix').all()
    modules_du_cours = Module.objects.filter(cours=quiz.cours).order_by('ordre')
    return render(request, 'admin/detail_quiz.html', {
        'quiz': quiz,
        'questions': questions,
        'modules_du_cours': modules_du_cours,
    })


@login_required
def supprimer_quiz_enseignant(request, id):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')
    quiz = get_object_or_404(Quiz, id=id)
    quiz.delete()
    messages.success(request, 'Quiz supprimé avec succès.')
    return redirect('liste_quiz_enseignant')

# ── Gestion des Visioconférences (Meet) ──
@login_required
def liste_sessions_visio(request):
    # --- Traitement "en arrière-plan" automatique ---
    # On met à jour le statut des sessions dont la durée est dépassée
    maintenant = timezone.now()
    sessions_anciennes = SessionVisio.objects.filter(est_termine=False, date_debut__lt=maintenant)
    
    for s in sessions_anciennes:
        fin = s.date_debut + timezone.timedelta(minutes=s.duree)
        if maintenant > fin:
            s.est_termine = True
            s.save()
    # -----------------------------------------------

    if request.user.is_administrateur:
        return redirect('dashboard')
        
    if request.user.is_enseignant:
        sessions_queryset = SessionVisio.objects.filter(enseignant=request.user.enseignant)
    elif request.user.is_etudiant:
        # Pour les étudiants, on affiche les sessions des cours auxquels ils sont inscrits
        inscriptions = Inscription.objects.filter(etudiant=request.user.etudiant, statut='validee')
        cours_ids = [i.cours.id for i in inscriptions]
        sessions_queryset = SessionVisio.objects.filter(cours_id__in=cours_ids)
    else:
        sessions_queryset = SessionVisio.objects.none()
        
    # On évalue le queryset en liste pour pouvoir ajouter un attribut dynamique "statut"
    sessions = list(sessions_queryset)
    
    # Traitement du statut dans la vue
    for s in sessions:
        fin = s.date_debut + timezone.timedelta(minutes=s.duree)
        if s.est_termine or maintenant > fin:
            s.statut = "terminé"
        elif maintenant < s.date_debut:
            s.statut = "à venir"
        else:
            s.statut = "en cours"

    return render(request, 'admin/liste_sessions_visio.html', {'sessions': sessions})

@login_required
def creer_session_visio(request):
    if not request.user.is_enseignant:
        return redirect('index')
    
    # Récupérer TOUS les cours de la base
    cours_disponibles = Cours.objects.all().order_by('titre')
    
    if request.method == 'POST':
        titre = request.POST.get('titre')
        date_debut = request.POST.get('date_debut')
        duree = request.POST.get('duree', 60)
        lien_reunion = request.POST.get('lien_reunion')
        cours_id = request.POST.get('cours')
        
        cours_obj = None
        if cours_id:
            cours_obj = get_object_or_404(Cours, id=cours_id)
            
        SessionVisio.objects.create(
            titre=titre,
            date_debut=date_debut,
            duree=duree,
            lien_reunion=lien_reunion,
            enseignant=request.user.enseignant,
            cours=cours_obj
        )
        messages.success(request, "Session de visioconférence programmée !")
        return redirect('liste_sessions_visio')
        
    return render(request, 'admin/creer_session_visio.html', {'cours_enseignant': cours_disponibles})

@login_required
def supprimer_session_visio(request, session_id):
    if not request.user.is_enseignant and not request.user.is_administrateur:
        return redirect('index')
    
    if request.user.is_administrateur:
        session = get_object_or_404(SessionVisio, id=session_id)
    else:
        session = get_object_or_404(SessionVisio, id=session_id, enseignant=request.user.enseignant)
        
    session.delete()
    messages.success(request, "Session supprimée.")
    return redirect('liste_sessions_visio')


# ============================================================
# MESSAGERIE
# ============================================================

from django.db.models import Max

@login_required
def messagerie_index(request):
    conversations = request.user.conversations.annotate(
        dernier_message_date=Max('messages__date_envoi')
    ).order_by('-dernier_message_date', '-date_mise_a_jour')
    
    return render(request, 'admin/messagerie_index.html', {'conversations': conversations})

@login_required
def nouvelle_conversation(request):
    # Clause de garde 1 : Si ce n'est pas un POST, on affiche juste le template et on s'arrête là
    if request.method != 'POST':
        return render(request, 'admin/nouvelle_conversation.html')

    email_destinataire = request.POST.get('email_destinataire')
    contenu = request.POST.get('contenu')

    # Clause de garde 2 : Vérification des champs vides
    if not email_destinataire or not contenu:
        messages.error(request, "Veuillez renseigner l'adresse email du destinataire et écrire un message.")
        return render(request, 'admin/nouvelle_conversation.html')

    # Clause de garde 3 : Vérification de l'auto-envoi
    if email_destinataire == request.user.email:
        messages.error(request, "Vous ne pouvez pas vous envoyer un message à vous-même.")
        return render(request, 'admin/nouvelle_conversation.html')

    try:
        destinataire = User.objects.get(email=email_destinataire)
        
        # Chercher s'il existe déjà une conversation 1-to-1
        conv = Conversation.objects.filter(participants=request.user).filter(participants=destinataire).first()
        
        if not conv:
            conv = Conversation.objects.create()
            conv.participants.add(request.user, destinataire)
        
        Message.objects.create(
            conversation=conv,
            expediteur=request.user,
            contenu=contenu
        )
        
        conv.date_mise_a_jour = timezone.now()
        conv.save()
        
        messages.success(request, "Message envoyé !")
        return redirect('detail_conversation', conversation_id=conv.id)
        
    except User.DoesNotExist:
        messages.error(request, f"Aucun utilisateur trouvé avec l'adresse email : {email_destinataire}")
        return render(request, 'admin/nouvelle_conversation.html')

@login_required
def detail_conversation(request, conversation_id):
    # On récupère la conversation. Si l'utilisateur n'en fait pas partie, on renvoie une erreur 404.
    conversation = get_object_or_404(request.user.conversations, id=conversation_id)
    
    if request.method == 'POST':
        contenu = request.POST.get('contenu')
        if contenu:
            # On crée le message en base de données
            nouveau_message = Message.objects.create(
                conversation=conversation,
                expediteur=request.user,
                contenu=contenu
            )
            conversation.date_mise_a_jour = timezone.now()
            conversation.save()

            # NOUVEAU : Si la requête vient de JavaScript (AJAX), on renvoie du JSON
            # au lieu de rediriger vers la page (ce qui la rechargerait).
            # request.headers.get('X-Requested-With') est un en-tête que notre
            # JavaScript va envoyer pour identifier la requête comme AJAX.
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'ok',
                    'id': nouveau_message.id,
                    'contenu': nouveau_message.contenu,
                    'date_envoi': nouveau_message.date_envoi.strftime("%H:%M"),
                })
            # Si ce n'est pas AJAX (navigation normale), on redirige comme avant
            return redirect('detail_conversation', conversation_id=conversation.id)
            
    messages_list = conversation.messages.all().order_by('date_envoi')
    messages_list.exclude(expediteur=request.user).update(lu=True)
    
    autre_participant = conversation.participants.exclude(id=request.user.id).first()
    
    return render(request, 'admin/detail_conversation.html', {
        'conversation': conversation,
        'messages_list': messages_list,
        'autre_participant': autre_participant
    })

from django.http import JsonResponse


@login_required
def fetch_messages_chat(request, conversation_id):
    """
    API AJAX appelée par le polling JavaScript toutes les 3 secondes.
    Reçoit l'ID du dernier message déjà affiché sur l'écran, et renvoie
    uniquement les messages plus récents que celui-ci.
    """
    # On vérifie que l'utilisateur a bien accès à cette conversation
    conversation = get_object_or_404(request.user.conversations, id=conversation_id)

    # On récupère le paramètre 'last_id' envoyé par le JavaScript dans l'URL.
    # Exemple d'URL appelée : /api/chat/5/poll/?last_id=42
    # Si 'last_id' n'est pas envoyé, on utilise 0 par défaut (on renverra tous les messages)
    last_id = int(request.GET.get('last_id', 0))

    # On filtre : uniquement les messages dont l'ID est SUPÉRIEUR à last_id
    # C'est-à-dire les messages arrivés APRÈS le dernier qu'on a déjà affiché
    nouveaux_messages = conversation.messages.filter(id__gt=last_id).order_by('date_envoi')

    # On marque comme lus tous les messages reçus (pas envoyés par l'utilisateur actuel)
    nouveaux_messages.exclude(expediteur=request.user).update(lu=True)

    # On construit la liste des messages à renvoyer au format JSON
    data = []
    for msg in nouveaux_messages:
        data.append({
            'id': msg.id,
            # 'sent' = True si c'est un message qu'on a envoyé soi-même
            # Cela servira au JavaScript pour savoir si la bulle doit être bleue (envoyé) ou blanche (reçu)
            'sent': msg.expediteur.id == request.user.id,
            'contenu': msg.contenu,
            'date_envoi': msg.date_envoi.strftime("%H:%M"),
            'lu': msg.lu,
        })

    return JsonResponse({'messages': data})


@login_required
def check_nouveaux_messages(request):
    """
    API View appelée en AJAX pour vérifier s'il y a de nouveaux messages non lus.
    Retourne le nombre total de messages non lus, et les infos du dernier message pour la notification.
    """
    unread_messages = Message.objects.filter(
        conversation__participants=request.user,
        lu=False
    ).exclude(expediteur=request.user).order_by('-date_envoi')
    
    count = unread_messages.count()
    
    data = {
        'count': count,
        'has_new': count > 0,
        'notifications': []
    }
    
    for msg in unread_messages[:5]:  # On limite aux 5 plus récents
        data['notifications'].append({
            'id': msg.id,
            'sender': f"{msg.expediteur.nom} {msg.expediteur.prenom}",
            'content': msg.contenu[:50] + ('...' if len(msg.contenu) > 50 else ''),
            'date': msg.date_envoi.strftime("%d %b %H:%M"),
            'url': f"/dashboard/messagerie/{msg.conversation.id}/"
        })
        
    if count > 0:
        dernier = unread_messages.first()
        data['latest_sender'] = f"{dernier.expediteur.nom} {dernier.expediteur.prenom}"
        data['latest_content'] = dernier.contenu[:50] + ('...' if len(dernier.contenu) > 50 else '')
        data['latest_conversation_id'] = dernier.conversation.id
        
    return JsonResponse(data)


@login_required
def mes_courses(request):
    if not request.user.is_etudiant:
        messages.error(request, 'Accès réservé aux étudiants.')
        return redirect('dashboard')


    inscriptions = Inscription.objects.filter(
        etudiant=request.user.etudiant
    ).select_related('cours', 'cours__categorie').prefetch_related('cours__chapitres')

    # Calcul de la progression réelle par cours et détermination du statut
    nb_en_cours = 0
    nb_termines = 0
    for insc in inscriptions:
        insc.progression = calculer_progression(request.user.etudiant, insc.cours)

        # Déterminer le statut en fonction de la progression :
        # - 100% => terminé
        # - entamé (1% à 99%) => en cours
        # - 0% => inscrit mais pas encore commencé (ne compte pas comme "en cours")
        if insc.progression == 100:
            insc.statut = 'terminee'
            nb_termines += 1
        elif insc.progression > 0:
            insc.statut = 'validee'
            nb_en_cours += 1
        else:
            insc.statut = 'validee'

        # Sauvegarder les changements
        insc.save(update_fields=['statut'])

    # On affiche TOUS les cours inscrits ensemble (gratuits + premium, sans distinction).
    # La distinction premium/débloqué se fait au niveau des modules, dans la page du cours.
    paginator = Paginator(list(inscriptions), 6)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Récupérer les notifications non lues
    notifs = Notification.objects.filter(
        destinataire=request.user,
        lue=False
    ).select_related('cours', 'cours__categorie').order_by('-date_creation')

    # Marquer toutes les notifications comme lues dès la visite de la page
    notifs.update(lue=True)

    # Récupérer les nouveaux cours suggérés (catégories de l'étudiant, non encore inscrits)
    categories_etudiant = inscriptions.values_list('cours__categorie', flat=True).distinct()
    cours_deja_inscrits = inscriptions.values_list('cours_id', flat=True)
    nouveaux_cours = Cours.objects.filter(
        categorie__in=categories_etudiant
    ).exclude(
        id__in=cours_deja_inscrits
    ).select_related('categorie', 'enseignant').order_by('-date_publication')[:6]

    return render(request, 'admin/mes_formations.html', {
        'inscriptions': page_obj,
        'notifs': notifs,
        'nouveaux_cours': nouveaux_cours,
        'stats': {
            'nb_en_cours': nb_en_cours,
            'nb_termines': nb_termines,
        }
    })


@login_required
def voir_cours(request, cours_id):
    cours = get_object_or_404(Cours, id=cours_id)

    # Aperçu autorisé pour l'enseignant propriétaire (ou le staff) : il voit le cours
    # tel que l'étudiant le voit, sans inscription ni suivi de progression.
    est_etudiant = request.user.is_etudiant
    apercu_prof = False
    if not est_etudiant:
        if request.user.is_enseignant or request.user.is_staff:
            apercu_prof = True
        else:
            messages.error(request, 'Accès réservé aux étudiants.')
            return redirect('index')

    inscription = None
    if est_etudiant:
        inscription = Inscription.objects.filter(cours=cours, etudiant=request.user.etudiant).first()

    modules = Module.objects.filter(cours=cours).prefetch_related(
        Prefetch('chapitres', queryset=Chapitre.objects.order_by('ordre'))
    ).order_by('ordre')

    chapitres_sans_module = Chapitre.objects.filter(cours=cours, module=None).order_by('ordre')

    # Statut premium AU NIVEAU DE CHAQUE MODULE (défini par l'enseignant via Module.est_premium) :
    # - badge "Premium" affiché seulement si le module est marqué premium ;
    # - "Débloqué" si l'étudiant a payé le cours (ou aperçu prof), sinon "Bloqué" ;
    # - module non premium => aucun badge.
    est_paye = apercu_prof or bool(inscription and inscription.est_paye)
    modules = list(modules)
    for module in modules:
        module.debloque = est_paye

    chapitre_id = request.GET.get('chapitre')
    chapitre_actif = None
    tous_chapitres = list(Chapitre.objects.filter(cours=cours).order_by('module__ordre', 'ordre'))

    if chapitre_id:
        try:
            chapitre_actif = Chapitre.objects.get(id=chapitre_id, cours=cours)
        except Chapitre.DoesNotExist:
            pass

    # Suivi de progression : on enregistre que l'étudiant a consulté ce chapitre.
    if chapitre_actif and inscription:
        ChapitreVu.objects.get_or_create(
            etudiant=request.user.etudiant,
            chapitre=chapitre_actif,
        )

    # Aucun chapitre demandé : on affiche le sommaire (modules/sections du prof).
    # L'étudiant clique ensuite sur une section pour voir son contenu.

    chapitre_precedent = None
    chapitre_suivant = None
    if chapitre_actif and tous_chapitres:
        idx = next((i for i, c in enumerate(tous_chapitres) if c.id == chapitre_actif.id), None)
        if idx is not None:
            if idx > 0:
                chapitre_precedent = tous_chapitres[idx - 1]
            if idx < len(tous_chapitres) - 1:
                chapitre_suivant = tous_chapitres[idx + 1]

    # Quiz : on rattache chaque quiz à son module ; ceux sans module restent "du cours".
    quiz_list = list(cours.quiz.select_related('module').all())
    quizzes_par_module = {}
    for q in quiz_list:
        if q.module_id:
            quizzes_par_module.setdefault(q.module_id, []).append(q)
    for module in modules:
        module.quiz_list = quizzes_par_module.get(module.id, [])
    quiz_sans_module = [q for q in quiz_list if q.module_id is None]

    context = {
        'cours': cours,
        'modules': modules,
        'chapitres_sans_module': chapitres_sans_module,
        'tous_chapitres': tous_chapitres,
        'chapitre_actif': chapitre_actif,
        'chapitre_precedent': chapitre_precedent,
        'chapitre_suivant': chapitre_suivant,
        'inscription': inscription,
        'quiz_list': quiz_list,
        'quiz_sans_module': quiz_sans_module,
        'apercu_prof': apercu_prof,
    }
    return render(request, 'voir_cours.html', context)



@login_required
def inscription_cours(request, cours_id):
    if request.method != 'POST':
        return redirect('course')

    if not request.user.is_etudiant:
        messages.error(request, 'Seuls les etudiants peuvent s inscrire a un cours.')
        return redirect('dashboard')

    cours = get_object_or_404(Cours, id=cours_id)

    inscription, created = Inscription.objects.get_or_create(
        etudiant=request.user.etudiant,
        cours=cours,
        defaults={'statut': 'validee'},
    )

    if created:
        messages.success(request, f'Vous etes maintenant inscrit au cours "{cours.titre}".')
    elif inscription.statut == 'annulee':
        inscription.statut = 'validee'
        inscription.save(update_fields=['statut'])
        messages.success(request, f'Votre inscription au cours "{cours.titre}" a ete reactivee.')
    else:
        messages.info(request, f'Vous etes deja inscrit au cours "{cours.titre}".')

    return redirect('mes_courses')


@login_required
def mes_quiz_etudiant(request):
    if not request.user.is_etudiant:
        messages.error(request, 'Accès réservé aux étudiants.')
        return redirect('dashboard')

    etudiant = request.user.etudiant

    # IDs des cours inscrits (non annulés)
    cours_inscrits_ids = Inscription.objects.filter(
        etudiant=etudiant
    ).exclude(statut='annulee').values_list('cours_id', flat=True)

    # IDs des quiz déjà soumis par cet étudiant
    quiz_deja_soumis_ids = SoumissionQuiz.objects.filter(
        etudiant=etudiant
    ).values_list('quiz_id', flat=True)

    # Quiz disponibles : liés aux cours inscrits, pas encore soumis, sans doublons
    quiz_disponibles = Quiz.objects.filter(
        cours_id__in=cours_inscrits_ids
    ).exclude(
        id__in=quiz_deja_soumis_ids
    ).select_related('cours', 'cours__enseignant', 'cours__categorie').distinct().order_by('-id')

    return render(request, 'admin/quiz_etudiant.html', {'quiz_disponibles': quiz_disponibles})


@login_required
def detail_quiz_etudiant(request, id):
    if not request.user.is_etudiant:
        messages.error(request, 'Accès réservé aux étudiants.')
        return redirect('dashboard')

    # Récupérer les cours inscrits pour vérifier l'accès
    cours_inscrits_ids = Inscription.objects.filter(
        etudiant=request.user.etudiant
    ).exclude(statut='annulee').values_list('cours_id', flat=True)

    # Récupérer le quiz s'il appartient bien à un cours inscrit
    quiz = Quiz.objects.filter(id=id, cours_id__in=cours_inscrits_ids).first()
    if quiz is None:
        messages.info(request, "Ce quiz n'existe plus ou n'est pas disponible. Voici vos quiz actuels.")
        return redirect('mes_quiz_etudiant')

    # On récupère aussi les questions au cas où ce serait un QCM en ligne
    questions = quiz.questions.prefetch_related('choix').all()

    return render(request, 'admin/detail_quiz_etudiant.html', {
        'quiz': quiz,
        'questions': questions
    })


@login_required
def soumettre_quiz(request, id):
    if not request.user.is_etudiant:
        messages.error(request, 'Accès réservé aux étudiants.')
        return redirect('dashboard')

    if request.method != 'POST':
        return redirect('detail_quiz_etudiant', id=id)

    quiz = get_object_or_404(Quiz, id=id)
    etudiant = request.user.etudiant

    # Vérifier si l'étudiant a déjà soumis
    if SoumissionQuiz.objects.filter(quiz=quiz, etudiant=etudiant).exists():
        messages.warning(request, "Vous avez déjà soumis ce quiz.")
        return redirect('mes_resultats_etudiant')

    # Récupération des données selon le type de quiz
    fichier_reponse = request.FILES.get('fichier_reponse')
    reponses_qcm = {}
    
    if not fichier_reponse:
        # Collecter les réponses QCM (tous les champs qui commencent par question_)
        for key, value in request.POST.items():
            if key.startswith('question_'):
                reponses_qcm[key] = value

    soumission = SoumissionQuiz.objects.create(
        quiz=quiz,
        etudiant=etudiant,
        fichier_reponse=fichier_reponse,
        reponses_qcm=json.dumps(reponses_qcm) if reponses_qcm else None
    )

    if quiz.type_correction == 'auto':
        # --- CORRECTION AUTOMATIQUE PAR IA ---
        try:
            prompt = f"""Tu es un professeur sévère mais juste.
Évalue le travail d'un étudiant pour le quiz "{quiz.titre}".
La note maximale est de {quiz.note_max}.

Sujet / Contexte : Le quiz appartient au cours "{quiz.cours.titre}".
Travail de l'étudiant (Réponses JSON ou nom de fichier joint) : {reponses_qcm if reponses_qcm else 'Fichier joint'}
"""
            # Pour un traitement complet des fichiers, il faudrait idéalement extraire le texte du PDF/Word.
            # Ici on simule une évaluation de base avec les réponses QCM.
            prompt += """
Évalue le travail de l'étudiant et retourne UNIQUEMENT un objet JSON valide avec ce format exact :
{
  "note": 14.5,
  "commentaires": "Bon travail dans l'ensemble. Les concepts X et Y sont bien compris. Attention à Z."
}
"""
            resultat = json.loads(_gemini_generer_json(prompt))
            
            soumission.note_obtenue = resultat.get('note', 0)
            soumission.commentaires = resultat.get('commentaires', "Évaluation générée par IA.")
            soumission.est_corrige = True
            soumission.corrige_par_ia = True
            soumission.save()

            messages.success(request, "Votre note s'affichera dans 'Mes résultats', allez consulter.")
        except Exception as e:
            # En cas d'erreur de l'IA, on bascule en correction manuelle par sécurité
            messages.warning(request, f"Erreur lors de l'auto-correction de l'IA. Le professeur corrigera manuellement. ({str(e)})")
            soumission.est_corrige = False
            soumission.save()
            messages.success(request, "Votre note s'affichera dans vos résultats dès que l'enseignant aura finalisé la correction.")
    else:
        # --- CORRECTION MANUELLE ---
        messages.success(request, "Votre note s'affichera dans vos résultats dès que l'enseignant aura finalisé la correction.")

    return redirect('mes_resultats_etudiant')


@login_required
def mes_resultats_etudiant(request):
    if not request.user.is_etudiant:
        messages.error(request, 'Accès réservé aux étudiants.')
        return redirect('dashboard')
        
    soumissions = SoumissionQuiz.objects.filter(etudiant=request.user.etudiant).select_related('quiz', 'quiz__cours').order_by('-date_soumission')
    
    # Préparer les données pour l'affichage (QCM)
    for soumission in soumissions:
        soumission.questions_info = []
        if soumission.reponses_qcm:
            try:
                reponses_dict = json.loads(soumission.reponses_qcm)
                questions = soumission.quiz.questions.all()
                for q in questions:
                    rep_etudiant = reponses_dict.get(f'question_{q.id}', 'Non répondu')
                    
                    # Chercher la bonne réponse (s'il y en a une définie)
                    bonne_reponse = ""
                    if not q.est_ouverte:
                        correct_choix = q.choix.filter(est_correct=True).first()
                        if correct_choix:
                            bonne_reponse = correct_choix.texte
                            
                    soumission.questions_info.append({
                        'question': q.texte,
                        'reponse_etudiant': rep_etudiant,
                        'bonne_reponse': bonne_reponse,
                        'points': q.points
                    })
            except json.JSONDecodeError:
                pass
                
    return render(request, 'admin/mes_resultats.html', {'soumissions': soumissions})


@login_required
def detail_resultat_etudiant(request, soumission_id):
    if not request.user.is_etudiant:
        messages.error(request, 'Accès réservé aux étudiants.')
        return redirect('dashboard')

    soumission = get_object_or_404(SoumissionQuiz, id=soumission_id, etudiant=request.user.etudiant)

    soumission.questions_info = []
    if soumission.reponses_qcm:
        try:
            reponses_dict = json.loads(soumission.reponses_qcm)
            questions = soumission.quiz.questions.all()
            for q in questions:
                rep_etudiant = reponses_dict.get(f'question_{q.id}', 'Non répondu')
                bonne_reponse = ""
                if not q.est_ouverte:
                    correct_choix = q.choix.filter(est_correct=True).first()
                    if correct_choix:
                        bonne_reponse = correct_choix.texte
                soumission.questions_info.append({
                    'question': q.texte,
                    'reponse_etudiant': rep_etudiant,
                    'bonne_reponse': bonne_reponse,
                    'points': q.points
                })
        except json.JSONDecodeError:
            pass

    return render(request, 'admin/detail_resultat.html', {'soumission': soumission})


@login_required
def corrections_attente(request):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('dashboard')
        
    soumissions = SoumissionQuiz.objects.filter(
        est_corrige=False
    ).select_related('quiz', 'etudiant', 'quiz__cours').order_by('date_soumission')
    
    return render(request, 'admin/corrections_attente.html', {'soumissions': soumissions})


@login_required
def corriger_soumission(request, soumission_id):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('dashboard')
        
    soumission = get_object_or_404(
        SoumissionQuiz,
        id=soumission_id
    )
    
    if request.method == 'POST':
        note = request.POST.get('note')
        commentaires = request.POST.get('commentaires')
        
        try:
            soumission.note_obtenue = float(note)
            soumission.commentaires = commentaires
            soumission.est_corrige = True
            soumission.corrige_par_ia = False
            soumission.save()
            
            messages.success(request, f'La correction pour {soumission.etudiant} a été enregistrée avec succès.')
            return redirect('corrections_attente')
        except ValueError:
            messages.error(request, 'Veuillez saisir une note valide.')
            
    # Si c'est un QCM, on a des réponses en JSON
    reponses_dict = {}
    questions_info = []
    
    if soumission.reponses_qcm:
        try:
            reponses_dict = json.loads(soumission.reponses_qcm)
            # Récupérer les vraies questions pour afficher le texte
            questions = soumission.quiz.questions.all()
            for q in questions:
                # La clé dans le dict est de type 'question_1'
                rep = reponses_dict.get(f'question_{q.id}', 'Non répondu')
                questions_info.append({'question': q.texte, 'points': q.points, 'reponse': rep})
        except json.JSONDecodeError:
            pass
            
    return render(request, 'admin/corriger_soumission.html', {
        'soumission': soumission,
        'questions_info': questions_info
    })


@login_required
def liste_livres(request):
    livres = Livre.objects.all().order_by('-date_ajout')
    livres_achetes = []
    if request.user.is_etudiant:
        livres_achetes = AchatLivre.objects.filter(etudiant=request.user.etudiant).values_list('livre_id', flat=True)
    
    return render(request, 'admin/bibliotheque.html', {
        'livres': livres,
        'livres_achetes': livres_achetes
    })

@login_required
def acheter_livre(request, livre_id):
    if not request.user.is_etudiant:
        messages.error(request, "Seuls les étudiants peuvent acheter des livres.")
        return redirect('index')
    
    livre = get_object_or_404(Livre, id=livre_id)
    etudiant = request.user.etudiant
    
    if AchatLivre.objects.filter(etudiant=etudiant, livre=livre).exists():
        messages.info(request, "Vous possédez déjà ce livre.")
        return redirect('liste_livres')
    
    if etudiant.solde >= livre.prix:
        etudiant.solde -= livre.prix
        etudiant.save()
        
        AchatLivre.objects.create(
            etudiant=etudiant,
            livre=livre,
            montant_paye=livre.prix
        )
        
        TransactionSimulee.objects.create(
            etudiant=etudiant,
            montant=livre.prix,
            type_transaction='achat_livre',
            description=f"Achat du livre : {livre.titre}"
        )
        
        messages.success(request, f"Livre '{livre.titre}' ajouté à votre collection !")
    else:
        messages.error(request, "Solde insuffisant pour acheter ce livre.")
        
    return redirect('liste_livres')


# ============================================================
# COURS ET CHAPITRES PREMIUM
# ============================================================

@login_required
def liste_cours_premium(request):
    # Cours ayant au moins un chapitre premium OU marqué comme premium globalement
    from django.db.models import Q
    cours_premium = Cours.objects.filter(
        Q(chapitres__est_premium=True) | Q(est_premium=True)
    ).distinct().prefetch_related('chapitres', 'enseignant', 'categorie')
    
    for cours in cours_premium:
        premium_chapitres = cours.chapitres.filter(est_premium=True)
        cours.nb_premium = premium_chapitres.count()
        
        # Si le cours est premium mais n'a pas de chapitres premium, on simule 1 chapitre (le cours lui-même)
        if cours.est_premium and cours.nb_premium == 0:
            cours.nb_premium = 1
            cours.prix_mini = cours.prix
        else:
            cours.prix_mini = premium_chapitres.aggregate(Min('prix'))['prix__min'] or 0
        
        # Vérification si débloqué : un cours premium n'est débloqué QUE s'il a été payé.
        cours.debloque = False
        if request.user.is_authenticated and request.user.is_etudiant:
            cours.debloque = Inscription.objects.filter(
                etudiant=request.user.etudiant,
                cours=cours,
                est_paye=True
            ).exists()
            
    return render(request, 'cours_premium.html', {'cours_premium': cours_premium})


@login_required
def detail_cours_premium(request, cours_id):
    # Sur l'URL /cours/<id>/ on affiche EXACTEMENT la même page que « voir le cours » :
    # thème vert, minuteur à gauche (filtres jour/semaine/mois/année) et quiz sous
    # chaque module concerné. On délègue donc à la vue voir_cours.
    return voir_cours(request, cours_id)

    # --- Correction legacy : cours sans chapitres ---
    chapitres_qs = cours.chapitres.all().order_by('ordre')
    if not chapitres_qs.exists() and (cours.ressource or cours.lien_youtube):
        legacy_chapitre = Chapitre.objects.create(
            cours=cours,
            titre="Contenu complet du cours",
            description="Accédez aux ressources principales fournies lors de la création.",
            est_premium=cours.est_premium,
            prix=cours.prix if cours.est_premium else 0,
            ressource=cours.ressource,
            lien_youtube=cours.lien_youtube,
            ordre=1
        )
        chapitres_qs = Chapitre.objects.filter(id=legacy_chapitre.id).order_by('ordre')

    # --- Modules + chapitres ordonnés (prefetch + ordre) ---
    # IMPORTANT: certains projets ajoutent des chapitres directement à Chapitre(cours=...) sans les relier à un Module.
    # On gère donc un fallback pour que la Table des matières s'affiche toujours.
    modules = (
        Module.objects.filter(cours=cours)
        .prefetch_related('chapitres')
        .order_by('ordre')
    )

    # Flat list de tous les chapitres, dans l'ordre global (module.ordre puis chapitre.ordre)
    tous_chapitres_ordonnes = []
    for m in modules:
        tous_chapitres_ordonnes.extend(
            list(m.chapitres.all().order_by('ordre'))
        )

    # Fallback: s'il n'y a aucun module/aucun chapitre via modules, on récupère les chapitres liés directement au cours.
    if not tous_chapitres_ordonnes:
        chapitres_sans_module = list(cours.chapitres.all().order_by('ordre'))
        tous_chapitres_ordonnes = chapitres_sans_module

        # Pour que la sidebar (modules -> chapitres) fonctionne sans casser le template,
        # on crée une structure de module virtuel uniquement en mémoire via l'injection de `chapitres`.
        class _ModuleVirtuel:
            def __init__(self, chapitres):
                self._chapitres = chapitres
            @property
            def chapitres(self):
                return self._chapitres

        modules = [_ModuleVirtuel(chapitres_sans_module)]



    if not tous_chapitres_ordonnes:
        # fallback : au cas où un cours existe sans module/chapitres (rare)
        tous_chapitres_ordonnes = list(cours.chapitres.all().order_by('ordre'))

    contenu_vide = len(tous_chapitres_ordonnes) == 0

    chapitre_actuel = None
    chapitre_precedent = None
    chapitre_suivant = None

    chapitre_id_param = request.GET.get('chapitre_id')
    if chapitre_id_param is None:
        chapitre_id_param = request.GET.get('chapitre')

    if not contenu_vide:
        if chapitre_id_param:
            try:
                chapitre_id_val = int(chapitre_id_param)
                chapitre_actuel = next((c for c in tous_chapitres_ordonnes if c.id == chapitre_id_val), None)
            except (TypeError, ValueError):
                chapitre_actuel = None

        if chapitre_actuel is None:
            chapitre_actuel = tous_chapitres_ordonnes[0]

        idx = tous_chapitres_ordonnes.index(chapitre_actuel)
        chapitre_precedent = tous_chapitres_ordonnes[idx - 1] if idx > 0 else None
        chapitre_suivant = tous_chapitres_ordonnes[idx + 1] if idx < len(tous_chapitres_ordonnes) - 1 else None

    return render(request, 'detail_cours_premium.html', {
        'cours': cours,
        'modules': modules,
        'contenu_vide': contenu_vide,
        'chapitre_actuel': chapitre_actuel,
        'chapitre_precedent': chapitre_precedent,
        'chapitre_suivant': chapitre_suivant,
    })



@login_required
def acheter_chapitre(request, chapitre_id):
    if not request.user.is_etudiant:
        return JsonResponse({'status': 'error', 'message': "Seuls les étudiants peuvent acheter des chapitres."}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': "Méthode non autorisée."}, status=405)
        
    chapitre = get_object_or_404(Chapitre, id=chapitre_id, est_premium=True)
    etudiant = request.user.etudiant
    
    if ChapitreDebloque.objects.filter(etudiant=etudiant, chapitre=chapitre).exists():
        return JsonResponse({'status': 'error', 'message': "Vous avez déjà débloqué ce chapitre."}, status=400)
        
    if etudiant.solde >= chapitre.prix:
        etudiant.solde -= chapitre.prix
        etudiant.save()
        
        ChapitreDebloque.objects.create(etudiant=etudiant, chapitre=chapitre)
        
        TransactionSimulee.objects.create(
            etudiant=etudiant,
            montant=chapitre.prix,
            type_transaction='achat_chapitre',
            description=f"Déblocage du chapitre : {chapitre.titre} ({chapitre.cours.titre})"
        )
        
        return JsonResponse({
            'status': 'success', 
            'message': f"Le chapitre '{chapitre.titre}' a été débloqué avec succès !",
            'nouveau_solde': float(etudiant.solde)
        })
    else:
        return JsonResponse({'status': 'error', 'message': "Solde insuffisant."}, status=400)

@login_required
def mes_chapitres_debloques(request):
    if not request.user.is_etudiant:
        messages.error(request, "Accès réservé aux étudiants.")
        return redirect('dashboard')

    etudiant = request.user.etudiant

    # Chapitres individuels achetés (via solde portefeuille)
    deblocages = ChapitreDebloque.objects.filter(etudiant=etudiant).select_related(
        'chapitre', 'chapitre__cours'
    ).order_by('-date_deblocage')

    # Cours premium entiers payés (via PayGate)
    cours_premium_payes = Inscription.objects.filter(
        etudiant=etudiant,
        cours__est_premium=True,
        est_paye=True,
    ).select_related('cours').prefetch_related('cours__chapitres').order_by('-date_inscription')

    return render(request, 'admin/mes_chapitres_debloques.html', {
        'deblocages': deblocages,
        'cours_premium_payes': cours_premium_payes,
    })

@login_required
def fetch_notifications(request):
    """
    API AJAX pour récupérer les notifications non lues.
    """
    notifs = Notification.objects.filter(
        destinataire=request.user,
        lue=False
    ).select_related('cours').order_by('-date_creation')[:5]
    
    data = []
    for n in notifs:
        # Icone et couleur selon le type
        icon = 'fa-book-open'
        color = 'bg-primary'
        if n.type_notif == 'nouvelle_ressource':
            icon = 'fa-file-alt'
            color = 'bg-success'
            
        data.append({
            'id': n.id,
            'message': f"{n.get_type_notif_display()} : {n.cours.titre}",
            'date': n.date_creation.strftime("%d/%m %H:%M"),
            'icon': icon,
            'color': color
        })
    
    return JsonResponse({'notifications': data, 'count': notifs.count()})
