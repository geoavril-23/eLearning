import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ppe301.settings')
django.setup()

from eLearning.models import User

u = User.objects.get(email='admin@example.com')
u.set_password('admin123')
u.save()
print('Password reset to: admin123')

