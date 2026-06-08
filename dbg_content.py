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
# Titre du chapitre affiche
m = re.search(r'<h1 class="chapitre-title">(.*?)</h1>', r.text)
print("Titre chapitre:", m.group(1) if m else "?")
# Contenu affiche
mc = re.search(r'<div class="chapitre-content">(.*?)</div>\s*<div class="navigation">', r.text, re.DOTALL)
if mc:
    txt = re.sub(r'<[^>]+>', '', mc.group(1)).strip()
    print("Contenu (texte brut):", repr(txt[:200]))
    print("Longueur contenu:", len(mc.group(1)))
