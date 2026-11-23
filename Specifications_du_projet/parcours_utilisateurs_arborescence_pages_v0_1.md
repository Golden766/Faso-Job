# Parcours utilisateurs et arborescence des pages

**Version :** 0.1 — document de travail  
**Date :** 12 octobre 2026  
**Projet :** plateforme d'opportunités professionnelles — nom à définir  
**Documents de référence :** spécification générale v0.1 ; architecture fonctionnelle v0.1 ; modèle conceptuel de données v0.1  
**Statut :** proposition à relire avant les maquettes détaillées

> Ce document décrit les parcours et les pages nécessaires au MVP. Il ne constitue ni une maquette graphique ni une spécification technique définitive. Les chemins d'URL proposés sont indicatifs et pourront être adaptés à la technologie retenue.

## 1. Objectif et périmètre

L'objectif est de définir comment les visiteurs découvrent une offre, la comprennent et accèdent à la candidature, comment un tiers peut soumettre une annonce, et comment l'administrateur collecte, contrôle, publie et actualise les offres.

### Principes retenus

- Le catalogue est consultable sans compte.
- La candidature se déroule généralement en dehors de la plateforme, par WhatsApp, téléphone, email, site externe ou dépôt physique.
- Une annonce soumise par un tiers ne devient jamais publique automatiquement dans le MVP.
- Les offres collectées et les offres soumises suivent le même contrôle éditorial et aboutissent au même catalogue central.
- L'origine de l'annonce, l'état de publication, la disponibilité du poste et les vérifications sont présentés séparément.
- Le site doit d'abord être simple à utiliser sur smartphone et rester léger.
- Les comptes candidats, l'espace employeur complet, les alertes avancées et la candidature hébergée sont hors périmètre initial.

## 2. Rôles et besoins

| Rôle | Besoin principal | Capacités prévues au MVP |
|---|---|---|
| Visiteur / chercheur d'emploi | Trouver une opportunité pertinente et savoir comment postuler | Consulter, rechercher, filtrer, partager, ouvrir un canal de candidature, signaler une annonce, soumettre une offre si nécessaire |
| Employeur ou autre contributeur | Faire connaître une opportunité | Remplir un formulaire public de soumission ; recevoir une confirmation de réception, sans publication automatique |
| Administrateur | Gérer le catalogue et la qualité du contenu | Collecter, créer, modifier, contrôler, publier, fermer, archiver, traiter les signalements et consulter les statistiques de base |
| Modérateur distinct | Aider à vérifier et traiter les signalements | Hors MVP ; pourra être introduit si le volume le justifie |
| Candidat inscrit | Recevoir des alertes, enregistrer des favoris | Évolution future, non nécessaire à la consultation publique |
| Employeur inscrit | Gérer ses offres et consulter des statistiques | Évolution future ; le MVP ne propose qu'un formulaire de soumission |

**Décision de conception :** « visiteur » et « candidat » désignent la même personne lorsqu'elle consulte le site sans compte. Il n'est pas nécessaire de distinguer ces rôles dans le système au lancement.

## 3. Arborescence proposée

### 3.1 Espace public

```text
/
├── /offres                         Catalogue et recherche
│   └── /offres/:slug               Fiche détaillée d'une offre
├── /soumettre-une-offre            Formulaire de soumission
├── /soumettre-une-offre/confirmation
├── /a-propos                       Présentation du projet
├── /methode-de-verification        Explication des statuts et contrôles
├── /contact
├── /confidentialite
├── /conditions-utilisation
└── /signaler/:offerId              ou formulaire intégré à la fiche
```

Les filtres de recherche (ville, métier, type d'emploi, salaire, date) peuvent être des paramètres de la page catalogue plutôt que des pages distinctes. Les pages de référencement spécifiques par ville ou métier pourront être ajoutées après validation du besoin SEO ; elles ne sont pas indispensables au premier MVP.

### 3.2 Espace d'administration

```text
/admin/connexion
└── /admin
    ├── /                           Tableau de bord
    ├── /offres                     Liste et recherche interne
    ├── /offres/nouvelle            Création d'une annonce collectée
    ├── /offres/:id                 Détail, édition et contrôles
    ├── /soumissions                Annonces envoyées via le formulaire public
    ├── /signalements               Offres signalées par les visiteurs
    └── /statistiques               Indicateurs d'utilisation de base
```

Les chemins d'administration sont des propositions logiques, pas un engagement technique. Les sections « sources », « catégories » et « paramètres » peuvent être gérées dans les formulaires ou ajoutées à l'interface si leur gestion devient fréquente. L'administration doit être protégée et inaccessible aux visiteurs non autorisés.

## 4. Parcours utilisateur principaux

### Parcours A — trouver une offre et contacter l'employeur

**Point d'entrée :** accueil, résultat de recherche Google, lien WhatsApp/Facebook, partenaire ou URL partagée.

1. Le visiteur arrive sur la page d'accueil ou directement sur une fiche d'offre.
2. Il parcourt les annonces récentes ou ouvre le catalogue.
3. Il recherche par mots-clés et/ou applique les filtres disponibles.
4. Il consulte une fiche détaillée : poste, lieu, conditions connues, date, source et statuts de contrôle.
5. Il choisit l'action de candidature proposée : WhatsApp, téléphone, email, site externe ou dépôt physique.
6. Il peut partager l'annonce ou signaler une information inexacte.

**Résultat attendu :** le visiteur sait ce qui est proposé, ce qui a été contrôlé et comment contacter le recruteur, sans devoir créer un compte.

**Cas particuliers à couvrir :** aucun résultat ; informations non précisées ; offre à actualiser ; offre fermée consultée depuis un ancien lien ; lien de candidature indisponible.

### Parcours B — soumettre une annonce

**Point d'entrée :** lien « Soumettre une offre » visible dans la navigation et dans le pied de page.

1. Le contributeur ouvre le formulaire public.
2. Il saisit les informations principales du poste et les modalités de candidature.
3. Il indique la source ou confirme qu'il est autorisé à soumettre l'annonce au nom du recruteur ; les champs exacts seront définis dans la spécification du formulaire.
4. Il confirme les informations et envoie le formulaire.
5. Le système valide les champs, enregistre la soumission en attente et affiche une confirmation de réception.
6. L'administrateur examine l'annonce ; il peut la publier, demander une correction par un canal disponible ou la refuser.

**Résultat attendu :** le contributeur comprend que l'annonce a été reçue mais qu'elle n'est pas nécessairement publiée immédiatement.

**Règle MVP :** pas de compte employeur obligatoire et pas de publication automatique. La gestion d'une demande de correction sans compte pourra se faire manuellement au lancement.

### Parcours C — collecter et publier une annonce manuellement

**Point d'entrée :** espace d'administration.

1. L'administrateur repère une annonce sur une source accessible.
2. Il vérifie si elle existe déjà dans le catalogue afin de limiter les doublons.
3. Il crée un brouillon, enregistre la source et la date de collecte.
4. Il reformule et structure les faits utiles sans inventer les informations absentes.
5. Il ajoute uniquement les marqueurs de contrôle justifiés par les vérifications effectuées.
6. Il prévisualise la fiche puis la publie si elle répond aux règles éditoriales.
7. Il vérifie ensuite les retours, les signalements et l'ancienneté ; il actualise, ferme ou archive l'offre si nécessaire.

**Résultat attendu :** les annonces issues de sources diverses sont présentées dans un format homogène et gardent une provenance traçable.

### Parcours D — traiter un signalement

1. Le visiteur choisit « Signaler cette offre » depuis la fiche.
2. Il sélectionne un motif : offre expirée/pourvue, informations inexactes, contact injoignable, suspicion de fraude ou autre.
3. Il peut ajouter une précision facultative, sans devoir créer un compte.
4. Le système enregistre le signalement pour examen et affiche un accusé de réception.
5. L'administrateur consulte l'annonce, la source et le motif ; il décide de maintenir, corriger, actualiser, suspendre ou fermer l'annonce.
6. Les changements importants sont conservés dans l'historique opérationnel.

**Règle MVP :** un signalement ne retire pas automatiquement l'annonce. L'administration doit pouvoir agir rapidement, mais la décision dépend des éléments examinés.

### Parcours E — administrer le catalogue au quotidien

1. L'administrateur se connecte à l'espace protégé.
2. Le tableau de bord met en évidence les soumissions à examiner, les signalements et les offres à actualiser.
3. Il ouvre une file de travail et traite les éléments un par un.
4. Il peut rechercher une offre, corriger ses données ou modifier son statut.
5. Il consulte les statistiques de base afin de repérer les offres vues et les actions de contact générées.
6. Il se déconnecte ; les visiteurs n'ont aucun accès à l'espace d'administration.

**Résultat attendu :** les opérations quotidiennes peuvent être réalisées par une seule personne sans outils RH complexes.

## 5. Responsabilité et contenu des pages principales

| Page | Contenu / actions essentiels | État ou règle à prévoir |
|---|---|---|
| Accueil | Recherche, accès au catalogue, offres récentes, appel à soumettre une offre, explication courte de la promesse | État si aucune offre récente ; ne pas afficher des annonces fermées comme actives |
| Catalogue | Liste d'offres, recherche, filtres, tri pertinent, pagination ou chargement progressif | Aucun résultat, filtres actifs, chargement et erreur |
| Fiche d'offre | Poste, lieu, description, conditions connues, source, dates, statuts de contrôle, action de candidature, partage, signalement | Offre active, à actualiser ou fermée ; données inconnues clairement indiquées |
| Soumettre une offre | Formulaire, règles de soumission, champs obligatoires, consentements et validation | Erreurs compréhensibles, confirmation après envoi, prévention du spam |
| Confirmation de soumission | Confirmation de réception et explication de la suite | Ne pas promettre une publication automatique ni un délai non garanti |
| Méthode de vérification | Définition des statuts, contrôles réalisés et limites | Texte clair, pas de score de confiance artificiel |
| Contact / signalement | Canaux de contact et formulaire de signalement | Ne collecter que les données nécessaires |
| Administration — tableau de bord | Résumé des offres, soumissions, signalements, offres à actualiser | États vides et priorités opérationnelles |
| Administration — gestion des offres | Recherche interne, filtres par statut, création, édition, aperçu et changement de statut | Confirmer les actions sensibles ; limiter les erreurs de manipulation |
| Administration — soumissions | Contenu reçu, source, coordonnées fournies, actions publier/refuser/demander une correction | Le contenu reste non public tant qu'il n'est pas approuvé |
| Administration — signalements | Motif, offre associée, notes et action de résolution | Statut du signalement traçable |
| Administration — statistiques | Vues, clics sortants, partages, recherches et volume d'offres | Présenter les clics comme des intentions de contact, pas comme des recrutements confirmés |

## 6. Règles de navigation et d'expérience

- Le catalogue doit être accessible depuis toutes les pages publiques principales.
- Chaque fiche publiée possède une URL stable et partageable.
- Le bouton de candidature doit correspondre au mode indiqué dans l'annonce ; ne pas afficher un bouton WhatsApp si le numéro ou le lien n'est pas disponible.
- Les informations inconnues sont marquées « non précisé » ou simplement omises ; elles ne sont jamais inventées.
- Une annonce fermée vue depuis un ancien lien affiche clairement son état et, si possible, propose de revenir aux offres actives.
- Les formulaires doivent être utilisables au téléphone, afficher les erreurs près des champs concernés et préserver autant que possible les saisies en cas d'erreur.
- Les contrôles de sécurité des pages d'administration sont appliqués côté serveur, pas seulement par masquage d'éléments visuels.
- L'interface doit rester légère, lisible et utilisable avec une connexion mobile modeste.
- Les pages doivent distinguer l'action principale (consulter / postuler ou contacter) des actions secondaires (partager / signaler).

## 7. États communs à traiter

| Situation | Comportement attendu |
|---|---|
| Catalogue vide | Expliquer qu'aucune offre n'est disponible pour l'instant et proposer de revenir ou d'élargir les critères |
| Recherche sans résultat | Afficher les critères appliqués et permettre de les retirer facilement |
| Offre fermée ou expirée | Informer clairement le visiteur et proposer de consulter les offres actives |
| Offre avec informations manquantes | Afficher uniquement les informations disponibles ; utiliser « non précisé » si cela aide la compréhension |
| Lien de candidature manquant | Expliquer le mode de candidature connu ou signaler que les coordonnées ne sont pas disponibles ; ne pas inventer de contact |
| Erreur lors d'une soumission | Expliquer l'erreur et permettre de corriger sans perdre les champs inutilement |
| Signalement envoyé | Confirmer la réception sans promettre une action ou un délai précis |
| Erreur serveur / page introuvable | Afficher un message compréhensible et une voie de retour vers le catalogue |

## 8. Périmètre du MVP et évolutions

### À construire dans le MVP

- Accueil, catalogue, recherche et filtres essentiels.
- Fiche d'offre publique avec provenance, contrôles, dates et action de candidature.
- Formulaire public de soumission avec confirmation de réception.
- Formulaire de signalement.
- Connexion administrateur et pages d'administration nécessaires à la collecte, l'édition, la publication, la clôture, aux soumissions et aux signalements.
- Statistiques de base des consultations et actions sortantes.
- Pages de présentation, de contact et de confidentialité.

### À prévoir mais pas à construire tout de suite

- Compte candidat, favoris et alertes personnalisées.
- Compte employeur complet et gestion autonome des annonces.
- Candidature directement sur la plateforme et suivi des candidatures.
- Paiements, annonces sponsorisées et abonnements.
- Recommandation personnalisée ou matching par IA.
- Publication automatique sur les réseaux sociaux et intégrations partenaires avancées.
- Interfaces séparées de modération et rôles d'équipe multiples.

## 9. Critères d'acceptation avant les maquettes détaillées

La conception des maquettes peut commencer lorsque :

1. les entrées et sorties de chaque parcours sont définies ;
2. les pages nécessaires au MVP sont recensées ;
3. les rôles, permissions et restrictions sont clairs ;
4. les états normaux, vides, expirés et en erreur sont pris en compte ;
5. les règles de soumission, de contrôle et de publication sont cohérentes avec l'architecture fonctionnelle ;
6. les fonctions hors MVP sont explicitement séparées ;
7. les décisions ouvertes sont consignées plutôt que supposées.

## 10. Décisions ouvertes à traiter plus tard

- Faut-il créer dès le MVP des pages SEO dédiées par ville/métier ou se limiter au catalogue filtrable ?
- Quel niveau de détail le formulaire public de soumission doit-il exiger ?
- Comment permettre à un contributeur sans compte de répondre à une demande de correction ?
- Quelle politique précise appliquer aux offres anciennes et à leur reconfirmation ?
- Quels événements analytiques sont nécessaires au départ, et combien de temps les conserver ?
- Faut-il proposer une page publique regroupant les dernières annonces d'une source partenaire ?

Ces décisions n'empêchent pas d'avancer sur le modèle conceptuel ; elles devront être résolues avant que les écrans et le comportement correspondant soient définitivement figés.

## 11. Étape suivante

Après validation de cette arborescence et de ces parcours, le prochain livrable sera une **spécification des écrans (wireframes fonctionnels)** : pour chaque page du MVP, définir les zones, composants, actions, états et liens de navigation. On pourra ensuite établir la conception visuelle puis finaliser les détails techniques avant le développement.
