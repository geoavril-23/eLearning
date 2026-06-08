from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('courses/', views.course, name='course'),
    path('apropos/', views.apropos, name='a_propos'),
    path('contact/', views.contact, name='contact'),
    path('register/', views.admin_register, name='register'),
    
    # Dashboards
    path('dashboard/', views.dashboard, name='dashboard'),

    path('dashboard/admin/login/', views.admin_login, name='admin_login'),
    path('dashboard/admin/logout/', views.admin_logout, name='admin_logout'),
    path('dashboard/etudiant/', views.dashboard_etudiant_view, name='dashboard_etudiant'),
    path('dashboard/etudiant/mes-courses/', views.mes_courses, name='mes_courses'),
    path('dashboard/etudiant/cours/<int:cours_id>/voir/', views.voir_cours, name='voir_cours'),
    path('dashboard/etudiant/inscription/<int:cours_id>/', views.inscription_cours, name='inscription_cours'),
    path('dashboard/enseignant/', views.dashboard_enseignant, name='dashboard_enseignant'),
    path('dashboard/admin/', views.dashboard_admin, name='dashboard_admin'),
    path('dashboard/profil/', views.profil, name='profil'),
    path('dashboard/toggle-theme/', views.toggle_theme, name='toggle_theme'),
    path('dashboard/admin/utilisateurs/', views.liste_utilisateurs, name='liste_utilisateurs'),
    path('dashboard/admin/cours/', views.gestion_cours, name='gestion_cours'),
    path('dashboard/admin/paiements/', views.paiements, name='paiements'),
    path('dashboard/etudiant/acheter-cours/<int:cours_id>/', views.acheter_cours_premium, name='acheter_cours_premium'),
    path('dashboard/etudiant/recharger/', views.recharger_solde, name='recharger_solde'),
    path('dashboard/etudiant/paygate/retour/', views.paygate_retour, name='paygate_retour'),
    path('dashboard/etudiant/paygate/statut/', views.paygate_statut_json, name='paygate_statut_json'),
    path('paygate/callback/', views.paygate_callback, name='paygate_callback'),
    path('dashboard/etudiant/paygate/simulation/', views.paygate_simulation, name='paygate_simulation'),
    path('dashboard/etudiant/paygate/simulation/<str:action>/', views.paygate_simulation_action, name='paygate_simulation_action'),
    path('dashboard/bibliotheque/', views.liste_livres, name='liste_livres'),
    path('dashboard/etudiant/acheter-livre/<int:livre_id>/', views.acheter_livre, name='acheter_livre'),
    path('dashboard/admin/activite/', views.suivi_activite, name='suivi_activite'),
    path('dashboard/enseignant/cours/nouveau-complet/', views.creer_cours_complet, name='creer_cours_complet'),
    path('dashboard/enseignant/mes-cours/', views.mes_cours_enseignant, name='mes_cours_enseignant'),
    path('dashboard/enseignant/cours/<int:cours_id>/gerer/', views.gerer_cours_enseignant, name='gerer_cours_enseignant'),
    path('dashboard/enseignant/cours/<int:cours_id>/modifier-complet/', views.modifier_cours_complet, name='modifier_cours_complet'),
    path('dashboard/enseignant/cours/<int:cours_id>/chapitre/ajouter/', views.ajouter_chapitre_cours, name='ajouter_chapitre_cours'),
    path('dashboard/enseignant/chapitre/<int:chapitre_id>/modifier/', views.modifier_chapitre_cours, name='modifier_chapitre_cours'),
    path('dashboard/enseignant/chapitre/<int:chapitre_id>/supprimer/', views.supprimer_chapitre_cours, name='supprimer_chapitre_cours'),
    path('dashboard/enseignant/cours/<int:cours_id>/ressource/ajouter/', views.ajouter_ressource_cours, name='ajouter_ressource_cours'),
    path('dashboard/enseignant/ressource/<int:ressource_id>/supprimer/', views.supprimer_ressource_cours, name='supprimer_ressource_cours'),
    path('dashboard/enseignant/cours/<int:cours_id>/module/ajouter/', views.ajouter_module, name='ajouter_module'),
    path('dashboard/enseignant/module/<int:module_id>/supprimer/', views.supprimer_module, name='supprimer_module'),
    path('dashboard/enseignant/module/<int:module_id>/premium/', views.basculer_module_premium, name='basculer_module_premium'),
    path('dashboard/enseignant/cours/<int:cours_id>/statut-premium/', views.modifier_premium_cours, name='modifier_premium_cours'),
    path('dashboard/enseignant/chapitre/<int:chapitre_id>/ressource/ajouter/', views.ajouter_ressource_chapitre, name='ajouter_ressource_chapitre'),
    path('dashboard/enseignant/ressource-chapitre/<int:ressource_id>/supprimer/', views.supprimer_ressource_chapitre, name='supprimer_ressource_chapitre'),
    # Legacy routes (if needed, but replaced by the unified view)
    path('dashboard/enseignant/cours/supprimer/<int:id>/', views.supprimer_cours_enseignant, name='supprimer_cours_enseignant'),

    # Quiz (Génération IA et Manuel)
    path('dashboard/enseignant/quiz/', views.liste_quiz_enseignant, name='liste_quiz_enseignant'),
    path('dashboard/enseignant/quiz/generer/', views.generer_quiz_ia, name='generer_quiz_ia'),
    path('dashboard/enseignant/quiz/nouveau/', views.creer_quiz_manuel, name='creer_quiz_manuel'),
    path('dashboard/enseignant/quiz/<int:quiz_id>/ajouter-question/', views.ajouter_question_quiz, name='ajouter_question_quiz'),
    path('dashboard/enseignant/quiz/<int:id>/', views.detail_quiz_enseignant, name='detail_quiz_enseignant'),
    path('dashboard/enseignant/quiz/<int:id>/supprimer/', views.supprimer_quiz_enseignant, name='supprimer_quiz_enseignant'),
    
    # Quiz (Étudiant)
    path('dashboard/etudiant/quiz/', views.mes_quiz_etudiant, name='mes_quiz_etudiant'),
    path('dashboard/etudiant/quiz/<int:id>/', views.detail_quiz_etudiant, name='detail_quiz_etudiant'),
    path('dashboard/etudiant/quiz/<int:id>/soumettre/', views.soumettre_quiz, name='soumettre_quiz'),
    path('dashboard/etudiant/mes-resultats/', views.mes_resultats_etudiant, name='mes_resultats_etudiant'),
    path('dashboard/etudiant/mes-resultats/<int:soumission_id>/', views.detail_resultat_etudiant, name='detail_resultat_etudiant'),
    
    # Correction Quiz (Enseignant)
    path('dashboard/enseignant/corrections/', views.corrections_attente, name='corrections_attente'),
    path('dashboard/enseignant/corrections/<int:soumission_id>/', views.corriger_soumission, name='corriger_soumission'),
    
    # Visioconférence (Meet)
    path('dashboard/enseignant/visio/', views.liste_sessions_visio, name='liste_sessions_visio'),
    path('dashboard/enseignant/visio/nouveau/', views.creer_session_visio, name='creer_session_visio'),
    path('dashboard/enseignant/visio/<int:session_id>/supprimer/', views.supprimer_session_visio, name='supprimer_session_visio'),
    
    # Messagerie
    path('dashboard/messagerie/', views.messagerie_index, name='messagerie_index'),
    path('dashboard/messagerie/nouvelle/', views.nouvelle_conversation, name='nouvelle_conversation'),
    path('dashboard/messagerie/<int:conversation_id>/', views.detail_conversation, name='detail_conversation'),
    
    # API pour les notifications
    path('api/messages/unread/', views.check_nouveaux_messages, name='api_unread_messages'),

    # API AJAX pour le polling du chat en temps réel
    # Reçoit l'ID de la conversation et le paramètre ?last_id= dans l'URL
    path('api/chat/<int:conversation_id>/poll/', views.fetch_messages_chat, name='api_fetch_messages_chat'),

    # Cours et Chapitres Premium
    path('premium-courses/', views.liste_cours_premium, name='liste_cours_premium'),
    path('cours/<int:cours_id>/', views.detail_cours_premium, name='detail_cours_premium'),

    path('api/chapitre/<int:chapitre_id>/acheter/', views.acheter_chapitre, name='acheter_chapitre'),
    path('dashboard/etudiant/mes-chapitres/', views.mes_chapitres_debloques, name='mes_chapitres_debloques'),
    path('api/notifications/fetch/', views.fetch_notifications, name='fetch_notifications'),
]
