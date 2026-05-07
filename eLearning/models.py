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
    titre = models.CharField(max_length=100)
    duree = models.CharField(max_length=20)
    note_max = models.FloatField()
    cours = models.ForeignKey(
        Cours,
        on_delete=models.CASCADE,
        related_name='quiz'
    )
    fichier_quiz = models.FileField(upload_to='quizzes/', null=True, blank=True)

    def __str__(self):
        return self.titre


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