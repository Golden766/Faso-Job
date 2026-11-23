# Architecture technique ? plateforme d'opportunit?s professionnelles

**Version :** 0.2 ? orientation Django retenue  
**Date :** 20 octobre 2026  
**Statut :** valid? pour la pr?paration et le d?veloppement Django  
**D?pendances :** specification generale v0.1, architecture fonctionnelle v0.1, modele conceptuel de donnees v0.1, parcours utilisateurs v0.1, specification des ecrans v0.3 et guide visuel v0.2.

## 1. Objectif

D?finir une architecture simple et robuste pour le d?veloppement progressif de la plateforme, en privil?giant Django comme framework principal et les templates Django pour l'interface. L'objectif est d'?viter la complexit? inutile, de s?curiser les acc?s et de garantir des donn?es fiables sur les offres, leur v?rification et leur publication.

## 2. D?cisions retenues

| Couche | Choix retenu | Raison |
|---|---|---|
| Langage principal | Python | Compatible avec les outils de d?veloppement, les tests et le d?ploiement web. |
| Framework web | Django | Framework complet, stable et bien adapt? ? un monolithe modulaire. |
| Interface | HTML, CSS et templates Django | Rendu serveur simple, maintenable et adapt? ? la plateforme. |
| JavaScript | Seulement si n?cessaire pour des interactions tr?s limit?es | ?vite le surd?veloppement front-end inutile. |
| Donn?es | PostgreSQL en local, puis h?bergement/option distante si besoin | Base relationnelle adapt?e aux offres, statuts, signalements et mod?ration. |
| Administration | Django Admin comme base de travail | Rapidement exploitable pour g?rer les offres et les permissions. |
| S?curit? | Variables d'environnement, validation des donn?es, permissions c?t? serveur, sauvegardes | Protecte le site et les donn?es ?ditoriales. |
| H?bergement | ? choisir au moment du d?ploiement, sans souscription avant pr?paration | Permet de comparer les options en fonction du besoin r?el. |
| Supabase | Option de base PostgreSQL distante pour les tests | Utile pour des tests externes avec sauvegardes s?par?es. |
| DigitalOcean | Option VPS ? comparer au moment du d?ploiement | ? ?valuer selon le budget et la charge attendue. |
| Tests | Tests cibl?s, validation Django, v?rification des r?gles m?tier | Garantit la fiabilit? avant validation. |
| D?p?t | Git + d?p?t GitHub/GitLab priv? | Historique, revue et retour en arri?re. |

## 3. Architecture d'ensemble

```text
Navigateur
   ?
   ??? Pages publiques : accueil, recherche, catalogue, fiche d'offre
   ??? Espace admin : connexion, offres, soumissions, signalements, statistiques
                 ?
                 ?
          Application Django
          ??? URLconf et vues
          ??? Templates HTML/CSS
          ??? Mod?les et migrations PostgreSQL
          ??? Forms et validation des donn?es
          ??? Django Admin
          ??? S?curit?, permissions et sessions
                 ?
                 ?
            PostgreSQL
            ??? Offres et cat?gories
            ??? Sources et liens source
            ??? Contr?les et historique de statut
            ??? Soumissions en attente
            ??? Signalements
            ??? Utilisateurs administrateurs
            ??? Donn?es ?ditoriales et sauvegardes
```

### Principe cl? : monolithe modulaire

Les pages, vues et r?gles m?tier restent dans une application Django organis?e par domaine. Il n'est pas n?cessaire de d?marrer avec des microservices, une API s?par?e, des files de messages, Redis ou une base vectorielle, sauf si un besoin fonctionnel r?el le justifie.

Les fronti?res sont fonctionnelles, pas des services ind?pendants. On pourra introduire une s?paration uniquement si la complexit? technique le n?cessite.

## 4. Rendu des pages

- Les pages publiques d'offres et de cat?gories sont rendues via les vues Django et les templates, avec un HTML clair et un CSS structur?.
- Les fichiers statiques CSS sont s?par?s pour garder un design coh?rent et facile ? maintenir.
- Les fiches d'offres re?oivent une URL stable, un titre et une description adapt?s, ainsi que les liens de candidature r?ellement disponibles.
- Les filtres importants sont conserv?s dans l'URL pour rester partageables et recharg?s correctement.
- Les pages d'offres ferm?es ne doivent pas ?tre pr?sent?es comme actives.
- Les informations absentes doivent rester absentes ; l'interface ne doit pas inventer de donn?es.

## 5. Organisation recommand?e du d?p?t

```text
.
??? manage.py
??? requirements.txt
??? .env
??? .gitignore
??? plateforme_offres/
?   ??? __init__.py
?   ??? settings.py
?   ??? urls.py
?   ??? wsgi.py
?   ??? asgi.py
??? apps/
?   ??? offres/
?   ?   ??? models.py
?   ?   ??? views.py
?   ?   ??? urls.py
?   ?   ??? admin.py
?   ?   ??? templates/
?   ?   ??? static/
?   ??? comptes/
?   ??? publications/
?   ??? signalements/
?   ??? core/
??? templates/
?   ??? base.html
?   ??? accueil.html
?   ??? catalogue.html
?   ??? fiche_offre.html
??? static/
?   ??? css/
?   ??? js/
?   ??? images/
??? media/
??? docs/
??? tests/
??? backups/
```

Ne pas cr?er tous les fichiers vides d'un coup. Cr?er chaque dossier uniquement lorsque la fonctionnalit? correspondante entre dans le plan de r?alisation.

## 6. Authentification et s?curit?

### Espace d'administration

- D?sactiver l'inscription publique des comptes d'administration.
- Cr?er les comptes d'administration de mani?re contr?l?e.
- Exiger une session valide sur toutes les routes d'administration.
- V?rifier les permissions c?t? serveur ; masquer un lien n'est pas une protection.
- Utiliser les permissions Django et les groupes utiles pour les r?les ?ditoriaux.
- Ne jamais exposer les secrets dans les fichiers versionn?s ni dans les templates.

### Formulaires publics

- Valider les champs c?t? serveur avec Django forms et les contr?les de mod?le.
- Toute soumission externe est enregistr?e comme en attente de validation : un visiteur ne peut pas directement produire un statut `published`, `verified` ou `closed`.
- Ajouter une protection simple anti-spam si n?cessaire : honeypot, d?lai ou validation minimale.
- Conserver l'historique des changements importants ? travers les mod?les et l'administration.

## 7. D?ploiement et environnement

- Pr?parer une configuration locale avec Python, venv et PostgreSQL.
- Garder un `.env` local hors du d?p?t pour les secrets.
- Pr?parer les variables de production et la configuration Django de mani?re s?par?e.
- Pr?voir l'utilisation de PostgreSQL local au d?part, puis ?ventuellement un h?bergement distant avec sauvegardes distinctes.
- ?valuer Supabase ou un VPS DigitalOcean selon le besoin r?el au moment du lancement.
- Ne pas souscrire ? un h?bergement avant la pr?paration du lancement et la validation technique.

## 8. Crit?res d'acceptation

- L'application Django d?marre localement sans erreur.
- Les mod?les PostgreSQL correspondent bien aux r?gles m?tier et ? l'administration.
- Les pages publiques sont rendues par les templates Django, sans API s?par?e inutile.
- Les permissions admin sont conformes et les acc?s non autoris?s sont bloqu?s.
- Le catalogue ne publie pas d'offres non v?rifi?es ni d'informations invent?es.
- Les sauvegardes et la s?curit? des donn?es sont pr?vues avant le lancement.

## 9. R?f?rences utiles

- Django ? site officiel : https://www.djangoproject.com/
- Django ? documentation des models et migrations : https://docs.djangoproject.com/en/stable/topics/db/models/
- Django Admin : https://docs.djangoproject.com/en/stable/ref/contrib/admin/
- PostgreSQL : https://www.postgresql.org/
- Python venv : https://docs.python.org/fr/3/library/venv.html
