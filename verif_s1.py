import requests, re
BASE = "http://127.0.0.1:8000"
s = requests.Session()
s.get(BASE + "/dashboard/admin/login/")
t = s.cookies.get("csrftoken", "")
s.post(BASE + "/dashboard/admin/login/", data={
    "email": "awessogeorges01@gmail.com", "password": "georges230407", "csrfmiddlewaretoken": t
}, headers={"Referer": BASE + "/dashboard/admin/login/"})

r = s.get(BASE + "/dashboard/etudiant/cours/10/voir/", allow_redirects=True)
print("URL finale:", r.url)
m = re.search(r'<h1 class="chapitre-title">(.*?)</h1>', r.text)
print("Titre chapitre:", m.group(1) if m else "?")
mc = re.search(r'<div class="chapitre-content">(.*?)</div>\s*<div class="navigation">', r.text, re.DOTALL)
if mc:
    print("Longueur HTML contenu:", len(mc.group(1)))
    print("Contient 'Cryptologie':", "Cryptologie" in mc.group(1))
    print("Contient 'One-Time Pad':", "One-Time Pad" in mc.group(1))
    print("Contient 'En resume'/'resume':", "sum" in mc.group(1))
    print("Toujours le texte de test ?", "Contenu modifie via formulaire" in mc.group(1))
