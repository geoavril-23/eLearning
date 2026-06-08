import django, os
os.environ["DJANGO_SETTINGS_MODULE"] = "ppe301.settings"
django.setup()
from eLearning.models import Chapitre

ch = Chapitre.objects.get(id=10)
print("Section 1 titre:", repr(ch.titre))
print("Longueur contenu:", len(ch.contenu or ''), "caracteres")
import re
txt = re.sub(r'<[^>]+>', '', ch.contenu or '')
print("Apercu texte (300 premiers):")
print(txt[:300])
