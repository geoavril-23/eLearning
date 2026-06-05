import re

with open(r'd:/ppe301/eLearning/templates/admin/profil.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix multiline {{ p.pourcentage\n}} patterns
before = len(content)
content = re.sub(r'\{\{\s*p\.pourcentage\s*\}\}', '{{ p.pourcentage }}', content)
after = len(content)

print(f"Replacements done: {before != after}")

# Also fix any other multiline template vars in the file  
content = re.sub(r'\{\{\s*p\.css_class\s*\}\}', '{{ p.css_class }}', content)
content = re.sub(r'\{\{\s*p\.cours\.titre\s*\}\}', '{{ p.cours.titre }}', content)

with open(r'd:/ppe301/eLearning/templates/admin/profil.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done - profil.html updated")
