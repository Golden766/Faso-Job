# Plan de développement

## Objectif

Mettre en place une application Django pour la plateforme d'offres d'emploi, avec un développement progressif, sécurisé et conforme aux règles métier du projet.

## Étapes principales

1. Préparer Windows avec Python, VS Code et Git.
2. Créer le projet Django et vérifier qu'il fonctionne en local.
3. Construire les premières pages avec des données fictives.
4. Définir les modèles PostgreSQL et les migrations.
5. Développer le catalogue public, les filtres et les fiches d'offres.
6. Configurer l'administration, les permissions et le processus de vérification des offres.
7. Tester, sécuriser et préparer le déploiement sur le futur hébergement.

## Développement technique recommandé

- Créer le projet Django et valider le démarrage local.
- Configurer les modèles et les migrations dès les premiers blocs fonctionnels.
- Développer les pages avec les templates Django, sans créer de couche API séparée inutile.
- Construire l'administration avec Django Admin comme base, puis l'adapter aux besoins éditoriaux.
- Sécuriser les accès, les données et les variables d'environnement avant le lancement.

## Règles à retenir

- Langage principal : Python.
- Framework web : Django.
- Interface : HTML, CSS et templates Django ; JavaScript uniquement si nécessaire.
- Base de données : PostgreSQL, en local au départ.
- Administration : Django Admin comme base de travail, ensuite personnalisation éditeur.
- Hébergement : aucune souscription avant la préparation du lancement.
- Supabase : option de base PostgreSQL distante pour les tests, avec sauvegardes indépendantes.
- DigitalOcean : option de VPS à comparer au moment du déploiement.
- Sécurité : secrets dans des variables d'environnement, contrôles côté serveur, validation des données et sauvegardes.
- Méthode de travail : une tâche à la fois, tests avant validation, explications en français simple.

## Ordre de développement retenu

1. Préparer Windows avec Python, VS Code et Git.
2. Créer un projet Django et vérifier qu'il fonctionne en local.
3. Construire les premières pages avec des données fictives.
4. Définir les modèles PostgreSQL et les migrations.
5. Développer le catalogue public, les filtres et les fiches d'offres.
6. Configurer l'administration, les permissions et le processus de vérification des offres.
7. Tester, sécuriser et préparer le déploiement sur le futur hébergement.

La décision est donc prise : nous partons sur Django, sans Next.js ni FastAPI.
