import requests, re, django, os
os.environ["DJANGO_SETTINGS_MODULE"] = "ppe301.settings"
django.setup()
from eLearning.models import Cours, Quiz

c = Cours.objects.get(id=10)
qs = list(c.quiz.all())
print("Quiz du cours 10:", [(q.id, q.titre) for q in qs])

BASE = "http://127.0.0.1:8000"
s = requests.Session()
s.get(BASE + "/dashboard/admin/login/")
t = s.cookies.get("csrftoken", "")
s.post(BASE + "/dashboard/admin/login/", data={
    "email": "awessogeorges01@gmail.com", "password": "georges230407", "csrfmiddlewaretoken": t
}, headers={"Referer": BASE + "/dashboard/admin/login/"})
r = s.get(BASE + "/dashboard/etudiant/cours/10/voir/?chapitre=10")
print("status:", r.status_code)
# Section Quiz dans la TOC ?
print("Section 'Quiz' dans TOC:", ">Quiz</h3>" in r.text or "Quiz</h3>" in r.text)
print("Lien detail_quiz present:", "/dashboard/etudiant/quiz/" in r.text)
