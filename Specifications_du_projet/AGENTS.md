# Règles de travail pour l'agent IA

Le projet est construit autour de Python et de Django. L'agent doit utiliser Django comme framework web principal, avec les templates Django, les fichiers CSS, les vues Django et les modèles Django.

## Stack technique retenue

- Langage principal : Python.
- Framework web : Django, avec une version stable prise en charge.
- Interface : HTML, CSS et templates Django ; JavaScript uniquement lorsque cela est strictement nécessaire.
- Base de données : PostgreSQL, en local au départ.
- Administration : utiliser Django Admin comme base de travail, puis l'adapter aux besoins éditoriaux de la plateforme.
- Hébergement : aucune souscription avant la préparation au lancement.
- Supabase : option de base PostgreSQL distante pour les tests, avec sauvegardes indépendantes.
- DigitalOcean : option de VPS à comparer au moment du déploiement.
- Sécurité : secrets dans des variables d'environnement, contrôle des accès côté serveur, validation des données et sauvegardes.
- Méthode de travail : une tâche à la fois, tests avant validation, explications en français simple.

## Consignes de conception

- Utiliser Django comme référence principale pour le développement web du projet.
- Travailler avec les templates Django, les fichiers statiques CSS et les vues/modèles Django.
- Ne pas créer une API séparée si le besoin n'est pas démontré et validé.
- Ne pas installer un framework frontend séparé (par exemple Next.js, React, Vue ou autre) sans justification claire et validation préalable.
- Préserver la cohérence du projet monolithique Django, sans introduire de couches techniques superflues.
- Développer le catalogue public, les filtres, les fiches d'offres et l'administration en s'appuyant sur les mécanismes Django natifs.

## Règles métier à conserver

Les règles métier déjà établies restent inchangées :

- provenance des offres ;
- vérification des sources ;
- statut de publication ;
- disponibilité doivent rester distincts.

L'agent ne doit pas supposer qu'une annonce est publiée, vérifiée ou disponible uniquement parce qu'elle a été soumise. Les informations absentes doivent être validées ou clairement indiquées, sans inventaire de données.

## Bonnes pratiques attendues

- Lire les consignes du projet avant de modifier du code.
- Vérifier l'environnement local avant de créer l'application.
- Construire progressivement : projet Django, modèles, migrations, vues, templates, administration, sécurité et préparation au déploiement.
- Expliquer les décisions en français simple et rester concentré sur une tâche à la fois.
- Tester le comportement local avant de considérer une étape comme validée.

La décision est donc prise : nous partons sur Django, sans Next.js ni FastAPI.
