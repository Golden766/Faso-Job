# Environnement Windows

## Objectif

Le projet est développé avec Python et Django. L'environnement principal n'est plus Node.js, mais Python avec un environnement virtuel dédié.

## Outils à installer

- Python 3.11 ou 3.12 (version stable prise en charge)
- VS Code
- Git
- Un environnement virtuel Python (`venv`)
- PostgreSQL localement au départ, éventuellement via Docker plus tard

## Étapes recommandées

1. Installer Python depuis le site officiel ou via le gestionnaire de paquets de Windows.
2. Vérifier l'installation :

```bash
python --version
pip --version
```

3. Installer VS Code et Git.
4. Créer un environnement virtuel dans le dossier du projet :

```bash
python -m venv .venv
.venv\Scripts\activate
```

5. Vérifier que le venv est actif puis installer les dépendances Python nécessaires.
6. Préparer PostgreSQL éventuellement dans un second temps, avec une option Docker si la base doit être ajoutée sans installer un moteur complet localement.

## Règles de préparation

- Python remplace Node.js comme environnement principal.
- Le projet doit pouvoir être démarré localement dans un environnement virtuel propre.
- Les secrets doivent rester hors du dépôt et être stockés dans des variables d'environnement.
- PostgreSQL est la base cible, même si l'installation locale peut être différée au moment où le schéma Django est prêt.

## Vérification avant démarrage

Avant de créer l'application Django, vérifier :

- Python installé et fonctionnel ;
- Git disponible ;
- VS Code ouvert sur le projet ;
- environnement virtuel prêt ;
- dossier de travail propre et documenté.
