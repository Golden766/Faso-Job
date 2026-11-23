# Wireframes visuels basse fidélité — Plateforme d'opportunités professionnelles

**Version :** 0.1 — 12 octobre 2026  
**Statut :** proposition de travail à valider  
**Objectif :** valider l'organisation générale des écrans avant la maquette visuelle haute fidélité et le développement.

> Les annonces, noms, chiffres, salaires et statuts figurant dans les wireframes sont fictifs. Ils ne représentent pas des offres réelles. Le nom « OPPORTUNITÉS » est provisoire.

## Principes utilisés

- Priorité au mobile pour la consultation publique ; l'administration est d'abord optimisée pour ordinateur, tout en restant accessible sur mobile.
- Interface basse fidélité, sans identité graphique définitive.
- Consultation publique sans création de compte obligatoire.
- Les offres collectées manuellement et les soumissions externes alimentent un même catalogue après contrôle.
- La source de l'annonce, l'état de publication, les contrôles effectués et la disponibilité du poste restent distincts.
- Les informations inconnues sont indiquées comme non précisées, jamais devinées.

## Écran 1 — Accueil
**Objectif :** orienter immédiatement vers la recherche et rendre visibles les opportunités récentes.

Zones : en-tête, proposition de valeur, recherche par métier et ville, catégories d'opportunités, offres récentes, appel à soumettre une offre, pied de page.

Mobile : champs empilés, CTA de recherche pleine largeur, catégories horizontales, cartes d'offres en une colonne.

![Accueil desktop](desktop/01_accueil.png)

## Écran 2 — Catalogue et recherche
**Objectif :** permettre de retrouver les offres selon les critères disponibles.

Zones : titre et contexte, champ de mots-clés, ville, filtres, compteur de résultats, tri, liste d'offres, pagination ou chargement supplémentaire.

Mobile : filtres regroupés dans un panneau repliable ; les résultats occupent toute la largeur ; chaque carte montre les informations les plus utiles.

![Catalogue desktop](desktop/02_catalogue_recherche.png)

## Écran 3 — Fiche d'offre
**Objectif :** donner assez d'informations au visiteur pour décider s'il contacte l'employeur.

Zones : intitulé, ville, type, informations essentielles, description, profil, source, dates et statuts de contrôle, action de candidature, signalement.

Règle : ne pas afficher « employeur vérifié » ou « disponibilité confirmée » si le contrôle correspondant n'a pas été effectué. Sur mobile, les actions principales apparaissent avant les sections longues.

![Fiche d'offre desktop](desktop/03_fiche_offre.png)

## Écran 4 — Soumettre une offre
**Objectif :** permettre à un employeur ou contributeur de proposer gratuitement une annonce, sans créer de compte au MVP.

Zones : explication du processus, informations du poste, description, source originale, modalité de candidature, moyen de recontacter la personne ayant soumis, avertissement sur la validation préalable.

La soumission crée un élément en attente de contrôle, jamais une offre publique automatiquement.

![Soumettre une offre desktop](desktop/04_soumettre_offre.png)

## Écran 5 — Tableau de bord d'administration
**Objectif :** aider l'administrateur à piloter les opérations courantes.

Zones : navigation latérale, indicateurs synthétiques, actions en attente, annonces à actualiser, tableau des offres récemment modifiées, accès aux files de contrôle et aux signalements.

L'administration est conçue d'abord pour ordinateur ; une adaptation mobile indicative est fournie, sans chercher à optimiser toutes les opérations complexes sur téléphone.

![Administration desktop](desktop/05_admin_tableau_bord.png)

## Parcours mobile

Les aperçus mobiles accompagnent chaque écran dans le document Word et sont disponibles séparément dans le dossier `mobile/`.

## Décisions à confirmer avant haute fidélité

1. Nom de marque et identité visuelle.
2. Ordre exact des filtres du catalogue ; ne montrer que des filtres qui correspondent à des données réellement collectées.
3. Niveau de détail de la page d'accueil lorsque le catalogue contient peu d'offres.
4. Politique d'affichage des coordonnées et liens de candidature selon la source et les permissions obtenues.
5. Libellés précis des statuts de confiance et de fraîcheur.
6. La soumission sans compte reste la proposition du MVP ; un contrôle anti-abus doit être prévu.
7. L'administration mobile est secondaire, mais les tâches de contrôle urgentes doivent rester possibles.

## Hors périmètre de ces wireframes

- couleurs et typographies définitives ;
- logo et éléments de marque ;
- animations et micro-interactions ;
- authentification complète employeur/candidat ;
- alertes personnalisées, paiements, annonces sponsorisées et matching par IA.

## Critère de validation

Valider que chaque écran contient les informations et actions nécessaires, que la navigation est compréhensible, que les statuts sont honnêtes et que le parcours mobile permet de chercher une offre et d'accéder à la candidature sans compte obligatoire.
