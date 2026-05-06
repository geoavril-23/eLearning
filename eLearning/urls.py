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
    path('dashboard/etudiant/', views.dashboard_etudiant, name='dashboard_etudiant'),
    path('dashboard/enseignant/', views.dashboard_enseignant, name='dashboard_enseignant'),
    path('dashboard/admin/', views.dashboard_admin, name='dashboard_admin'),
    path('dashboard/profil/', views.profil, name='profil'),
    path('dashboard/admin/utilisateurs/', views.liste_utilisateurs, name='liste_utilisateurs'),
    path('dashboard/admin/cours/', views.gestion_cours, name='gestion_cours'),
    path('dashboard/admin/paiements/', views.paiements, name='paiements'),
    path('dashboard/admin/activite/', views.suivi_activite, name='suivi_activite'),
    path('dashboard/enseignant/cours/nouveau/', views.creer_cours_enseignant, name='creer_cours_enseignant'),
    path('dashboard/enseignant/mes-cours/', views.mes_cours_enseignant, name='mes_cours_enseignant'),
    path('dashboard/enseignant/cours/modifier/<int:id>/', views.modifier_cours_enseignant, name='modifier_cours_enseignant'),
    path('dashboard/enseignant/cours/supprimer/<int:id>/', views.supprimer_cours_enseignant, name='supprimer_cours_enseignant'),

    # Quiz (Génération IA et Manuel)
    path('dashboard/enseignant/quiz/', views.liste_quiz_enseignant, name='liste_quiz_enseignant'),
    path('dashboard/enseignant/quiz/generer/', views.generer_quiz_ia, name='generer_quiz_ia'),
    path('dashboard/enseignant/quiz/nouveau/', views.creer_quiz_manuel, name='creer_quiz_manuel'),
    path('dashboard/enseignant/quiz/<int:quiz_id>/ajouter-question/', views.ajouter_question_quiz, name='ajouter_question_quiz'),
    path('dashboard/enseignant/quiz/<int:id>/', views.detail_quiz_enseignant, name='detail_quiz_enseignant'),
    path('dashboard/enseignant/quiz/<int:id>/supprimer/', views.supprimer_quiz_enseignant, name='supprimer_quiz_enseignant'),
    
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
]