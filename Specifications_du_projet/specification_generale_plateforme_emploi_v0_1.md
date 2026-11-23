# Spécification générale du produit
## Plateforme de référencement et de recherche d’opportunités professionnelles

**Version :** 0.1 — document de travail  
**Date :** 12 octobre 2026  
**Nom du projet :** à définir  
**Statut :** première base à valider avant la conception détaillée et le développement

> Ce document fixe la vision et les limites du produit. Il ne constitue pas encore le cahier des charges fonctionnel détaillé, le modèle de données ni le choix de la stack technique.

## 1. Résumé du projet

Le projet consiste à créer une plateforme web qui centralise et organise des offres d’emploi et d’autres opportunités professionnelles diffusées à travers plusieurs canaux : réseaux sociaux, sites web, entreprises, recruteurs et, lorsque des partenariats seront possibles, radios.

Au démarrage, la majorité des annonces pourra être collectée manuellement par l’administrateur à partir de sources accessibles. Les annonces seront présentées dans un format homogène, avec leur provenance, la date de collecte, un statut de contrôle et les instructions disponibles pour candidater. À terme, les entreprises et recruteurs pourront également soumettre directement des offres.

La première version vise le marché burkinabè. Le choix de la ville pilote reste à confirmer ; Bobo-Dioulasso et Ouagadougou sont des candidates possibles. L’expansion vers d’autres pays d’Afrique de l’Ouest est une ambition à plus long terme, après validation du modèle au Burkina Faso.

## 2. Contexte et problème à résoudre

Les opportunités professionnelles sont déjà diffusées à travers différents canaux : Facebook, WhatsApp, sites d’emploi, pages d’entreprises, bouche-à-oreille et émissions radio. Les démarches de candidature peuvent être simples et directes : contacter un numéro WhatsApp, appeler, envoyer un email, se rendre sur un site externe ou déposer physiquement un dossier.

Le projet part de l’hypothèse que cette information est dispersée, présentée de manière inégale et parfois difficile à actualiser. Un candidat peut avoir du mal à retrouver une annonce, à comparer plusieurs opportunités, à savoir si une offre est encore ouverte ou à identifier la source d’origine.

La plateforme cherchera donc à améliorer l’accès à l’information et sa lisibilité, sans imposer aux candidats ni aux employeurs un processus de recrutement compliqué.

**Hypothèse centrale à valider :** un nombre suffisant de candidats au Burkina Faso trouverait utile de consulter un catalogue unique, régulièrement actualisé et organisé, même si les candidatures continuent de passer par les canaux actuels des employeurs.

## 3. Vision, mission et objectif

### Vision

Devenir une référence accessible pour découvrir les opportunités professionnelles au Burkina Faso, puis éventuellement dans d’autres pays d’Afrique de l’Ouest.

### Mission

Rendre les offres et opportunités professionnelles plus faciles à trouver, à comprendre, à vérifier et à partager, quel que soit le canal par lequel elles ont été initialement diffusées.

### Objectif initial

Valider qu’un catalogue centralisé, entretenu et utile attire des visiteurs, facilite l’accès aux annonces et donne envie aux utilisateurs de revenir. La première phase cherchera à apprendre et à établir une base de confiance plutôt qu’à maximiser les revenus immédiatement.

## 4. Positionnement du produit

La plateforme doit être conçue d’abord comme un **média spécialisé et un catalogue de recherche d’opportunités professionnelles**, doté d’un processus éditorial de collecte, de structuration, de contrôle et d’actualisation.

Elle n’est pas, au lancement, un logiciel complet de gestion des ressources humaines ni un cabinet de recrutement numérique. Elle ne garantit pas qu’un candidat sera recruté et ne remplace pas la procédure officielle de candidature fixée par l’employeur.

### Proposition de valeur envisagée

- **Pour le candidat :** trouver au même endroit des opportunités venant de plusieurs sources, comprendre rapidement les conditions connues et accéder au canal de candidature.
- **Pour l’employeur :** bénéficier éventuellement d’un canal complémentaire de visibilité et, plus tard, d’un moyen simple de soumettre une offre.
- **Pour les partenaires de diffusion :** offrir une visibilité complémentaire aux annonces et, à terme, envisager des collaborations avec des radios ou des communautés locales.

Cette proposition devra être confirmée par des observations et des retours d’utilisateurs.

## 5. Publics concernés

### 5.1 Candidats et personnes en recherche d’opportunités

Personnes recherchant un emploi formel ou informel, un stage, une mission ponctuelle ou une autre opportunité professionnelle. Le produit ne doit pas supposer que chaque personne possède un CV élaboré ou souhaite créer un compte.

### 5.2 Employeurs et recruteurs

Entreprises de toutes tailles, commerces, ateliers, organisations, cabinets de recrutement et particuliers ou structures proposant des opportunités professionnelles légitimes. Leurs besoins et leurs moyens numériques peuvent être très différents.

### 5.3 Administrateur / équipe éditoriale

Au lancement, l’administrateur sera probablement la personne qui collecte les annonces, vérifie les informations disponibles, les classe, les publie, répond aux signalements et actualise ou retire les offres.

### 5.4 Partenaires et sources

Pages publiques, sites spécialisés, sites d’entreprises, groupes ou communautés lorsque la republication est autorisée, radios et autres relais locaux susceptibles de contribuer à la diffusion ou à la collecte d’offres.

## 6. Types d’opportunités couvertes

Le catalogue pourra accueillir, lorsque les informations sont suffisamment claires :

- emplois permanents ou à durée déterminée ;
- stages et premières expériences ;
- missions temporaires ou ponctuelles ;
- emplois à temps plein ou à temps partiel ;
- opportunités formelles, semi-formelles et certains emplois informels légitimes.

La plateforme ne devra pas inventer de conditions manquantes. Si le salaire, le contrat, la date limite ou l’expérience ne sont pas indiqués par la source, ces informations seront marquées comme non précisées plutôt que déduites.

## 7. Sources et publication des annonces

Deux voies d’entrée sont prévues dans la vision du produit :

1. **Collecte par l’administrateur :** recherche manuelle d’annonces disponibles auprès de sources pertinentes, puis saisie dans le système.
2. **Soumission directe :** formulaire permettant à un employeur ou recruteur de proposer une annonce. Les offres soumises directement seront contrôlées avant publication pendant la phase initiale.

Les deux voies doivent alimenter un seul catalogue. Chaque offre devra conserver une trace de sa provenance : nom de la source, lien vers la publication originale si disponible, date de collecte et informations de contrôle.

La source pourra être affichée publiquement avec un lien retour lorsque cela est approprié. La republication devra respecter les droits applicables, les conditions des plateformes sources et la protection des données personnelles. Une publication accessible publiquement n’est pas automatiquement libre de reproduction intégrale.

## 8. Principes de confiance et de transparence

La plateforme doit distinguer les contrôles suivants, qui ne sont pas interchangeables :

- **Source retrouvée :** l’annonce originale ou la source déclarée a été retrouvée.
- **Employeur vérifié :** l’identité de l’employeur a été contrôlée à l’aide d’éléments jugés suffisants.
- **Disponibilité confirmée :** une confirmation récente indique que le poste est toujours ouvert.
- **Offre expirée ou pourvue :** l’annonce ne doit plus être présentée comme une opportunité active.

Le détail des critères de validation sera défini plus tard dans les règles métier. Le produit ne devra jamais afficher un statut de vérification sans contrôle correspondant. Les visiteurs devront pouvoir signaler une annonce suspecte, inexacte ou expirée.

La vérification sera présentée comme un niveau de contrôle effectué, et non comme une garantie absolue contre la fraude ou comme une promesse d’embauche.

## 9. Principes de conception

1. **Mobile d’abord :** la consultation et les actions principales doivent être pratiques sur smartphone.
2. **Accès simple :** la consultation des offres publiques ne nécessite pas de compte au lancement.
3. **Candidature par le canal indiqué :** WhatsApp, téléphone, email, site externe ou dépôt physique peuvent être utilisés selon la source.
4. **Transparence :** provenance, date de collecte et état de contrôle sont visibles lorsque cela est pertinent.
5. **Fraîcheur de l’information :** les offres anciennes doivent être réexaminées, marquées comme à confirmer ou retirées.
6. **Sobriété du MVP :** construire uniquement les fonctions essentielles au test initial, tout en évitant des choix techniques qui bloqueraient les évolutions raisonnables.
7. **Langage accessible :** interfaces et instructions en français clair, avec une conception qui pourra être adaptée plus tard à d’autres langues si le besoin est démontré.
8. **Protection des données :** ne collecter que les données nécessaires et éviter d’exposer des coordonnées qui n’étaient pas destinées à une diffusion publique.

## 10. Périmètre du MVP envisagé

Le MVP devra permettre de démontrer le fonctionnement principal de bout en bout : collecter des offres, les structurer, les contrôler, les publier, aider le visiteur à les retrouver et l’orienter vers la candidature.

### Inclus dans le MVP

- site web responsive ;
- catalogue public d’offres ;
- fiches détaillées pour chaque annonce ;
- recherche et filtres essentiels ;
- source, date de collecte et statut de contrôle ;
- liens ou instructions de candidature ;
- interface d’administration protégée pour créer, modifier, publier, archiver et supprimer des offres ;
- formulaire de soumission d’offre, avec validation administrative avant publication ;
- mécanisme simple de signalement ou de demande de correction ;
- suivi de base des consultations et clics vers les canaux de candidature.

### Hors périmètre initial

- application mobile native ;
- comptes candidats obligatoires ;
- espace employeur complet avec gestion de plusieurs recrutements ;
- ATS / pipeline RH sophistiqué ;
- matching avancé par IA ;
- traitement automatique généralisé des annonces provenant des réseaux sociaux ;
- paiement intégré, abonnements ou annonces sponsorisées ;
- déploiement simultané dans plusieurs pays ;
- promesse de placement ou de recrutement garanti.

Ces éléments pourront être réévalués à partir des usages, des retours et des contraintes techniques et économiques.

## 11. Modèle économique : principe de départ

La phase initiale privilégiera l’accès gratuit au catalogue pour les candidats et la soumission gratuite des annonces. La stratégie de monétisation n’est pas encore arrêtée.

Les pistes à explorer ultérieurement comprennent la mise en avant d’annonces, la diffusion multicanale, les services de présélection, des outils destinés aux employeurs et des partenariats avec des acteurs de l’emploi ou de la formation. Aucune de ces pistes ne doit être considérée comme validée avant d’avoir observé un besoin et testé une volonté de payer.

La candidature classique ne devrait pas devenir payante dans le MVP. Toute évolution devra préserver l’utilité et la confiance du service.

## 12. Indicateurs de validation

Les premiers indicateurs doivent aider à juger l’utilité et la qualité du service, pas seulement le volume de trafic :

- nombre d’offres actives et part des annonces actualisées ;
- diversité des sources et des catégories couvertes ;
- consultations des fiches et recherches effectuées ;
- clics vers les canaux de candidature ;
- partages des annonces ;
- signalements d’annonces expirées ou inexactes ;
- retours et visites répétées des candidats ;
- nombre d’offres soumises directement par des employeurs ;
- demandes de publication répétées ou demandes spontanées de services complémentaires.

Les objectifs chiffrés seront fixés après le choix de la zone pilote et la définition du protocole de test.

## 13. Principaux risques à anticiper

- **Offres obsolètes :** prévoir des règles de réexamen, d’expiration et de retrait.
- **Fraudes ou informations trompeuses :** clarifier les statuts, contrôler la source et permettre les signalements.
- **Republication non autorisée :** définir les règles de collecte, attribution, résumé et retrait.
- **Exposition de données personnelles :** ne publier que les coordonnées et renseignements nécessaires, pour un usage prévu par la source.
- **Manque d’offres ou de visiteurs :** démarrer sur une zone limitée et travailler la distribution via les canaux existants.
- **Charge de gestion manuelle :** garder le processus simple au départ et mesurer le temps requis par offre.
- **Monétisation prématurée :** ne pas bâtir le modèle financier sur une volonté de payer qui n’a pas été démontrée.

## 14. Décisions acquises et éléments à confirmer

### Décisions déjà exprimées

- Construire un site web sur mesure, avec l’aide d’outils d’IA pour le développement.
- Commencer par le Burkina Faso, avec une ambition régionale à plus long terme.
- Centraliser les offres provenant de plusieurs canaux, et pas seulement les annonces publiées directement par des employeurs.
- Collecter les premières annonces manuellement.
- Afficher la source et, lorsque c’est possible et approprié, un lien vers la publication originale.
- Prévoir des liens de candidature adaptés au canal original, notamment WhatsApp, les sites externes et les dépôts physiques.
- Garder le catalogue gratuit pendant la phase initiale et décider de la monétisation après observation.
- Définir la conception du produit et son architecture avant le développement détaillé.

### À confirmer avant la spécification détaillée

- ville ou zone exacte du pilote ;
- nom et identité de la plateforme ;
- types précis d’opportunités admis ou exclus ;
- règles opérationnelles et critères de chaque statut de contrôle ;
- politique de collecte et de republication des annonces issues de groupes ou de sources tierces ;
- durée pendant laquelle une annonce reste active sans confirmation ;
- technologies, hébergement, budget et outils de développement ;
- objectifs chiffrés du test initial.

## 15. Suite du travail

Après validation de cette spécification générale, les prochains livrables seront :

1. l’architecture fonctionnelle et la liste des modules ;
2. les rôles, autorisations et parcours utilisateurs ;
3. le modèle de données et les règles métier ;
4. l’architecture technique et les exigences de sécurité ;
5. les pages et wireframes ;
6. le plan de réalisation du MVP et ses critères de test.

**Ce document est une base de travail évolutive. Les points marqués « à confirmer » ne doivent pas être transformés en exigences définitives sans décision explicite.**
