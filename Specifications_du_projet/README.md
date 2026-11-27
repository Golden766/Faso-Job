# Plateforme d'opportunités professionnelles

Projet de plateforme web destinée à centraliser des offres d'emploi et d'autres
opportunités professionnelles, d'abord pour le marché burkinabè. Le catalogue
public doit rendre les annonces plus faciles à trouver, comprendre, vérifier et
partager, tout en conservant leur source et leur véritable canal de candidature.

> **État actuel :** préparation du projet autour de Python et Django. Les documents
> de cadrage sont en place et la pile technique retenue est désormais Django avec
> templates Django, CSS, vues et modèles, sans création d'API séparée ni ajout de
> framework frontend sans justification et validation.

## Stack technique retenue

- Langage principal : Python.
- Framework web : Django, version stable prise en charge.
- Interface : HTML, CSS et templates Django ; JavaScript uniquement si nécessaire.
- Base de données : PostgreSQL, en local au départ.
- Administration : Django Admin comme base de travail, puis adaptation éditoriale.
- Hébergement : aucune souscription avant la préparation au lancement.
- Supabase : option de base PostgreSQL distante pour les tests, avec sauvegardes indépendantes.
- DigitalOcean : option de VPS à comparer au moment du déploiement.
- Sécurité : secrets dans des variables d'environnement, contrôle des accès côté serveur, validation des données et sauvegardes.
- Méthode de travail : une tâche à la fois, tests avant validation, explications en français simple.

## Démarrer en local

Prérequis : Python 3.12, Git et VS Code. Depuis la racine du dépôt, dans
PowerShell :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py runserver
```

Pour appliquer les migrations lors d'une première installation :

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

Ouvrir ensuite l'URL locale de Django, généralement :

```text
http://127.0.0.1:8000/
```

Créez un fichier `.env` à la racine pour les variables d'environnement du projet,
par exemple :

```env
SECRET_KEY=votre-cle-secrete
DEBUG=True
DATABASE_URL=postgresql://user:password@localhost:5432/plateforme_offres
```

Ne jamais versionner de secret réel. Les valeurs de production doivent être
conservées hors du dépôt et renseignées dans l'environnement d'hébergement.

### Utiliser Supabase comme base de développement

La configuration Supabase doit être faite après la stabilisation des modèles et
la création de leurs migrations, mais avant la création du superutilisateur ou
de comptes éditoriaux. Ainsi, les comptes seront créés directement dans la base
qui sera utilisée pour les essais.

1. Créer un projet Supabase et récupérer sa chaîne PostgreSQL dans les paramètres
   de connexion du projet.
2. Renseigner dans `.env` `USE_POSTGRES=True` et `DATABASE_URL` avec cette chaîne.
   Garder les secrets uniquement dans `.env` ; ne pas les coller dans le dépôt ni
   dans une conversation.
3. Vérifier la connexion et appliquer le schéma :

```bash
python manage.py check
python manage.py migrate
```

4. Créer le compte administrateur, puis les rôles éditoriaux :

```bash
python manage.py createsuperuser
python manage.py setup_editorial_roles
python manage.py setup_editorial_roles --username NOM_UTILISATEUR --role moderator
```

Les rôles disponibles sont `editor` et `moderator`. Une soumission acceptée
devient une offre « en attente de validation » ; elle n'est pas publiée et sa
source, sa vérification et sa disponibilité restent à confirmer séparément.

Avant de connecter une base distante, faire une sauvegarde indépendante et
vérifier que l'instance Supabase ne contient pas de données à préserver qui
seraient affectées par les migrations.

## Vision du MVP

Le MVP doit permettre de :

- consulter les offres publiées sans créer de compte candidat ;
- rechercher et filtrer les offres actives ;
- consulter une fiche structurée avec sa provenance et ses statuts de contrôle ;
- contacter le recruteur par le canal réellement indiqué (WhatsApp, téléphone,
  email, site externe ou dépôt physique) ;
- partager une offre avec une URL stable ;
- saisir et publier des offres depuis un espace d'administration protégé ;
- recevoir des propositions d'annonces et des signalements depuis les pages
  publiques ;
- examiner chaque proposition ou signalement dans l'administration avant toute
  décision éditoriale.

Les candidatures restent hors plateforme. Une annonce soumise par un tiers ne
doit jamais être publiée automatiquement : son acceptation crée une offre en
attente de vérification. Un signalement ne modifie pas automatiquement le statut
ou la disponibilité d'une offre. « Publiée », « source retrouvée »,
« employeur vérifiée » et « disponibilité confirmée » sont des états distincts.
Les informations absentes d'une annonce ne doivent pas être inventées.

### Hors périmètre initial

Comptes candidats, CVthèque, candidature hébergée, messagerie interne, espace
employeur autonome, publication automatique, paiements, annonces sponsorisées,
scraping automatisé et application mobile native.

## Arborescence cible

La structure ci-dessous est une cible indicative, à créer progressivement au
fil des fonctionnalités.

```text
.
├── README.md
├── .env
├── .gitignore
├── requirements.txt
├── manage.py
├── plateforme_offres/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── offres/
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   ├── templates/
│   │   └── static/
│   ├── comptes/
│   ├── publications/
│   ├── signalements/
│   └── core/
├── templates/
│   ├── base.html
│   ├── accueil.html
│   ├── catalogue.html
│   └── fiche_offre.html
├── static/
│   ├── css/
│   ├── js/
│   └── images/
├── media/
├── docs/
└── tests/
```

L'application reste un monolithe modulaire, organisé par domaine métier et
construit avec les mécanismes natifs de Django.

## Étapes de développement

Chaque étape doit être validée avant de commencer la suivante.

### 1. Préparer l'environnement Windows

- Installer Python, Git et VS Code.
- Créer un environnement virtuel `venv`.
- Vérifier la version de Python et confirmer le fonctionnement de Git.
- Préparer le dépôt local et les dépendances du projet.

**Validation :** environnement fonctionnel, versions confirmées et projet prêt à accueillir Django.

### 2. Créer le projet Django et vérifier le démarrage

- Initialiser le projet Django dans le dossier de travail.
- Configurer les paramètres de base, la base PostgreSQL et les variables d'environnement.
- Vérifier le lancement local sans erreur.
- Créer les applications métier nécessaires et les premiers modules.

**Validation :** application Django démarrable localement avec base PostgreSQL préparée.

### 3. Construire les premières pages

- Créer les pages publiques avec templates Django.
- Ajouter des données fictives pour valider les vues et les layouts.
- Mettre en place le style de base avec HTML/CSS.
- Faire un premier parcours accueil → catalogue → fiche offre.

**Validation :** pages rendues correctement et navigation cohérente.

### 4. Définir les modèles et les migrations

- Modéliser les offres, leurs statuts, leurs sources, leur provenance et leur disponibilité.
- Développer les modèles Django et les migrations PostgreSQL.
- Définir les relations entre offres, soumissions, signalements et administration.
- Vérifier l'intégrité des données.

**Validation :** migrations réexécutables et schéma cohérent avec les règles métier.

### 5. Développer le catalogue public

- Créer les filtres de recherche et les pages de liste.
- Ajouter les fiches d'offre avec informations vérifiables.
- Conserver les statuts distincts : source, publication, disponibilité et vérification.
- Empêcher les données absentes ou ambiguës d'être inventées.

**Validation :** parcours public clair et fiable, sans publication abusive ni informations inventées.

### 6. Configurer l'administration

- Utiliser Django Admin comme base de travail.
- Adapter les permissions, les vues et l'édition des offres.
- Mettre en place le processus de vérification des offres avant publication.
- Gérer les soumissions et les signalements dans un espace sécurisé.

**Validation :** seules les personnes autorisées peuvent modifier l'état des offres.

### 7. Tester, sécuriser et préparer le déploiement

- Vérifier les autorisations, les validations et les contrôles serveur.
- Tester les formulaires publics et privés.
- Sécuriser les secrets, les accès et les backups.
- Préparer la mise en production avec hébergement futur à choisir.

**Validation :** application stable, sécurisée et prête pour le lancement contrôlé.

## Règle de travail pour chaque fonctionnalité

Avancer par petites tranches : lire les documents concernés, définir un objectif
et des critères observables, modifier uniquement les fichiers nécessaires,
ajouter ou mettre à jour les tests, exécuter les contrôles pertinents, puis
résumer les changements et les décisions restantes. Ne pas changer une règle
métier ou une décision structurante sans la signaler et la faire valider.

## Documents de référence présents

- [Spécification générale](./specification_generale_plateforme_emploi_v0_1.md)
- [Architecture fonctionnelle](./architecture_fonctionnelle_plateforme_emploi_v0_1.md)
- [Modèle conceptuel de données](./modele_conceptuel_donnees_plateforme_emploi_v0_1.md)
- [Parcours utilisateurs](./parcours_utilisateurs_arborescence_pages_v0_1.md)
- [Plan de développement détaillé](./plan_developpement_detaille_v0_1.md)
- [Architecture technique proposée](./blueprint_developpement_plateforme_emploi_v0_1/architecture_technique_v0_1.md)
- [Système de composants UI](./blueprint_developpement_plateforme_emploi_v0_1/systeme_composants_ui_v0_1.md)
- [AGENTS.md](./AGENTS.md)
- [ENVIRONNEMENT-WINDOWS.md](./ENVIRONNEMENT-WINDOWS.md)
- [PLAN-DE-DEVELOPPEMENT.md](./PLAN-DE-DEVELOPPEMENT.md)
- [PREMIER-PROMPT.md](./PREMIER-PROMPT.md)
