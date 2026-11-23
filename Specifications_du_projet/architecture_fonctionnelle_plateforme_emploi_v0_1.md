# Architecture fonctionnelle de la plateforme d'opportunités professionnelles

**Version :** 0.1 — document de travail  
**Date :** 12 octobre 2026  
**Nom du projet :** à définir  
**Dépendance :** Spécification générale du produit v0.1  
**Statut :** proposition à examiner avant le modèle de données et les maquettes

> Ce document décrit les modules fonctionnels et leurs interactions. Il ne fixe pas encore la stack technique, le schéma détaillé de la base de données ni le design final des écrans.

## 1. Objectif de ce document

Définir une architecture fonctionnelle cohérente pour organiser le produit avant le développement sur mesure avec l'aide de l'IA. Le document précise les modules, leur responsabilité, les rôles qui les utilisent, les principaux flux et la frontière entre le MVP et les évolutions futures.

L'architecture doit permettre de commencer avec une collecte manuelle et un petit volume d'offres, puis d'évoluer sans devoir séparer ou reconstruire le catalogue.

## 2. Principes d'architecture

1. **Un catalogue central unique.** Toutes les offres, qu'elles soient collectées manuellement ou soumises par un employeur, alimentent le même catalogue après contrôle.
2. **Séparation entre contenu, source et contrôle.** Une offre, sa provenance et les contrôles effectués sont des informations liées, mais distinctes.
3. **Aucune candidature interne obligatoire au départ.** La plateforme présente l'offre et dirige vers le canal de candidature indiqué par la source : WhatsApp, téléphone, email, site externe ou dépôt physique.
4. **Accès public sans compte.** Les visiteurs peuvent consulter les offres sans créer de compte.
5. **Publication contrôlée.** Aucune soumission externe ne devient publique automatiquement pendant le MVP.
6. **Statuts explicites.** L'état de publication d'une annonce ne doit pas être confondu avec le fait que le recruteur ou la disponibilité du poste ont été vérifiés.
7. **Traçabilité.** Chaque offre collectée doit conserver sa source, la date de collecte et les actions de contrôle importantes.
8. **Mobile d'abord et sobriété.** Le parcours principal doit rester simple sur smartphone et les premières fonctions doivent pouvoir être administrées manuellement.
9. **Évolution progressive.** Alertes, comptes employeurs, automatisation et monétisation pourront être ajoutés sans les rendre obligatoires au MVP.

## 3. Cartographie générale des modules

La plateforme est organisée autour des modules suivants :

- **M1 — Découverte publique :** accueil, catalogue, recherche, filtres, fiche d'offre et navigation par catégories ou villes.
- **M2 — Collecte et sources :** saisie manuelle, enregistrement des sources, formulaire de soumission d'offre.
- **M3 — Gestion éditoriale des offres :** brouillons, contrôle, publication, mise à jour, expiration et retrait.
- **M4 — Qualité et confiance :** informations de vérification, signalements et correction des annonces.
- **M5 — Diffusion et partage :** URL d'offre, partage social, accès aux canaux de candidature et préparation future des alertes.
- **M6 — Mesure et retours :** consultations, clics sortants, partages, recherches et signalements.
- **M7 — Administration et permissions :** accès sécurisé à l'espace interne et actions autorisées.
- **M8 — Services candidats (évolution) :** alertes personnalisées, favoris, préférences et éventuellement compte candidat.
- **M9 — Services employeurs (évolution) :** espace employeur, gestion de ses annonces et statistiques avancées.

### 3.1 Vue simplifiée des flux

```text
Sources publiques ──> Collecte manuelle ──┐
                                          ├─> Contrôle éditorial ─> Catalogue central
Formulaire employeur ─> File de contrôle ─┘                            │
                                                                       ├─> Site public / recherche
                                                                       ├─> Partage / diffusion
                                                                       ├─> Contact ou candidature externe
                                                                       └─> Mesure des interactions
                                                                                 │
Signalement / retour utilisateur ───────────────────────────────────────────────┘
```

Le contrôle éditorial est la passerelle obligatoire vers la publication. La mesure des interactions sert à améliorer la plateforme, mais un clic ou une consultation ne prouve pas qu'une candidature ou un recrutement a abouti.

## 4. Description des modules

### M1 — Découverte publique

**Mission :** aider un visiteur à trouver une opportunité, à en comprendre les informations disponibles et à accéder au canal de candidature.

**Fonctions MVP :**
- page d'accueil avec les offres récentes et un accès évident à la recherche ;
- catalogue des offres publiées ;
- recherche simple par mots-clés ;
- filtres essentiels selon les données réellement disponibles : ville, catégorie/métier, type d'opportunité et éventuellement salaire ;
- fiche détaillée d'une offre ;
- affichage de la source, de la date de collecte et des statuts de contrôle pertinents ;
- bouton d'action adapté au mode de candidature ;
- partage d'une fiche par lien ;
- pages d'information : à propos, méthode de contrôle, contact, confidentialité et signalement.

**Évolutions possibles :** pages de référencement par métier et ville, recherche sauvegardée, alertes, favoris et recommandations personnalisées.

**Hors périmètre MVP :** profil candidat, candidature hébergée, messagerie interne et suivi complet d'une candidature.

### M2 — Collecte et gestion des sources

**Mission :** faire entrer les offres dans le système avec une provenance claire.

**Voies d'entrée :**
1. **Collecte interne :** l'administrateur crée une fiche à partir d'une annonce retrouvée sur une source accessible.
2. **Soumission externe :** un employeur ou un tiers remplit un formulaire public. La soumission arrive en attente de contrôle et ne peut pas être publiée immédiatement.

**Informations opérationnelles :** nom et type de source, URL source lorsqu'elle existe, date de collecte, mode de collecte, notes internes et référence vers la publication originale.

**Règles :**
- une source publique n'autorise pas automatiquement la reproduction intégrale de son contenu ;
- l'annonce doit être reformulée et structurée lorsque cela est nécessaire, sans modifier le sens des faits ;
- les coordonnées visibles doivent être celles indiquées pour la candidature ou clairement prévues pour un contact professionnel ;
- les annonces issues de groupes privés ou contenant des données personnelles non destinées à une diffusion publique demandent une prudence particulière et, si nécessaire, une autorisation ;
- le système doit permettre de retrouver l'origine d'une annonce après sa publication.

### M3 — Gestion éditoriale du cycle de vie des offres

**Mission :** assurer qu'une offre suit un processus prévisible de la collecte au retrait.

**Fonctions MVP :** créer, modifier, prévisualiser, soumettre au contrôle, publier, dépublier, marquer expirée/pourvue, archiver et supprimer selon les règles retenues.

**Cycle de publication recommandé :**
1. **Brouillon :** fiche en préparation, non publique.
2. **À contrôler :** les informations doivent être examinées avant publication.
3. **Publiée :** visible dans le catalogue public.
4. **À actualiser :** nécessite une vérification de fraîcheur ; l'interface doit signaler l'incertitude selon les règles adoptées.
5. **Fermée :** expirée, pourvue ou retirée ; n'apparaît plus dans les résultats actifs.
6. **Archivée :** conservée pour l'historique interne, sans visibilité publique active.

Une soumission peut également être **refusée** avec une raison interne. L'historique des principales actions doit être conservé de manière proportionnée.

**Gestion des doublons :** avant publication, l'administrateur doit pouvoir repérer une annonce qui semble identique ou très similaire à une autre. Selon le cas, on met à jour l'annonce existante, on relie la nouvelle source ou on conserve deux annonces distinctes si les recrutements sont réellement différents.

### M4 — Qualité, vérification et signalements

**Mission :** informer clairement le visiteur sur les contrôles effectués et offrir une voie de correction.

Il faut conserver séparément trois dimensions :

- **État de publication :** brouillon, en contrôle, publiée, fermée, archivée, etc.
- **Contrôles de confiance :** source retrouvée, employeur vérifié, disponibilité confirmée. Chaque marqueur ne peut être activé que si le contrôle correspondant a été effectué.
- **Disponibilité de l'annonce :** inconnue/à confirmer, déclarée ouverte ou confirmée ouverte, pourvue/expirée/retirée selon les informations disponibles.

Les libellés visibles pourront être simplifiés, mais ils ne doivent pas promettre plus que ce qui a été vérifié.

**Signalement MVP :** un visiteur peut signaler une offre suspecte, expirée, inexacte ou ayant un problème de contact. Le signalement crée un élément à examiner dans l'administration ; il ne retire pas automatiquement l'offre, sauf règle de sécurité future spécifiquement définie.

**Traitement interne :** consulter l'offre, le motif du signalement et les éléments disponibles ; décider de maintenir, corriger, mettre à jour, suspendre ou retirer ; conserver une note de décision lorsque c'est utile.

### M5 — Diffusion, partage et accès à la candidature

**Mission :** rendre les offres faciles à redistribuer et aider les visiteurs à passer de la lecture à l'action.

**Fonctions MVP :**
- URL stable pour chaque offre publiée ;
- action de partage via les fonctions courantes du navigateur ou un lien copiable ;
- génération de liens sortants vers un site de candidature ou WhatsApp lorsque ces informations ont été fournies et contrôlées ;
- affichage des instructions de dépôt physique lorsque la source fournit les détails nécessaires ;
- comptage des clics sortants à des fins statistiques, sous réserve d'une mise en œuvre respectueuse de la vie privée.

**Fonctions manuelles au départ :** sélectionner des offres et préparer une publication pour Facebook ou WhatsApp. Il n'est pas nécessaire d'automatiser la publication sur les réseaux sociaux dans le MVP.

**Évolutions :** alertes par ville/métier, flux partenaires, API ou outils de diffusion automatique lorsque l'usage le justifie.

### M6 — Statistiques et retours

**Mission :** mesurer l'utilité du catalogue et soutenir les décisions produit.

**Indicateurs de base :** offres actives, offres à actualiser, vues de fiches, recherches, clics sortants, partages, signalements et sources d'acquisition lorsque la mesure est disponible.

**Limites d'interprétation :** une consultation ne signifie pas un intérêt réel ; un clic sur WhatsApp ne prouve pas qu'un message a été envoyé ; un clic vers un site tiers ne confirme ni candidature ni recrutement. Les rapports doivent utiliser des libellés qui reflètent ces limites.

**Confidentialité :** collecter uniquement ce qui est nécessaire pour l'analyse, limiter les données identifiantes et appliquer les obligations de confidentialité pertinentes.

### M7 — Administration, accès et permissions

**Mission :** fournir un espace protégé pour gérer le contenu et les opérations de la plateforme.

**MVP :** un rôle principal d'administrateur pouvant créer et modifier les offres, contrôler les soumissions, gérer les signalements et consulter les statistiques de base. L'espace d'administration n'est pas accessible au public.

**Évolution :** séparer les rôles de collecteur, modérateur, éditeur, responsable de vérification et administrateur technique si l'équipe grandit. Le principe du moindre privilège devra être appliqué : chaque rôle ne reçoit que les droits nécessaires.

**Sécurité minimale :** authentification sûre, protection des routes d'administration, validation des entrées, gestion des erreurs, limitation des tentatives abusives et sauvegardes adaptées à l'environnement retenu. Les choix techniques détaillés seront traités dans le document d'architecture technique.

### M8 — Services candidats (hors MVP, à réévaluer)

Fonctions envisageables si un besoin est démontré : inscription facultative aux alertes, choix de villes et métiers, favoris, préférences de notification et éventuellement compte candidat.

Ces fonctions ne doivent pas devenir un prérequis pour consulter les offres ou contacter un employeur. Les alertes devront reposer sur un consentement clair et inclure un moyen de se désabonner.

### M9 — Services employeurs (hors MVP, sauf formulaire de soumission)

Le MVP permet seulement de proposer une annonce via un formulaire, avec contrôle éditorial avant publication. Il ne prévoit pas encore un compte employeur complet.

Une version future pourrait intégrer : compte vérifié, gestion de ses propres annonces, modification ou clôture d'offre, statistiques et options de visibilité. Il faudra alors définir comment vérifier l'autorisation d'une personne à représenter un employeur et comment traiter les annonces frauduleuses ou contestées.

## 5. Rôles et capacités

| Rôle | Capacités dans le MVP | Statut |
|---|---|---|
| Visiteur public | Consulter, rechercher, partager, ouvrir un canal de candidature, signaler | Inclus |
| Administrateur | Collecter, créer, modifier, contrôler, publier, fermer/archiver les offres, traiter les signalements et consulter les statistiques de base | Inclus |
| Employeur / contributeur externe | Soumettre une annonce via formulaire, sans publication automatique | Inclus sous forme limitée |
| Modérateur séparé | Examiner signalements et contrôler certains contenus avec des permissions limitées | Évolution si besoin |
| Candidat inscrit | Alertes, favoris et préférences | Hors MVP |
| Employeur inscrit | Gérer ses annonces et consulter des statistiques | Hors MVP |

## 6. Flux métier principaux

### 6.1 Offre collectée manuellement

1. L'administrateur trouve une annonce sur une source.
2. Il crée un brouillon et enregistre la provenance et la date de collecte.
3. Il structure l'annonce sans inventer d'information manquante.
4. Il effectue les contrôles possibles et choisit les marqueurs justifiés.
5. Il prévisualise, puis publie si le contenu répond aux règles.
6. L'offre apparaît dans le catalogue et reçoit une URL publique.
7. Les interactions de base sont mesurées.
8. Selon son ancienneté, les signalements ou les informations de la source, l'offre est actualisée, fermée ou archivée.

### 6.2 Offre soumise par un employeur ou un tiers

1. Le contributeur remplit le formulaire.
2. Le système valide les champs obligatoires et enregistre la soumission en attente.
3. L'administrateur examine le contenu, la source, les coordonnées et les risques apparents.
4. Il demande éventuellement une clarification par un canal disponible.
5. Il publie, refuse ou demande une correction.
6. Si publiée, l'offre rejoint exactement le même catalogue que les offres collectées manuellement.

### 6.3 Parcours du visiteur

1. Le visiteur arrive directement sur le site, par un lien partagé, un moteur de recherche ou un partenaire.
2. Il consulte les offres récentes ou lance une recherche.
3. Il ouvre une fiche, vérifie les informations disponibles et lit les modalités de candidature.
4. Il contacte l'employeur ou suit la procédure indiquée.
5. Il peut partager l'offre ou signaler un problème.
6. La plateforme enregistre les événements de mesure de base définis pour le MVP.

### 6.4 Traitement d'un signalement

1. Le visiteur sélectionne un motif et peut fournir une précision facultative.
2. Le signalement est enregistré pour contrôle.
3. L'administrateur examine les éléments disponibles.
4. Il maintient, corrige, actualise, suspend ou ferme l'annonce.
5. Les modifications importantes sont tracées à des fins opérationnelles.

## 7. Interfaces et frontières entre les modules

Pour éviter les incohérences pendant le développement :

- le **catalogue public** ne décide pas lui-même qu'une annonce est vérifiée ; il affiche les statuts fournis par la gestion éditoriale et le contrôle ;
- le **module de collecte** enregistre la source mais ne rend pas l'offre publique automatiquement ;
- le **module de contrôle** attribue des marqueurs de vérification selon des actions réalisées ;
- la **gestion éditoriale** gouverne la visibilité et le cycle de vie de l'offre ;
- la **diffusion** n'envoie que des liens vers des offres publiées ;
- les **statistiques** enregistrent des événements et ne modifient pas l'état d'une offre ;
- le **formulaire externe** crée une soumission, pas directement une offre publiée.

Ces responsabilités peuvent être implémentées dans une seule application et une seule base de données au départ. La séparation est fonctionnelle : elle ne signifie pas qu'il faut construire plusieurs services techniques indépendants.

## 8. Périmètre de réalisation

### Inclus dans le MVP

- M1 Découverte publique — fonctions essentielles ;
- M2 Collecte manuelle et formulaire public de soumission ;
- M3 Cycle de vie éditorial ;
- M4 Statuts de contrôle et signalement simple ;
- M5 URL publique, liens de candidature et partage ;
- M6 Mesures simples ;
- M7 Administration à rôle unique.

### Préparé dans la conception, mais non développé au départ

- M8 Comptes candidats, favoris et alertes personnalisées ;
- M9 Espace employeur complet ;
- automatisation de collecte et de diffusion ;
- système de paiement et offres sponsorisées ;
- matching par IA, présélection et ATS ;
- expansion multi-pays avec règles locales adaptées.

### Non décidé à ce stade

- nom et identité de marque ;
- ville pilote définitive ;
- politique exacte d'ancienneté et de reconfirmation des annonces ;
- critères détaillés de vérification d'employeur et de disponibilité ;
- durée de conservation des offres et des événements analytiques ;
- stack technique, hébergement et budget.

## 9. Exigences transversales

- Le site doit être utilisable sur smartphone avec un chargement raisonnable sur des connexions modestes.
- Le contenu public doit rester lisible et les actions importantes ne doivent pas dépendre de la création d'un compte.
- Chaque offre publique doit avoir une URL stable et un état de publication cohérent.
- Les erreurs dans les formulaires doivent être compréhensibles et ne doivent pas faire perdre inutilement les données saisies.
- Les permissions de l'administration doivent être contrôlées côté serveur, pas seulement par masquage visuel.
- Les coordonnées d'un employeur ne doivent être exposées que lorsqu'elles sont destinées à la candidature ou à la prise de contact pour cette offre.
- Les annonces fermées ne doivent pas continuer à apparaître comme des opportunités actives dans la recherche.
- Les changements de statut et les corrections importantes doivent rester traçables.
- Le système doit pouvoir exporter ou sauvegarder les données essentielles pour éviter une dépendance irréversible à un outil de développement.

## 10. Critères d'acceptation fonctionnels de l'architecture

L'architecture sera suffisamment définie pour passer à la conception de données lorsque les points suivants sont clairs :

1. Chaque module possède un périmètre et une responsabilité identifiables.
2. La distinction entre source, offre, statut de publication, disponibilité et contrôles de confiance est explicite.
3. Les flux des offres collectées et des offres soumises aboutissent au même catalogue après contrôle.
4. Les rôles et permissions du MVP sont connus.
5. Les parcours de collecte, publication, consultation, signalement et retrait sont décrits sans étape manquante.
6. Le périmètre MVP est séparé des évolutions futures.
7. Les questions encore ouvertes sont listées comme décisions à prendre, pas codées implicitement.

## 11. Décisions à prendre avant la phase suivante

Les décisions suivantes peuvent être discutées pendant la revue de cette architecture :

- faut-il inclure toutes les missions et tous les emplois informels dès le lancement, ou démarrer avec une sélection plus limitée ?
- le formulaire de soumission doit-il être ouvert à tous avec contrôle obligatoire, ou réservé aux employeurs identifiables ?
- quelle ancienneté déclenche le statut « à actualiser » ?
- une annonce dont la disponibilité n'est pas confirmée peut-elle être publiée avec avertissement, et sous quelles conditions ?
- quelles sources sont acceptées au lancement et lesquelles nécessitent une autorisation préalable ?
- faut-il séparer dès le départ les données analytiques de l'identité des visiteurs ?

## 12. Étape suivante

Après revue et validation de cette architecture fonctionnelle, le livrable suivant sera le **modèle conceptuel de données** : objets principaux, attributs, relations, règles d'unicité et états possibles. Il sera ensuite possible de dessiner les parcours et les maquettes, puis d'arrêter la stack technique en connaissance de cause.
