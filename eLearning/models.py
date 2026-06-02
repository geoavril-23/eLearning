import os
from django.db import models
# Commentaire pour forcer la detection des changements
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone

class UserManager(BaseUserManager):

    def create_user(self, email, nom, prenom, password=None, **extra_fields):
        if not email:
            raise ValueError('L\'email est obligatoire')
        email = self.normalize_email(email)
        user = self.model(email=email, nom=nom, prenom=prenom, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, nom, prenom, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'administrateur')
        return self.create_user(email, nom, prenom, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):

    ROLE_CHOICES = [
        ('etudiant', 'Étudiant'),
        ('enseignant', 'Enseignant'),
        ('administrateur', 'Administrateur'),
    ]

    objects = UserManager()
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    age = models.IntegerField(null=True, blank=True)  # ← null=True pour ne pas bloquer
    email = models.EmailField(max_length=300, unique=True)
    adresse = models.CharField(max_length=300, blank=True)
    role = models.CharField(max_length=100, choices=ROLE_CHOICES, default='etudiant')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    theme = models.CharField(max_length=50, default='light')
    photo_profil = models.ImageField(upload_to='photos_profil/', null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nom', 'prenom']

    def __str__(self):
        return f"{self.nom} {self.prenom} ({self.role})"

    # Propriétés utiles pour les templates et vues
    @property
    def is_etudiant(self):
        return self.role == 'etudiant'

    @property
    def is_enseignant(self):
        return self.role == 'enseignant'

    @property
    def is_administrateur(self):
        return self.role == 'administrateur'


class Etudiant(User):
    niveau = models.CharField(max_length=50, blank=True)
    etablissement = models.CharField(max_length=100, blank=True)
    solde = models.DecimalField(max_digits=10, decimal_places=2, default=50000.00)

    class Meta:
        verbose_name = "Étudiant"


class Enseignant(User):
    specialite = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Enseignant"


class Administrateur(User):

    class Meta:
        verbose_name = "Administrateur"


class Categorie(models.Model):
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='sous_categories'
    )

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"

    def __str__(self):
        if self.parent:
            return f"{self.parent.nom} > {self.nom}"
        return self.nom

MATIERES_CHOICES = [
    # Informatique Fondamentale
    ('ALGO', 'Algorithmique et Structures de Données'),
    ('ARCHI', 'Architecture des Ordinateurs et Systèmes d\'Exploitation (Linux/Windows)'),
    
    # Programmation
    ('POO', 'Programmation Orientée Objet (Java, C++, C#)'),
    
    # Développement Web & Mobile
    ('WEB_FRONT', 'Développement Web Frontend (HTML, CSS, JavaScript, React/Angular)'),
    ('WEB_BACK', 'Développement Web Backend (PHP/Symfony, Python/Django, Node.js)'),
    ('MOBILE', 'Développement Mobile (Android/Kotlin, iOS/Swift, Flutter)'),
    
    # Sécurité
    ('SECURE_SYS', 'Sécurité des Systèmes et des Réseaux'),
    ('CRYPTO', 'Cryptographie et Authentification'),
    
    # Mathématiques
    ('MATH_DISC', 'Mathématiques Discrètes et Logique'),
    ('ALGEBRE', 'Algèbre Linéaire et Analyse'),
    ('PROBA', 'Probabilités et Statistiques'),
]


class Cours(models.Model):
    titre = models.CharField(max_length=100)
    niveau = models.CharField(max_length=50)
    objectif = models.TextField()
    description = models.TextField()
    date_publication = models.DateField()
    ressource = models.FileField(upload_to='ressources/', null=True, blank=True)
    categorie = models.ForeignKey(
        Categorie, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='cours'
    )

    enseignant = models.ForeignKey(
        Enseignant,
        on_delete=models.CASCADE,
        related_name='cours'
    )
    est_premium = models.BooleanField(default=False)
    prix = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    lien_youtube = models.URLField(blank=True, null=True)
    image = models.ImageField(upload_to='cours_images/', null=True, blank=True)

    def __str__(self):
        return self.titre



    @property
    def get_extension(self):
        if self.ressource:
            return os.path.splitext(self.ressource.name)[1].lower().replace('.', '')
        return ""

    @property
    def get_file_icon(self):
        ext = self.get_extension
        if ext == 'pdf':
            return 'fa-file-pdf text-danger'
        elif ext in ['doc', 'docx']:
            return 'fa-file-word text-primary'
        elif ext in ['xls', 'xlsx']:
            return 'fa-file-excel text-success'
        elif ext in ['ppt', 'pptx']:
            return 'fa-file-powerpoint text-warning'
        elif ext in ['jpg', 'jpeg', 'png', 'gif']:
            return 'fa-file-image text-info'
        elif ext in ['mp4', 'avi', 'mov', 'mkv']:
            return 'fa-file-video text-secondary'
        elif ext in ['zip', 'rar', '7z']:
            return 'fa-file-archive text-muted'
        elif ext == 'txt':
            return 'fa-file-text text-dark'
        else:
            return 'fa-file-download text-primary'

class RessourceCours(models.Model):
    cours = models.ForeignKey(Cours, on_delete=models.CASCADE, related_name='ressources_annexes')
    titre = models.CharField(max_length=200)
    fichier = models.FileField(upload_to='ressources_cours/')
    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ressource du Cours"
        verbose_name_plural = "Ressources du Cours"

    def __str__(self):
        return f"{self.cours.titre} - {self.titre}"


class Module(models.Model):
    cours = models.ForeignKey(
        Cours,
        on_delete=models.CASCADE,
        related_name='modules'
    )
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    ordre = models.PositiveIntegerField(default=0)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ordre']
        verbose_name = "Module"
        verbose_name_plural = "Modules"

    def __str__(self):
        return f"{self.cours.titre} — Module {self.ordre}: {self.titre}"


class Chapitre(models.Model):
    cours = models.ForeignKey(Cours, on_delete=models.CASCADE, related_name='chapitres')
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='chapitres',
        null=True,
        blank=True
    )
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    contenu = models.TextField(blank=True, null=True)
    est_premium = models.BooleanField(default=False)
    prix = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    ressource = models.FileField(upload_to='chapitres_ressources/', null=True, blank=True)
    lien_youtube = models.URLField(max_length=255, null=True, blank=True)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordre']
        verbose_name = "Chapitre"
        verbose_name_plural = "Chapitres"

    def __str__(self):
        return f"{self.cours.titre} - {self.titre}"


class RessourceChapitre(models.Model):
    chapitre = models.ForeignKey(
        Chapitre,
        on_delete=models.CASCADE,
        related_name='ressources'
    )
    titre = models.CharField(max_length=200)
    fichier = models.FileField(upload_to='ressources_chapitres/')
    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ressource du Chapitre"
        verbose_name_plural = "Ressources du Chapitre"

    def __str__(self):
        return f"{self.chapitre.titre} - {self.titre}"

    @property
    def get_extension(self):
        if self.fichier:
            return os.path.splitext(self.fichier.name)[1].lower().replace('.', '')
        return ""

    @property
    def get_file_icon(self):
        ext = self.get_extension
        if ext == 'pdf':
            return 'fa-file-pdf text-danger'
        elif ext in ['doc', 'docx']:
            return 'fa-file-word text-primary'
        elif ext in ['xls', 'xlsx']:
            return 'fa-file-excel text-success'
        elif ext in ['ppt', 'pptx']:
            return 'fa-file-powerpoint text-warning'
        elif ext in ['jpg', 'jpeg', 'png', 'gif']:
            return 'fa-file-image text-info'
        elif ext in ['mp4', 'avi', 'mov', 'mkv']:
            return 'fa-file-video text-secondary'
        elif ext in ['zip', 'rar', '7z']:
            return 'fa-file-archive text-muted'
        elif ext == 'txt':
            return 'fa-file-text text-dark'
        else:
            return 'fa-file-download text-primary'




class ChapitreDebloque(models.Model):
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE, related_name='chapitres_debloques')
    chapitre = models.ForeignKey(Chapitre, on_delete=models.CASCADE, related_name='deblocages')
    date_deblocage = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('etudiant', 'chapitre')
        verbose_name = "Chapitre Débloqué"
        verbose_name_plural = "Chapitres Débloqués"

    def __str__(self):
        return f"{self.etudiant} - {self.chapitre.titre}"


class Inscription(models.Model):
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('validee', 'Validée'),
        ('annulee', 'Annulée'),
        ('terminee', 'Terminée'),
    ]
    date_inscription = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=100, choices=STATUT_CHOICES, default='en_attente')
    etudiant = models.ForeignKey(
        Etudiant,
        on_delete=models.CASCADE,
        related_name='inscriptions'
    )
    cours = models.ForeignKey(
        Cours,
        on_delete=models.CASCADE,
        related_name='inscriptions'
    )
    est_paye = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.etudiant} → {self.cours}"


class Quiz(models.Model):
    TYPE_CORRECTION_CHOICES = [
        ('manuelle', 'Correction Manuelle'),
        ('auto', 'Correction Automatique par IA'),
    ]
    titre = models.CharField(max_length=100)
    duree = models.CharField(max_length=20)
    note_max = models.FloatField()
    type_correction = models.CharField(max_length=20, choices=TYPE_CORRECTION_CHOICES, default='manuelle')
    cours = models.ForeignKey(
        Cours,
        on_delete=models.CASCADE,
        related_name='quiz'
    )
    fichier_quiz = models.FileField(upload_to='quizzes/', null=True, blank=True)

    def __str__(self):
        return self.titre


class SoumissionQuiz(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='soumissions')
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE, related_name='soumissions')
    date_soumission = models.DateTimeField(auto_now_add=True)
    
    # Travail de l'étudiant
    fichier_reponse = models.FileField(upload_to='reponses_quizzes/', null=True, blank=True)
    reponses_qcm = models.TextField(null=True, blank=True) # Stocké sous forme de chaîne JSON manuellement si DB ne supporte pas JSONField
    
    # Correction
    est_corrige = models.BooleanField(default=False)
    note_obtenue = models.FloatField(null=True, blank=True)
    commentaires = models.TextField(null=True, blank=True)
    corrige_par_ia = models.BooleanField(default=False)

    def __str__(self):
        return f"Soumission de {self.etudiant} - {self.quiz.titre}"



class Paiement(models.Model):
    montant = models.FloatField()
    date_paiement = models.DateField()
    moyen_paiement = models.CharField(max_length=50)
    etudiant = models.ForeignKey(
        Etudiant,
        on_delete=models.CASCADE,
        related_name='paiements'
    )
    inscription = models.OneToOneField(Inscription, on_delete=models.CASCADE, null=True, blank=True, related_name='paiement_detail')

    def __str__(self):
        return f"{self.etudiant} - {self.montant} FCFA"


class SessionVisio(models.Model):
    titre = models.CharField(max_length=200)
    date_debut = models.DateTimeField()
    duree = models.IntegerField(default=60, help_text="Durée en minutes")
    lien_reunion = models.URLField(max_length=500)
    enseignant = models.ForeignKey(Enseignant, on_delete=models.CASCADE, related_name='sessions_visio')
    cours = models.ForeignKey(Cours, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions_visio')
    date_creation = models.DateTimeField(auto_now_add=True)
    est_termine = models.BooleanField(default=False)

    class Meta:
        ordering = ['-date_debut']

    def __str__(self):
        return self.titre


from django.core.validators import MinValueValidator

class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    texte = models.TextField(blank=True, null=True)
    media = models.FileField(upload_to='quiz_media/', null=True, blank=True)
    points = models.FloatField(default=1.0, validators=[MinValueValidator(0.0)])
    est_ouverte = models.BooleanField(default=False)

    def __str__(self):
        return self.texte


class Choix(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choix')
    texte = models.CharField(max_length=200)
    est_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.texte


class Conversation(models.Model):
    participants = models.ManyToManyField(User, related_name='conversations')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Conversation {self.id}"



class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    expediteur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='messages_envoyes')
    contenu = models.TextField()
    date_envoi = models.DateTimeField(auto_now_add=True)
    lu = models.BooleanField(default=False)

    class Meta:
        ordering = ['date_envoi']

    def __str__(self):
        return f"Message de {self.expediteur.nom} {self.expediteur.prenom}"


class Notification(models.Model):

    TYPE_CHOICES = [
        ('nouveau_cours', 'Nouveau cours dans votre domaine'),
        ('nouvelle_ressource', 'Nouvelle ressource sur votre cours'),
    ]
    destinataire = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    type_notif = models.CharField(max_length=50, choices=TYPE_CHOICES, default='nouveau_cours')
    cours = models.ForeignKey(
        Cours,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    lue = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_creation']
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"Notif [{self.type_notif}] → {self.destinataire.email} : {self.cours.titre}"


class Livre(models.Model):
    titre = models.CharField(max_length=200)
    auteur = models.CharField(max_length=100)
    prix = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    description = models.TextField()
    lien_externe = models.URLField(blank=True, null=True)
    couverture = models.ImageField(upload_to='livres_couvertures/', null=True, blank=True)
    est_premium = models.BooleanField(default=True)
    date_ajout = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titre


class AchatLivre(models.Model):
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE, related_name='livres_achetes')
    livre = models.ForeignKey(Livre, on_delete=models.CASCADE, related_name='acheteurs')
    date_achat = models.DateTimeField(auto_now_add=True)
    montant_paye = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.etudiant} a acheté {self.livre}"


class TransactionSimulee(models.Model):
    TYPE_CHOICES = [
        ('achat_cours', 'Achat de Cours'),
        ('achat_livre', 'Achat de Livre'),
        ('achat_chapitre', 'Achat de Chapitre'),
        ('recharge', 'Recharge de Compte'),
    ]
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE, related_name='transactions_simulees')
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    type_transaction = models.CharField(max_length=20, choices=TYPE_CHOICES)
    date_transaction = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.type_transaction} - {self.montant} FCFA"


class LogActivite(models.Model):
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='logs_activite')
    action = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    date_action = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_action']

    def __str__(self):
        return f"{self.utilisateur} - {self.action} ({self.ip_address})"
