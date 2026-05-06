from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from .models import User, Etudiant, Enseignant, Cours, Inscription, Categorie, Quiz, Question, Choix, SessionVisio, Conversation, Message
import json
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import google.generativeai as genai

# Vues de base
def index(request):
    return render(request, 'index.html')

def course(request):
    return render(request, 'course.html')

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
    # Récupérer les inscriptions de l'étudiant
    inscriptions = []
    if request.user.is_etudiant:
        inscriptions = Inscription.objects.filter(etudiant=request.user.etudiant).select_related('cours')
    else:
        messages.error(request, 'Accès refusé. Réservé aux étudiants.')
        return redirect('index')
    
    return render(request, 'admin/index.html', {'mes_inscriptions': inscriptions})

@login_required
def dashboard_enseignant(request):
    if not request.user.is_enseignant:
        messages.error(request, 'Accès refusé. Réservé aux enseignants.')
        return redirect('index')
    
    # === STATS POUR LES GRAPHIQUES ===
    # 1. Progression (Inscriptions aux cours de cet enseignant sur les 7 derniers jours)
    # Pour l'instant, on met des données dynamiques basées sur le nombre de ses cours
    nb_cours = Cours.objects.filter(enseignant=request.user.enseignant).count()
    activite_data = [nb_cours * 2, nb_cours * 3, nb_cours * 1, nb_cours * 5, nb_cours * 4, nb_cours * 6, nb_cours * 8]
    
    # 2. Réussite (Simulation basée sur les inscriptions)
    total_inscrits = Inscription.objects.filter(cours__enseignant=request.user.enseignant).count()
    # On répartit arbitrairement pour la démo visuelle
    reussite_data = [
        int(total_inscrits * 0.6), # 60% succès
        int(total_inscrits * 0.3), # 30% moyen
        int(total_inscrits * 0.1)  # 10% échec
    ]
    
    context = {
        'activite_data': json.dumps(activite_data),
        'reussite_data': json.dumps(reussite_data),
        'stats': {
            'mes_cours': nb_cours,
            'total_eleves': total_inscrits,
            'reussite_quiz': 85,
            'questions_attente': 3
        }
    }
    
    return render(request, 'admin/index.html', context)

@login_required
def dashboard_admin(request):
    if not request.user.is_administrateur:
        messages.error(request, 'Accès refusé. Réservé aux administrateurs.')
        return redirect('index')
    return render(request, 'admin/index.html')

@login_required
def profil(request):
    return render(request, 'admin/profil.html')

@login_required
def liste_utilisateurs(request):
    return render(request, 'admin/utilisateurs.html')

@login_required
def gestion_cours(request):
    return render(request, 'admin/cours_admin.html')

@login_required
def paiements(request):
    return render(request, 'admin/paiements.html')

@login_required
def suivi_activite(request):
    return render(request, 'admin/suivi_activite.html')

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
        titre = request.POST.get('titre')
        niveau = request.POST.get('niveau')
        objectif = request.POST.get('objectif')
        description = request.POST.get('description')
        ressource = request.FILES.get('ressource')
        categorie_id = request.POST.get('categorie')

        try:
            # Récupérer la catégorie sélectionnée
            categorie_obj = None
            if categorie_id:
                try:
                    categorie_obj = Categorie.objects.get(id=categorie_id)
                except Categorie.DoesNotExist:
                    pass

            Cours.objects.create(
                titre=titre,
                niveau=niveau,
                objectif=objectif,
                description=description,
                date_publication=timezone.now().date(),
                ressource=ressource,
                enseignant=request.user.enseignant,
                categorie=categorie_obj
            )
            messages.success(request, 'Votre cours a été créé et publié avec succès !')
            return redirect('dashboard_enseignant')
        except Exception as e:
            messages.error(request, f'Erreur lors de la création du cours : {e}')

    categories = Categorie.objects.all()
    return render(request, 'admin/creer_cours.html', {'categories': categories})
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
        if nouvelle_ressource:
            cours.ressource = nouvelle_ressource
            
        categorie_id = request.POST.get('categorie')
        if categorie_id:
            try:
                cours.categorie = Categorie.objects.get(id=categorie_id)
            except Categorie.DoesNotExist:
                pass
        
        cours.save()
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

    mes_cours = Cours.objects.filter(enseignant=request.user.enseignant)

    if request.method == 'POST':
        cours_id    = request.POST.get('cours')
        chapitres   = request.POST.get('chapitres', '').strip()
        nb_questions = int(request.POST.get('nb_questions', 5))
        niveau      = request.POST.get('niveau', 'intermédiaire')
        duree       = request.POST.get('duree', '15')
        instructions_ia = request.POST.get('instructions_ia', '').strip()

        if not chapitres:
            messages.error(request, 'Veuillez décrire les chapitres à couvrir.')
            return render(request, 'admin/generer_quiz.html', {'mes_cours': mes_cours})

        try:
            cours_obj = Cours.objects.get(id=cours_id, enseignant=request.user.enseignant)
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

        try:
            cours_obj = Cours.objects.get(id=cours_id, enseignant=request.user.enseignant)
            fichier_quiz = request.FILES.get('fichier_quiz')
            note_max = request.POST.get('note_max', 0.0)

            quiz = Quiz.objects.create(
                titre=titre,
                cours=cours_obj,
                duree=f"{duree} min",
                note_max=float(note_max),
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

    mes_cours = Cours.objects.filter(enseignant=request.user.enseignant)
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
    
    cours_enseignant = Cours.objects.filter(enseignant=request.user.enseignant)
    
    if request.method == 'POST':
        titre = request.POST.get('titre')
        date_debut = request.POST.get('date_debut')
        duree = request.POST.get('duree', 60)
        lien_reunion = request.POST.get('lien_reunion')
        cours_id = request.POST.get('cours')
        
        cours_obj = None
        if cours_id:
            cours_obj = get_object_or_404(Cours, id=cours_id, enseignant=request.user.enseignant)
            
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
        
    return render(request, 'admin/creer_session_visio.html', {'cours_enseignant': cours_enseignant})

@login_required
def supprimer_session_visio(request, session_id):
    if not request.user.is_enseignant:
        return redirect('index')
    
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
