# -*- coding: utf-8 -*-
import django, os
os.environ["DJANGO_SETTINGS_MODULE"] = "ppe301.settings"
django.setup()
from eLearning.models import Chapitre

contenu = """
<h2>Découvrez la cryptographie</h2>
<p>Bienvenue dans ce cours sur la cryptographie ! Cette première partie couvre la cryptographie, son vocabulaire et ses origines, puis le chiffrement symétrique, la génération de nombres aléatoires, et le chiffrement de disque dur avec VeraCrypt.</p>
<p>La cryptographie est essentielle à la sécurité informatique. Sans elle, les attaquants peuvent intercepter les communications électroniques, lire les fichiers d'un disque dur, ou utiliser frauduleusement des cartes de crédit.</p>
<p>Pour les étudiants du parcours RSSI, vous devrez sélectionner et définir des systèmes cryptographiques pour garantir la sécurité du système d'information de votre organisation : chiffrement des disques durs, authentification par infrastructure de clés publiques, contrôle d'intégrité des communications.</p>

<h3>Exemples d'implémentations défaillantes</h3>
<p>En septembre 2018, des chercheurs belges ont démontré qu'il était possible d'ouvrir et de démarrer les voitures Tesla en clonant la clé électronique à distance. Tesla a corrigé ce problème avec des mises à jour et une authentification par code PIN.</p>
<p>En mai 2018, Twitter a demandé à 300 millions d'utilisateurs de changer leur mot de passe après la découverte d'un stockage en clair dans les journaux de connexion.</p>

<h2>Cryptologie, cryptographie, cryptanalyse : les différences</h2>
<p><strong>Cryptologie</strong> : science du secret (du grec « kruptos » signifiant « caché »), composée de deux disciplines :</p>
<ul>
<li><strong>Cryptographie</strong> : ensemble des méthodes de protection d'une information, garantissant la confidentialité lors de communications ou de stockage via le chiffrement, mais aussi l'intégrité et l'authentification.</li>
<li><strong>Cryptanalyse</strong> : méthodes utilisées pour analyser les messages chiffrés et « casser » la protection cryptographique, retrouvant l'information sans connaître la clé.</li>
</ul>
<p>La cryptographie repose sur des propriétés mathématiques, mais aucune connaissance mathématique particulière n'est requise pour ce cours.</p>

<h2>Vocabulaire de la cryptographie</h2>
<h3>Le chiffrement</h3>
<p>Le <strong>chiffrement</strong> transforme une information en clair en information chiffrée, incompréhensible mais déchiffrable avec une clé. Un <strong>système de chiffrement</strong> (ou cryptosystème, ou chiffre) comprend des algorithmes de chiffrement/déchiffrement et une clé de chiffrement.</p>
<h3>Message en clair</h3>
<p>Un <strong>message en clair</strong> (ou texte clair) est une information non protégée et compréhensible par tous.</p>
<h3>Texte chiffré</h3>
<p>Un <strong>texte chiffré</strong> est une information incompréhensible sans la clé de déchiffrement. Il contient toutes les informations du texte clair pour qui possède la clé, mais aucune pour qui ne la possède pas. C'est la confidentialité d'une information chiffrée.</p>
<h3>Algorithme de chiffrement</h3>
<p>Un <strong>algorithme de chiffrement</strong> prend en entrée le texte clair et la clé, transforme le texte par opérations, et fournit un texte chiffré. L'algorithme de déchiffrement est la fonction inverse.</p>
<h3>Clé de chiffrement</h3>
<p>La <strong>clé de chiffrement</strong> (ou cryptovariable) permet de transformer un texte clair en texte chiffré. L'<strong>espace de clé</strong> est l'ensemble des valeurs possibles de la clé. Lorsque les clés de chiffrement et de déchiffrement sont identiques, on parle de <strong>clé secrète</strong> et de <strong>chiffrement symétrique</strong> (sujet de cette première partie).</p>
<h3>Conventions terminologiques</h3>
<p>En cryptographie, <strong>Alice</strong> représente l'expéditrice et <strong>Bob</strong> le destinataire d'un message. Les termes « crypter », « encrypter » et « messages cryptés » sont des anglicismes. En français correct : chiffrer, déchiffrer, système de chiffrement.</p>

<h2>Origines de la cryptographie</h2>
<h3>Le chiffre de César</h3>
<p>La plus célèbre méthode antique est le <strong>chiffre de César</strong>, ou chiffrement par décalage, décalant chaque lettre d'une distance fixe dans l'alphabet. Exemple : avec une distance de 3, « ATTAQUEZ A L AUBE » devient « DWWDTXHC D O DXEH ».</p>
<p><strong>Formules</strong> :</p>
<ul>
<li>Chiffrement : Texte chiffré = (Texte clair + Clé) mod 26</li>
<li>Déchiffrement : Texte clair = (Texte chiffré - Clé) mod 26</li>
</ul>
<h3>Attaque par force brute</h3>
<p>Avec seulement 26 valeurs possibles de clé, un adversaire n'a besoin que de 26 essais. Un faible espace de clé rend l'algorithme vulnérable.</p>
<h3>Chiffrement par substitution</h3>
<p>Une généralisation remplace chaque lettre par une autre. Le tableau de substitution sert de clé : il y a 26! (≈ 10²⁷) clés possibles, ce qui rend l'attaque par force brute impossible sans moyens informatiques.</p>
<h3>Analyse fréquentielle</h3>
<p>L'<strong>analyse fréquentielle</strong> casse facilement le chiffrement par substitution. En français, E est la lettre la plus courante, suivie de S. Comme chaque lettre est toujours remplacée par la même, les fréquences sont conservées et permettent de retrouver les correspondances.</p>
<h3>Le chiffre de Vigenère</h3>
<p>Inventé au XVIᵉ siècle, le <strong>chiffre de Vigenère</strong> varie la distance de décalage via une clé-mot. Chaque lettre peut être remplacée différemment selon sa position : l'analyse fréquentielle simple ne fonctionne plus. Il a toutefois été cassé à partir du XVIIIᵉ siècle (méthode de Kasiski). La machine <strong>Enigma</strong> en est un descendant célèbre.</p>

<h2>Principaux fondateurs de la cryptologie</h2>
<p>À la fin du XIXᵉ siècle, Auguste Kerckhoffs énonce les <strong>principes de Kerckhoffs</strong> :</p>
<ul>
<li>La sécurité ne doit pas reposer sur le secret de l'algorithme, mais uniquement sur le fait que l'attaquant ne connaît pas la clé.</li>
<li>Les algorithmes doivent être physiquement ou mathématiquement impossibles à résoudre.</li>
<li>Le système doit être adapté à son usage pratique et la clé facilement modifiable.</li>
</ul>
<p>Claude Shannon, fondateur de la théorie de l'information, a reformulé le principe le plus important : <strong>« l'adversaire connaît le système »</strong>.</p>

<h2>Un algorithme de chiffrement incassable : le One-Time Pad</h2>
<p>En 1917, Vernam invente le <strong>masque jetable</strong> (One-Time Pad), où la clé est aussi longue que le message clair.</p>
<h3>L'opération XOR</h3>
<p>Le chiffrement effectue l'opération <strong>XOR (OU exclusif, ⊕)</strong> entre chaque bit du texte clair et celui de la clé :</p>
<ul>
<li>0 ⊕ 0 = 0</li>
<li>0 ⊕ 1 = 1</li>
<li>1 ⊕ 0 = 1</li>
<li>1 ⊕ 1 = 0</li>
</ul>
<p>Exemple : 1001001110 ⊕ 0010101110 = 1011100000.</p>
<h3>Sécurité inconditionnelle</h3>
<p>Comme la clé n'est jamais répétée, la cryptanalyse fréquentielle est impossible. Shannon a démontré que, correctement utilisé, cet algorithme est <strong>incassable</strong> (perfect secrecy) : même avec une puissance de calcul infinie, on ne peut retrouver le message clair. La clé doit être <strong>aléatoire, aussi longue que le message, et utilisée une seule fois</strong>.</p>
<p><strong>Attention</strong> : réutiliser la même clé compromet la sécurité du système. Ce système a notamment servi pour le téléphone rouge entre la Maison Blanche et le Kremlin.</p>

<h2>En résumé</h2>
<ul>
<li>La cryptographie est essentielle à la sécurité informatique : pas de confidentialité sans cryptographie.</li>
<li>Un système de chiffrement symétrique repose sur un algorithme de chiffrement/déchiffrement et une clé secrète partagée.</li>
<li>La sécurité ne repose pas sur la confidentialité des algorithmes, mais sur le secret de la clé.</li>
<li>Pour être parfaitement secret, un système doit utiliser une clé aléatoire aussi longue que le message, n'être utilisée qu'une seule fois, et le texte chiffré ne doit donner aucune information sur le texte clair.</li>
</ul>
"""

ch = Chapitre.objects.get(id=10)
ch.contenu = contenu.strip()
ch.save(update_fields=["contenu"])
ch.refresh_from_db()
print("Section 1 mise a jour.")
print("Titre:", ch.titre)
print("Longueur contenu:", len(ch.contenu), "caracteres")
