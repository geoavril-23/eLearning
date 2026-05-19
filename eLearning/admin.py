from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Etudiant, Administrateur, Enseignant, Inscription, Cours, Quiz, Paiement, Chapitre, ChapitreDebloque, TransactionSimulee


class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ['email', 'nom', 'prenom', 'role', 'is_active']
    list_filter = ['role', 'is_active']
    search_fields = ['email', 'nom', 'prenom']
    ordering = ['email']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('nom', 'prenom', 'age', 'adresse', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nom', 'prenom', 'age', 'adresse', 'role', 'password1', 'password2'),
        }),
    )


@admin.register(Etudiant)
class EtudiantAdmin(admin.ModelAdmin):
    list_display = ['email', 'nom', 'prenom', 'niveau', 'solde', 'is_active']
    list_filter = ['niveau', 'is_active']
    search_fields = ['email', 'nom', 'prenom', 'etablissement']
    fieldsets = (
        ('Informations utilisateur', {'fields': ('email', 'nom', 'prenom', 'age', 'adresse', 'password')}),
        ('Informations étudiant', {'fields': ('niveau', 'etablissement', 'solde')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )


@admin.register(Administrateur)
class AdministrateurAdmin(admin.ModelAdmin):
    list_display = ['email', 'nom', 'prenom', 'is_active']
    list_filter = ['is_active']
    search_fields = ['email', 'nom', 'prenom']
    fieldsets = (
        ('Informations utilisateur', {'fields': ('email', 'nom', 'prenom', 'age', 'adresse', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )


@admin.register(Enseignant)
class EnseignantAdmin(admin.ModelAdmin):
    list_display = ['email', 'nom', 'prenom', 'specialite', 'is_active']
    list_filter = ['specialite', 'is_active']
    search_fields = ['email', 'nom', 'prenom', 'specialite']
    fieldsets = (
        ('Informations utilisateur', {'fields': ('email', 'nom', 'prenom', 'age', 'adresse', 'password')}),
        ('Informations enseignant', {'fields': ('specialite',)}),  # ← cours_crees supprimé
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )


class InscriptionInline(admin.TabularInline):
    model = Inscription
    extra = 0
    readonly_fields = ['date_inscription']  # ← corrigé


class CoursInline(admin.TabularInline):
    model = Cours
    extra = 0
    readonly_fields = ['date_publication']


class QuizInline(admin.TabularInline):
    model = Quiz
    extra = 0


class ChapitreInline(admin.TabularInline):
    model = Chapitre
    extra = 1

@admin.register(Cours)
class CoursAdmin(admin.ModelAdmin):
    list_display = ['titre', 'niveau', 'enseignant', 'date_publication', 'image']
    list_filter = ['niveau', 'date_publication']
    search_fields = ['titre', 'description', 'objectif']
    readonly_fields = ['date_publication']
    inlines = [QuizInline, ChapitreInline]


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['titre', 'cours', 'duree', 'note_max']
    list_filter = ['cours']
    search_fields = ['titre']


@admin.register(Inscription)
class InscriptionAdmin(admin.ModelAdmin):
    list_display = ['etudiant', 'date_inscription', 'statut']       # ← corrigé
    list_filter = ['statut', 'date_inscription']                     # ← corrigé
    search_fields = ['etudiant__nom', 'etudiant__prenom', 'etudiant__email']
    readonly_fields = ['date_inscription']                           # ← corrigé


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ['etudiant', 'montant', 'date_paiement', 'moyen_paiement']
    list_filter = ['moyen_paiement', 'date_paiement']
    search_fields = ['etudiant__nom', 'etudiant__prenom', 'etudiant__email']
    readonly_fields = ['date_paiement']


@admin.register(Chapitre)
class ChapitreAdmin(admin.ModelAdmin):
    list_display = ['titre', 'cours', 'est_premium', 'prix', 'ordre']
    list_filter = ['cours', 'est_premium']
    search_fields = ['titre', 'description']

@admin.register(ChapitreDebloque)
class ChapitreDebloqueAdmin(admin.ModelAdmin):
    list_display = ['etudiant', 'chapitre', 'date_deblocage']
    list_filter = ['date_deblocage']

@admin.register(TransactionSimulee)
class TransactionSimuleeAdmin(admin.ModelAdmin):
    list_display = ['etudiant', 'type_transaction', 'montant', 'date_transaction']
    list_filter = ['type_transaction', 'date_transaction']

admin.site.register(User, CustomUserAdmin)