from django.contrib.auth import authenticate, login, logout
from django.db.models import F

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from .models import User, Etudiant, Enseignant, Cours, Inscription, Categorie, Quiz, Question, Choix, SessionVisio, Conversation, Message, Notification, SoumissionQuiz, Paiement, Livre, AchatLivre, TransactionSimulee, Chapitre, ChapitreDebloque, LogActivite
import json
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import google.generativeai as genai
import os

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

# Dashboards (Version "Nue" sans contextes)
@login_required
def dashboard_etudiant(request):
    if not request.user.is_etudiant:
        messages.error(request, 'Accès refusé. Réservé aux étudiants.')
        return redirect('index')
    
    etudiant = request.user.etudiant
    
    # === CALCUL DES STATS RÉELLES ===
    # 1. Inscriptions et Progression par cours
    inscriptions = Inscription.objects.filter(etudiant=etudiant).select_related('cours').prefetch_related('cours__chapitres')
    
    # On calcule la progression pour chaque inscription
    for insc in inscriptions:
        total_chapitres = insc.cours.chapitres.count()
        if total_chapitres > 0:
            debloques = ChapitreDebloque.objects.filter(etudiant=etudiant, chapitre__cours=insc.cours).count()
            insc.progression = min(int((debloques / total_chapitres) * 100), 100)
        else:
            insc.progression = 0

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
    
    from django.db.models import Sum
    from django.utils import timezone
    
    mois_en_cours = timezone.now().month
    annee_en_cours = timezone.now().year
    
    total_users = User.objects.count()
    total_courses = Cours.objects.count()
    revenu_mois = TransactionSimulee.objects.filter(
        type_transaction__in=['achat_cours', 'achat_chapitre', 'achat_livre'],
        date_transaction__month=mois_en_cours,
        date_transaction__year=annee_en_cours
    ).aggregate(total=Sum('montant'))['total'] or 0
    
    import calendar
    activite_labels = []
    activite_data = []
    
    for i in range(5, -1, -1):
        d = timezone.now() - timezone.timedelta(days=i*30)
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
        # 1. Temps passé (Même simulation que dashboard : 2h par chapitre)
        nb_chapitres = ChapitreDebloque.objects.filter(etudiant=etudiant).count()
        stats['temps_passe'] = f"{nb_chapitres * 2}h"
        
        # 2. Cours terminés
        inscriptions = Inscription.objects.filter(etudiant=etudiant).select_related('cours').prefetch_related('cours__chapitres')
        nb_termines = 0
        
        # 3. Calcul progression par cours
        for insc in inscriptions:
            total = insc.cours.chapitres.count()
            if total > 0:
                count_deb = ChapitreDebloque.objects.filter(etudiant=etudiant, chapitre__cours=insc.cours).count()
                pourcentage = min(int((count_deb / total) * 100), 100)
                if pourcentage == 100:
                    nb_termines += 1
            else:
                pourcentage = 0
            
            if pourcentage < 100: # On n'affiche que ceux "en cours" dans la liste de progression ?
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
    if request.user.is_etudiant:
        etudiant = request.user.etudiant
        transactions = TransactionSimulee.objects.filter(etudiant=etudiant).order_by('-date_transaction')
        from django.db.models import Sum
        total_depense = transactions.filter(
            type_transaction__in=['achat_cours', 'achat_chapitre', 'achat_livre']
        ).aggregate(total=Sum('montant'))['total'] or 0
        total_recharge = transactions.filter(
            type_transaction='recharge'
        ).aggregate(total=Sum('montant'))['total'] or 0
        context = {
            'etudiant': etudiant,
            'transactions': transactions,
            'total_depense': total_depense,
            'total_recharge': total_recharge,
        }
        return render(request, 'admin/paiements.html', context)
    
    # Vue Admin / Enseignant — Données détaillées
    from django.db.models import Sum, Count
    
    # Toutes les transactions simulées (richesses réelles des étudiants)
    toutes_transactions = TransactionSimulee.objects.all().select_related('etudiant').order_by('-date_transaction')
    
    # Stats globales
    total_achats = toutes_transactions.filter(type_transaction__in=['achat_cours', 'achat_chapitre', 'achat_livre']).aggregate(total=Sum('montant'))['total'] or 0
    total_recharges = toutes_transactions.filter(type_transaction='recharge').aggregate(total=Sum('montant'))['total'] or 0
    nb_etudiants_actifs = toutes_transactions.values('etudiant').distinct().count()
    
    # Par étudiant : solde + total dépensé
    from .models import Etudiant as EtudiantModel
    etudiants = EtudiantModel.objects.all()

    etudiants_data = []
    for e in etudiants:
        depenses = TransactionSimulee.objects.filter(
            etudiant=e, 
            type_transaction__in=['achat_cours', 'achat_chapitre', 'achat_livre']
        ).aggregate(total=Sum('montant'))['total'] or 0
        recharges = TransactionSimulee.objects.filter(etudiant=e, type_transaction='recharge').aggregate(total=Sum('montant'))['total'] or 0
        etudiants_data.append({
            'user': e,
            'solde': e.solde,
            'total_depense': depenses,
            'total_recharge': recharges,
            'nb_transactions': TransactionSimulee.objects.filter(etudiant=e).count(),
        })
    
    stats = {
        'revenu_total': total_achats,
        'total_recharges': total_recharges,
        'nb_etudiants_actifs': nb_etudiants_actifs,
        'nb_transactions': toutes_transactions.count(),
    }
    return render(request, 'admin/paiements.html', {
        'toutes_transactions': toutes_transactions,
        'etudiants_data': etudiants_data,
        'stats': stats
    })


@login_required
def acheter_cours_premium(request, cours_id):
    if not request.user.is_etudiant:
        messages.error(request, "Seuls les étudiants peuvent acheter des cours.")
        return redirect('index')
    
    cours = get_object_or_404(Cours, id=cours_id, est_premium=True)
    etudiant = request.user.etudiant
    
    if Inscription.objects.filter(etudiant=etudiant, cours=cours).exists():
        messages.info(request, "Vous êtes déjà inscrit à ce cours.")
        return redirect('mes_courses')
    
    if etudiant.solde >= cours.prix:
        etudiant.solde -= cours.prix
        etudiant.save()
        
        Inscription.objects.create(
            etudiant=etudiant,
            cours=cours,
            statut='validee',
            est_paye=True
        )
        
        Paiement.objects.create(
            montant=float(cours.prix),
            date_paiement=timezone.now().date(),
            moyen_paiement="Portefeuille Virtuel",
            etudiant=etudiant
        )
        
        TransactionSimulee.objects.create(
            etudiant=etudiant,
            montant=cours.prix,
            type_transaction='achat_cours',
            description=f"Achat du cours : {cours.titre}"
        )
        
        messages.success(request, f"Félicitations ! Vous avez débloqué le cours '{cours.titre}'.")
        return redirect('mes_courses')
    else:
        messages.error(request, "Solde insuffisant pour acheter ce cours.")
        return redirect('course')

@login_required
def recharger_solde(request):
    if not request.user.is_etudiant:
        return redirect('index')
    
    if request.method == 'POST':
        montant = request.POST.get('montant', 10000)
        try:
            montant_int = int(montant)
            etudiant = request.user.etudiant
            etudiant.solde += montant_int
            etudiant.save()
            
            TransactionSimulee.objects.create(
                etudiant=etudiant,
                montant=montant_int,
                type_transaction='recharge',
                description="Recharge du compte (Simulation)"
            )
            messages.success(request, f"Votre compte a été rechargé de {montant_int} FCFA.")
        except ValueError:
            messages.error(request, "Montant invalide.")
        
    return redirect('paiements')

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


def creer_cours_enseignant(request):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé. Réservé aux enseignants.')
        return redirect('index')

    if request.method == 'POST':
        titre_chapitre = request.POST.get('titre')
        niveau = request.POST.get('niveau') # Bien que lié au chapitre, le niveau peut être hérité ou spécifique
        objectif = request.POST.get('objectif')
        description = request.POST.get('description')
        ressource = request.FILES.get('ressource')
        cours_id = request.POST.get('cours_id')

        try:
            cours_obj = get_object_or_404(Cours, id=cours_id)

            est_premium = request.POST.get('est_premium') == 'on'
            prix = request.POST.get('prix', 0)
            lien_youtube = request.POST.get('lien_youtube')

            # Créer le chapitre lié au cours sélectionné
            nouveau_chapitre = Chapitre.objects.create(
                cours=cours_obj,
                titre=titre_chapitre,
                description=description,
                est_premium=est_premium,
                prix=prix,
                ressource=ressource,
                lien_youtube=lien_youtube,
                ordre=cours_obj.chapitres.count() + 1
            )

            # Optionnel : mettre à jour le niveau du cours si nécessaire
            if niveau:
                cours_obj.niveau = niveau
                cours_obj.save()

            messages.success(request, f'Le chapitre "{titre_chapitre}" a été ajouté avec succès au cours "{cours_obj.titre}".')
            return redirect('dashboard_enseignant')
        except Exception as e:
            messages.error(request, f'Erreur lors de l\'ajout du chapitre : {e}')

    # Récupérer TOUS les cours de la base (ceux visibles sur cours.html)
    tous_les_cours = Cours.objects.all().order_by('titre')
    return render(request, 'admin/creer_cours.html', {'mes_cours': tous_les_cours})

@login_required
def mes_cours_enseignant(request):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé. Réservé aux enseignants.')
        return redirect('index')
    
    # Récupérer les cours de l'enseignant avec leurs catégories
    mes_cours = Cours.objects.filter(enseignant=request.user.enseignant).select_related('categorie')
    
    return render(request, 'admin/mes_cours.html', {'mes_cours': mes_cours})

@login_required
def modifier_cours_enseignant(request, id):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')
    
    cours = get_object_or_404(Cours, id=id, enseignant=request.user.enseignant)
    
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
    
    cours = get_object_or_404(Cours, id=id, enseignant=request.user.enseignant)
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
    quiz_list = Quiz.objects.filter(
        cours__enseignant=request.user.enseignant
    ).select_related('cours').order_by('-id')
    return render(request, 'admin/liste_quiz.html', {'quiz_list': quiz_list})


@login_required
def generer_quiz_ia(request):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')

    # Récupérer TOUS les cours de la base
    mes_cours = Cours.objects.all().order_by('titre')

    if request.method == 'POST':
        cours_id    = request.POST.get('cours')
        chapitres   = request.POST.get('chapitres', '').strip()
        nb_questions = int(request.POST.get('nb_questions', 5))
        niveau      = request.POST.get('niveau', 'intermédiaire')
        duree       = request.POST.get('duree', '15')
        instructions_ia = request.POST.get('instructions_ia', '').strip()
        type_correction = request.POST.get('type_correction', 'manuelle')

        if not chapitres:
            messages.error(request, 'Veuillez décrire les chapitres à couvrir.')
            return render(request, 'admin/generer_quiz.html', {'mes_cours': mes_cours})

        try:
            cours_obj = Cours.objects.get(id=cours_id)
        except Cours.DoesNotExist:
            messages.error(request, 'Cours introuvable.')
            return render(request, 'admin/generer_quiz.html', {'mes_cours': mes_cours})

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
            # ── Appel à Gemini (Google) ──
            # On force le transport 'rest' pour éviter les erreurs gRPC/404 sur Windows
            genai.configure(api_key=settings.GEMINI_API_KEY, transport='rest')
            model = genai.GenerativeModel('gemini-flash-latest')
            
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )

            response_text = response.text.strip()
            quiz_data = json.loads(response_text)

            # ── Créer le Quiz en base ──
            quiz = Quiz.objects.create(
                titre=quiz_data['titre'],
                duree=f"{duree} min",
                note_max=float(nb_questions),
                type_correction=type_correction,
                cours=cours_obj
            )

            # ── Créer les Questions et Choix ──
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

    return render(request, 'admin/generer_quiz.html', {'mes_cours': mes_cours})


@login_required
def creer_quiz_manuel(request):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')

    if request.method == 'POST':
        titre = request.POST.get('titre')
        cours_id = request.POST.get('cours')
        duree = request.POST.get('duree')
        type_correction = request.POST.get('type_correction', 'manuelle')

        try:
            cours_obj = Cours.objects.get(id=cours_id)
            fichier_quiz = request.FILES.get('fichier_quiz')
            note_max = request.POST.get('note_max', 0.0)

            quiz = Quiz.objects.create(
                titre=titre,
                cours=cours_obj,
                duree=f"{duree} min",
                note_max=float(note_max),
                type_correction=type_correction,
                fichier_quiz=fichier_quiz
            )
            
            if fichier_quiz:
                messages.success(request, f'Quiz "{quiz.titre}" créé avec le fichier joint !')
                return redirect('liste_quiz_enseignant')
            else:
                messages.success(request, f'Quiz "{quiz.titre}" créé ! Ajoutez maintenant vos questions.')
                return redirect('ajouter_question_quiz', quiz_id=quiz.id)
        except Exception as e:
            messages.error(request, f'Erreur lors de la création : {e}')

    # Récupérer TOUS les cours de la base
    mes_cours = Cours.objects.all().order_by('titre')
    return render(request, 'admin/creer_quiz_manuel.html', {'mes_cours': mes_cours})


@login_required
def ajouter_question_quiz(request, quiz_id):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')

    quiz = get_object_or_404(Quiz, id=quiz_id, cours__enseignant=request.user.enseignant)

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
    quiz = get_object_or_404(Quiz, id=id, cours__enseignant=request.user.enseignant)
    questions = quiz.questions.prefetch_related('choix').all()
    return render(request, 'admin/detail_quiz.html', {'quiz': quiz, 'questions': questions})


@login_required
def supprimer_quiz_enseignant(request, id):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('index')
    quiz = get_object_or_404(Quiz, id=id, cours__enseignant=request.user.enseignant)
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

    # Calcul de la progression réelle par cours
    for insc in inscriptions:
        total_chapitres = insc.cours.chapitres.count()
        if total_chapitres > 0:
            debloques = ChapitreDebloque.objects.filter(etudiant=request.user.etudiant, chapitre__cours=insc.cours).count()
            insc.progression = min(int((debloques / total_chapitres) * 100), 100)
            # Si progression est 100%, on pourrait marquer comme terminée si ce n'est pas déjà le cas
            if insc.progression == 100 and insc.statut != 'terminee':
                insc.statut = 'terminee'
                insc.save(update_fields=['statut'])
        else:
            insc.progression = 0

    nb_en_cours = inscriptions.filter(statut='validee').count()
    nb_termines = inscriptions.filter(statut='terminee').count()

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
        'inscriptions': inscriptions,
        'notifs': notifs,
        'nouveaux_cours': nouveaux_cours,
        'stats': {
            'nb_en_cours': nb_en_cours,
            'nb_termines': nb_termines,
        }
    })



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

    # Récupérer les ID des cours où l'étudiant est inscrit (statut = validée)
    cours_inscrits_ids = Inscription.objects.filter(
        etudiant=request.user.etudiant,
        statut='validee'
    ).values_list('cours_id', flat=True)

    # Récupérer les quiz associés à ces cours
    quiz_disponibles = Quiz.objects.filter(
        cours_id__in=cours_inscrits_ids
    ).select_related('cours', 'cours__enseignant', 'cours__categorie').order_by('-id')

    return render(request, 'admin/quiz_etudiant.html', {'quiz_disponibles': quiz_disponibles})


@login_required
def detail_quiz_etudiant(request, id):
    if not request.user.is_etudiant:
        messages.error(request, 'Accès réservé aux étudiants.')
        return redirect('dashboard')

    # Récupérer les cours inscrits pour vérifier l'accès
    cours_inscrits_ids = Inscription.objects.filter(
        etudiant=request.user.etudiant,
        statut='validee'
    ).values_list('cours_id', flat=True)

    # Récupérer le quiz s'il appartient bien à un cours inscrit
    quiz = get_object_or_404(Quiz, id=id, cours_id__in=cours_inscrits_ids)
    
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
            genai.configure(api_key=settings.GEMINI_API_KEY, transport='rest')
            model = genai.GenerativeModel('gemini-flash-latest')
            
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
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            resultat = json.loads(response.text.strip())
            
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
def corrections_attente(request):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé.')
        return redirect('dashboard')
        
    soumissions = SoumissionQuiz.objects.filter(
        quiz__cours__enseignant=request.user.enseignant,
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
        id=soumission_id, 
        quiz__cours__enseignant=request.user.enseignant
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
            cours.prix_mini = premium_chapitres.aggregate(models.Min('prix'))['prix__min'] or 0
        
        # Vérification si débloqué
        cours.debloque = False
        if request.user.is_authenticated and request.user.is_etudiant:
            cours.debloque = Inscription.objects.filter(
                etudiant=request.user.etudiant, 
                cours=cours, 
                statut='validee'
            ).exists()
            
    return render(request, 'cours_premium.html', {'cours_premium': cours_premium})


@login_required
def detail_cours_premium(request, cours_id):
    cours = get_object_or_404(Cours, id=cours_id)
    chapitres = cours.chapitres.all().order_by('ordre')
    
    # Correction pour les cours existants sans chapitres
    if not chapitres.exists() and (cours.ressource or cours.lien_youtube):
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
        chapitres = [legacy_chapitre]

    chapitres_debloques_ids = []
    est_inscrit = False
    if request.user.is_etudiant:
        # Vérifier si l'étudiant est déjà inscrit au cours complet (achat legacy)
        est_inscrit = Inscription.objects.filter(
            etudiant=request.user.etudiant, 
            cours=cours, 
            statut='validee'
        ).exists()
        
        # Récupérer les chapitres achetés individuellement
        chapitres_debloques_ids = list(ChapitreDebloque.objects.filter(
            etudiant=request.user.etudiant, 
            chapitre__cours=cours
        ).values_list('chapitre_id', flat=True))
        
    return render(request, 'detail_cours_premium.html', {
        'cours': cours,
        'chapitres': chapitres,
        'chapitres_debloques_ids': chapitres_debloques_ids,
        'est_inscrit': est_inscrit
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
        
    deblocages = ChapitreDebloque.objects.filter(etudiant=request.user.etudiant).select_related('chapitre', 'chapitre__cours').order_by('-date_deblocage')
    return render(request, 'admin/mes_chapitres_debloques.html', {'deblocages': deblocages})

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
