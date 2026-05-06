import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ppe301.settings')
django.setup()

from eLearning.models import User

# Check existing users
users = User.objects.all()
print(f"Total users: {users.count()}")
for u in users:
    print(f"  - Email: {u.email}, is_staff: {u.is_staff}, is_superuser: {u.is_superuser}")

# Create admin if not exists
admin_email = 'admin@example.com'
if not User.objects.filter(email=admin_email).exists():
    print(f"\nCreating admin user: {admin_email}")
    admin = User.objects.create_superuser(
        email=admin_email,
        nom='Admin',
        prenom='Super',
        password='admin123'
    )
    print(f"Admin created successfully!")
else:
    print(f"\nAdmin user {admin_email} already exists")

