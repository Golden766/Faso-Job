# Spécification des écrans et wireframes fonctionnels

**Plateforme d’opportunités professionnelles — version 0.2**

- **Date :** 14 octobre 2026
- **Statut :** Document de travail à valider avant conception visuelle et développement
- **Références :** Spécification générale v0.1 ; architecture fonctionnelle v0.1 ; modèle conceptuel de données v0.1 ; parcours utilisateurs et arborescence v0.1

> Document fonctionnel à valider. Les wireframes sont basse fidélité et n’imposent pas la stack technique ni le design visuel définitif.

## 1. Objectif et périmètre

Ce document transforme les parcours et l’arborescence en spécifications d’écrans. Pour chaque écran, il décrit l’objectif, les zones, les informations, les actions, les états à gérer et les règles fonctionnelles. Les wireframes sont volontairement simples : ils décrivent la hiérarchie et le comportement, pas l’identité visuelle finale.

Le périmètre est le MVP : consultation publique sans compte, collecte manuelle, soumission publique contrôlée, gestion éditoriale, contrôle des sources, signalement et statistiques élémentaires. Les comptes candidats, l’espace employeur complet, les paiements, le matching et les candidatures internes restent hors périmètre.

> **Principe directeur :** Nous détaillons le comportement attendu, sans figer dès maintenant les couleurs, les polices, la stack technique ou le design final. Toute règle qui reste incertaine est signalée comme provisoire.

## 2. Principes communs d’interface

- Mobile d’abord : l’expérience doit être confortable sur un petit écran et ne pas dépendre d’une navigation complexe.
- Consultation sans compte : aucune inscription n’est nécessaire pour rechercher une offre, lire sa fiche ou contacter le recruteur.
- Transparence : la source, la date de collecte et les contrôles réalisés sont présentés sans exagérer ce qui a réellement été vérifié.
- Aucune invention : les informations absentes restent indiquées comme « Non précisé » lorsque cela aide à comprendre l’offre, ou sont omises si elles ne sont pas utiles.
- Actions principales explicites : « Voir l’offre », « Contacter / Postuler », « Soumettre une offre » et « Signaler » doivent être faciles à distinguer.
- États prévus : chargement, résultat vide, erreur, offre fermée, soumission réussie et validation de formulaire.
- Accessibilité : libellés visibles, navigation au clavier, contraste suffisant, focus identifiable et erreurs associées aux champs concernés.
- Pas de métriques trompeuses : un clic sortant n’est jamais présenté comme une candidature ou un recrutement confirmé.

## 3. Cartographie des écrans du MVP

| ID | Écran | Route indicative | Priorité |
| --- | --- | --- | --- |
| P01 | Accueil | / | MVP |
| P02 | Catalogue et résultats | /offres | MVP |
| P03 | Fiche d’offre | /offres/:slug | MVP |
| P04 | Soumettre une offre | /soumettre-une-offre | MVP |
| P05 | Confirmation de soumission | /soumettre-une-offre/confirmation | MVP |
| P06 | Signaler une offre | /offres/:slug/signaler | MVP |
| P07 | Pages d’information | /a-propos, /methode-de-verification, /contact, etc. | MVP |
| A01 | Connexion administration | /admin/connexion | MVP |
| A02 | Tableau de bord | /admin | MVP |
| A03 | Liste des offres | /admin/offres | MVP |
| A04 | Créer / modifier une offre | /admin/offres/nouvelle et /admin/offres/:id | MVP |
| A05 | Détail / contrôle d’une offre | /admin/offres/:id | MVP |
| A06 | File des soumissions | /admin/soumissions | MVP |
| A07 | Examen d’une soumission | /admin/soumissions/:id | MVP |
| A08 | File des signalements | /admin/signalements | MVP |
| A09 | Statistiques simples | /admin/statistiques | MVP |

Les chemins sont indicatifs. A04 et A05 peuvent former une seule page d’édition organisée en sections ; l’objectif est de séparer la création du contenu de la revue des contrôles, pas d’imposer deux implémentations.

## 4. Structure commune des pages publiques

Toutes les pages publiques partagent un cadre cohérent. Il doit rester léger et ne pas concurrencer le contenu des offres.

```text
┌───────────────────────────────────────────────────────────┐
│ Logo / nom du site              Offres   Soumettre une offre│
├───────────────────────────────────────────────────────────┤
│                     CONTENU DE LA PAGE                     │
│                                                           │
├───────────────────────────────────────────────────────────┤
│ À propos | Vérification | Contact | Confidentialité        │
│ Conditions d’utilisation                         © année  │
└───────────────────────────────────────────────────────────┘
```

- En-tête : logo ou nom du service, accès au catalogue et lien « Soumettre une offre ». Sur mobile, les liens peuvent être regroupés dans un menu simple, mais le catalogue doit rester facile à atteindre.
- Zone principale : titre de page clair, contenu prioritaire et action principale.
- Pied de page : méthode de vérification, à propos, contact, confidentialité et conditions d’utilisation.
- Le nom et l’identité visuelle sont provisoires ; le composant doit pouvoir accueillir la future marque sans modifier la structure fonctionnelle.

## 5. P01 — Accueil

Objectif : aider le visiteur à commencer immédiatement sa recherche, montrer que le catalogue contient des opportunités récentes et orienter les contributeurs vers la soumission d’une offre.

```text
┌────────────────────────────────────────────────────────┐
│ Logo                         Offres   Soumettre une offre│
├────────────────────────────────────────────────────────┤
│ Trouvez des opportunités professionnelles               │
│ [ Métier, mot-clé                         ] [Rechercher] │
│ Ville [Toutes ▼]      Type [Tous ▼]                     │
├────────────────────────────────────────────────────────┤
│ Offres récemment publiées                    [Tout voir]│
│ ┌────────────────────────────────────────────────────┐ │
│ │ Poste · Ville · type / salaire si connu            │ │
│ │ Source / statut de contrôle · date                 │ │
│ │                                        [Voir l’offre]│ │
│ └────────────────────────────────────────────────────┘ │
│                      ...                               │
├────────────────────────────────────────────────────────┤
│ Vous avez une offre à partager ? [Soumettre une offre] │
├────────────────────────────────────────────────────────┤
│ Comment nous contrôlons les offres | liens utiles      │
└────────────────────────────────────────────────────────┘
```

| Zone | Contenu et comportement |
| --- | --- |
| En-tête | Logo, lien catalogue, lien de soumission. |
| Recherche principale | Champ mot-clé ; filtre ville ; filtre type si les valeurs sont disponibles. Le bouton lance la recherche et conduit au catalogue avec les critères transmis. |
| Offres récentes | Afficher uniquement les offres publiées et admissibles à la visibilité publique. Trier par date de publication décroissante, sauf règle future validée. |
| Carte d’offre résumée | Intitulé, ville, type, salaire si renseigné, date de publication, source/contrôle en libellé mesuré, lien vers la fiche. |
| Appel à contribution | Un bloc bref invite à soumettre une annonce et précise qu’elle sera contrôlée avant publication. |
| Pied de page | Liens vers méthode de vérification, contact et informations légales. |

États à prévoir :

- Aucune offre publiée : expliquer que le catalogue se remplit et proposer d’élargir la recherche ou de revenir plus tard ; ne pas afficher de cartes fictives.
- Erreur de chargement : conserver le cadre et afficher un message compréhensible avec une action de réessai si elle est disponible.
- Offre récente mais à actualiser : ne pas la présenter comme confirmée ; afficher son statut de disponibilité conformément aux règles métier.

## 6. P02 — Catalogue et résultats de recherche

Objectif : permettre de parcourir et filtrer les opportunités disponibles, sans exiger de compte et sans créer l’impression que tous les critères seront renseignés pour chaque offre.

```text
┌───────────────────────────────────────────────────────────┐
│ Offres d’emploi et opportunités                            │
│ [Rechercher un métier, un mot-clé                 ] [Go]   │
│ Ville [Toutes ▼] Type [Tous ▼] Catégorie [Toutes ▼]        │
│ Salaire min [____]  Expérience [Toutes ▼]  [Effacer]       │
├───────────────────────────────────────────────────────────┤
│ 36 offres trouvées                         Trier : Récentes│
│ ┌──────────────────────────────┐ ┌───────────────────────┐│
│ │ Poste                         │ │ Filtres supplémentaires││
│ │ Ville · Type                  │ │ (mobile : panneau)    ││
│ │ Salaire si connu              │ └───────────────────────┘│
│ │ Source / date / statut        │                         │
│ │                         [Voir]│                         │
│ └──────────────────────────────┘                         │
│ [Précédent]                 Page 1 / N          [Suivant]  │
└───────────────────────────────────────────────────────────┘
```

| Élément | Comportement attendu |
| --- | --- |
| Recherche texte | Recherche sur l’intitulé, la description et les métiers/compétences associés lorsque ces champs existent. |
| Filtres | Ville ; catégorie/métier ; type d’opportunité ; salaire minimum si la donnée est disponible ; expérience si elle est structurée. Le MVP ne doit pas exposer des filtres impossibles à alimenter. |
| Tri | Par défaut, plus récemment publiée en premier. Les autres tris sont facultatifs au MVP. |
| Résultats | Cartes cohérentes, lien vers la fiche et indication des informations essentielles. L’absence de salaire ou de contrat ne doit pas empêcher l’affichage. |
| Filtres appliqués | Les critères actifs doivent être visibles et faciles à retirer individuellement ou via « Effacer les filtres ». |
| Pagination | Préférer une pagination ou un chargement progressif maîtrisé plutôt qu’une page très longue ; choix technique à définir plus tard. |
| URL | Les critères de recherche devraient être partageables au moyen de paramètres d’URL, pour permettre le retour arrière et le partage d’une recherche. |

États à prévoir :

- Aucun résultat : afficher les critères en cours et proposer de les élargir ou de les effacer.
- Filtre non disponible : ne pas l’afficher ou le désactiver avec une explication uniquement si cela aide réellement.
- Chargement et erreur : indiquer l’état sans effacer inutilement les critères saisis.
- Résultat fermé : une offre fermée ne doit jamais être présentée comme une opportunité active. Elle ne doit pas apparaître dans la liste active.

## 7. P03 — Fiche détaillée d’une offre

Objectif : permettre au visiteur de comprendre le poste, de juger les informations disponibles, de voir d’où vient l’annonce et de choisir la bonne modalité de candidature.

```text
┌───────────────────────────────────────────────────────────┐
│ ← Retour aux offres                                        │
│ ┌──────────────── CARTE : EN-TÊTE ──────────────────────┐  │
│ │ Intitulé · ville · type · statuts de contrôle         │  │
│ └───────────────────────────────────────────────────────┘  │
│ ┌────────── CARTE : INFORMATIONS ESSENTIELLES ──────────┐  │
│ │ Salaire · lieu · type · expérience · date limite      │  │
│ └───────────────────────────────────────────────────────┘  │
│ ┌──────────── CARTE : À PROPOS DU POSTE ────────────────┐  │
│ │ Missions · profil recherché · conditions connues      │  │
│ └───────────────────────────────────────────────────────┘  │
│ ┌────────── CARTE : SOURCE ET VÉRIFICATIONS ────────────┐  │
│ │ Source · date de collecte · statuts factuels         │  │
│ └───────────────────────────────────────────────────────┘  │
│ ┌────────────── CARTE : CANDIDATURE ────────────────────┐  │
│ │ [WhatsApp + « Postuler sur WhatsApp »] OU [Postuler]  │  │
│ │ [Consulter l’annonce source]                           │  │
│ └───────────────────────────────────────────────────────┘  │
│ ┌────────────── CARTE : SIGNALEMENT ────────────────────┐  │
│ │ Signaler une annonce expirée, suspecte ou inexacte    │  │
│ └───────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
```

| Zone | Règles |
| --- | --- |
| Organisation en cartes | Regrouper les sections dans des cartes distinctes : en-tête, informations essentielles, description/profil, source/vérifications, candidature et signalement. Toutes les informations descriptives de la fiche doivent appartenir à une carte. |
| En-tête d’offre | Intitulé, ville, type d’emploi, salaire/expérience si disponibles. Ne pas fabriquer un niveau de compatibilité ou un score de confiance. |
| Disponibilité | Afficher un état compréhensible : confirmée ouverte, non confirmée/à vérifier, fermée. Le libellé exact sera aligné avec les règles de gestion. |
| Action de candidature | Si le canal est WhatsApp, afficher le pictogramme WhatsApp avec le libellé « Postuler sur WhatsApp ». Pour tout autre canal connu, afficher « Postuler » et ouvrir le canal ou les instructions appropriées (site externe, email, appel, dépôt physique). Une seule variante principale est affichée à la fois. Si aucune modalité exploitable n’est connue, ne pas inventer de destination ; proposer la source lorsque c’est possible. |
| Contenu | Description, missions, profil demandé et conditions connues. Les sections vides sont omises ou affichent « Non précisé » selon leur importance. |
| Provenance | Nom/type de la source, date de collecte, lien de retour lorsqu’il est disponible et approprié, plus statuts de contrôle factuels. |
| Partage | Partager le lien de la fiche. Les textes générés pour les réseaux sociaux peuvent venir plus tard ; au MVP, partage natif ou copie du lien suffit. |
| Signalement | Ouvre le formulaire associé à l’offre et transmet son identifiant ; le visiteur n’a pas besoin de compte. |

Comportement pour une offre fermée consultée depuis un ancien lien : afficher clairement qu’elle n’est plus active, désactiver l’action de candidature si elle n’a plus de sens et proposer un retour au catalogue des offres actives.

## 8. P04 — Formulaire public de soumission d’une offre

Objectif : permettre à un employeur ou à un tiers autorisé de proposer une annonce sans créer de compte. Le formulaire ne publie jamais directement l’offre : il crée une soumission en attente de contrôle.

```text
┌───────────────────────────────────────────────────────────┐
│ Soumettre une offre                                        │
│ Les annonces sont examinées avant leur publication.        │
├───────────────────────────────────────────────────────────┤
│ INFORMATIONS SUR LE POSTE                                  │
│ Intitulé *           [____________________________]         │
│ Ville *              [____________________________]         │
│ Type d’emploi        [Choisir… ▼]                           │
│ Description *        [____________________________]         │
│ Salaire              [________] à [________] FCFA           │
│ Date limite          [____/____/______]                     │
├───────────────────────────────────────────────────────────┤
│ CANDIDATURE                                                │
│ Mode *               [WhatsApp / téléphone / email / ...]  │
│ Coordonnée / URL     [____________________________]         │
│ Instructions         [____________________________]         │
├───────────────────────────────────────────────────────────┤
│ SOURCE ET CONTACT POUR SUIVI                               │
│ Employeur/recruteur  [____________________________]         │
│ Source ou URL        [____________________________]         │
│ Contact du soumetteur[____________________________]         │
│ [ ] Je suis autorisé à soumettre ces informations          │
│ [ ] J’atteste leur exactitude à ma connaissance            │
│                                      [Envoyer la soumission]│
└───────────────────────────────────────────────────────────┘
```

Champs pressentis, à valider dans le modèle de données :

| Groupe | Champs requis / facultatifs |
| --- | --- |
| Poste | Intitulé, ville/lieu et description : requis. Type, salaire, expérience, niveau d’études, contrat et date limite : facultatifs si l’annonce originale ne les fournit pas. |
| Candidature | Mode de candidature requis ; coordonnée, URL ou instructions requises selon le mode choisi. |
| Provenance | Nom de l’employeur/recruteur et URL de la source si disponible. Si le soumetteur représente l’employeur, il le précise. |
| Contact de suivi | Au moins un moyen de joindre le soumetteur pour clarification. Ce contact ne doit pas être affiché automatiquement sur la fiche publique. |
| Déclarations | Confirmation d’autorisation à soumettre l’annonce et d’exactitude à la connaissance du soumetteur ; avis de confidentialité avant envoi. |
| Protection anti-abus | Validation côté serveur, limitation d’envois répétitifs et mécanisme anti-spam proportionné. Solution technique à décider plus tard. |

Règles de formulaire :

- Indiquer clairement les champs obligatoires et pourquoi les informations de contact sont demandées.
- Adapter les champs de candidature au choix du canal : par exemple, URL pour un site externe, numéro pour WhatsApp/téléphone, adresse ou consigne pour un dépôt physique.
- Valider les formats sans empêcher les formats légitimes locaux ; afficher les erreurs près des champs concernés.
- Ne pas demander une pièce d’identité ou des documents personnels du recruteur au MVP, sauf exigence future justifiée et encadrée.
- À l’envoi, créer une soumission en attente et rediriger vers l’écran de confirmation. En cas d’échec, préserver autant que possible les données déjà saisies.

## 9. P05 — Confirmation de soumission

Objectif : confirmer la réception et expliquer ce qui se passe ensuite, sans promettre une date de publication ni laisser croire que l’offre est déjà visible.

```text
┌─────────────────────────────────────────────────────┐
│                  ✓                                  │
│ Merci, votre annonce a bien été transmise.           │
│ Elle doit être examinée avant toute publication.     │
│ Nous pourrons vous contacter si une précision est   │
│ nécessaire.                                          │
│ [Retour au catalogue]     [Soumettre une autre offre]│
└─────────────────────────────────────────────────────┘
```

Ne pas afficher publiquement l’identifiant interne de soumission ni les données personnelles du soumetteur. Les liens vers « Retour au catalogue » et « Soumettre une autre offre » sont les actions principales.

## 10. P06 — Signaler une offre

Objectif : permettre au visiteur de transmettre un problème précis avec un minimum de friction, sans devoir s’inscrire.

```text
┌──────────────────────────────────────────────────────┐
│ Signaler l’offre : [Intitulé du poste]                │
│ Pourquoi la signalez-vous ? *                         │
│ ( ) Offre expirée ou poste pourvu                     │
│ ( ) Informations inexactes                            │
│ ( ) Contact injoignable                               │
│ ( ) Offre suspecte / possible fraude                  │
│ ( ) Autre                                             │
│ Précisions (facultatif)                               │
│ [_______________________________________________]     │
│ Contact pour suivi (facultatif, si nécessaire)        │
│ [_______________________________________________]     │
│ [Envoyer le signalement] [Annuler]                     │
└──────────────────────────────────────────────────────┘
```

- L’identifiant de l’offre est transmis automatiquement ; le visiteur ne doit pas le saisir.
- Le formulaire n’exige pas de compte. Les coordonnées du déclarant sont facultatives sauf nécessité opérationnelle clairement expliquée.
- Après envoi, afficher un accusé de réception. Ne pas promettre un délai de traitement ni une suppression automatique.
- Côté administration, le signalement est ajouté à une file de contrôle et relié à l’offre concernée.
- Prévoir une protection anti-spam et limiter la collecte de renseignements sensibles.

## 11. P07 — Pages d’information

| Page | Contenu fonctionnel |
| --- | --- |
| À propos | Rôle du service, zone couverte au lancement, principe de centralisation des opportunités et limites du service. |
| Méthode de vérification | Définition compréhensible de « source retrouvée », « employeur vérifié », « disponibilité confirmée » et des limites de ces contrôles. |
| Contact | Canal de contact du gestionnaire, motif du message si un formulaire est utilisé, avertissement de ne pas envoyer de documents sensibles inutiles. |
| Confidentialité | Informations sur les données collectées, finalités, conservation, droits et canal pour les demandes. Contenu juridique à faire vérifier avant lancement. |
| Conditions d’utilisation | Règles de publication, interdiction des annonces frauduleuses, droits de retrait/correction, limites de responsabilité et usages interdits. Texte final à valider juridiquement. |

Ces pages sont simples, mais elles contribuent à la transparence. Les textes juridiques définitifs ne doivent pas être improvisés uniquement par l’IA sans revue adaptée au contexte burkinabè.

## 12. A01 — Connexion à l’administration

```text
┌───────────────────────────────────────────────┐
│ Administration                                 │
│ Connectez-vous pour gérer les offres.          │
│ Email / identifiant [_______________________]  │
│ Mot de passe       [_______________________]  │
│                       [Se connecter]           │
│ Erreur éventuelle visible près du formulaire   │
└───────────────────────────────────────────────┘
```

- Aucun lien d’inscription public à l’administration.
- Les messages d’erreur ne doivent pas révéler si un identifiant existe ; les détails techniques ne sont pas affichés.
- Prévoir la limitation des tentatives, une gestion sûre de la session et une déconnexion explicite.
- L’authentification et les permissions doivent être contrôlées côté serveur.

## 13. Cadre commun de l’administration

Les écrans d’administration partagent une navigation interne, protégée et distincte de l’espace public.

```text
┌────────────────────────────────────────────────────────────┐
│ Administration   [Tableau de bord] [Offres] [Soumissions]   │
│                                  [Signalements] [Stats]      │
├────────────────────────────────────────────────────────────┤
│ Titre de l’écran                     Actions principales    │
├────────────────────────────────────────────────────────────┤
│ Contenu : filtres, tableau/liste, formulaire ou détail      │
└────────────────────────────────────────────────────────────┘
```

Au MVP, un seul rôle d’administrateur suffit. Le menu peut inclure une déconnexion. Les rôles spécialisés et la matrice de permissions détaillée sont différés, mais toutes les routes d’administration doivent être protégées.

## 14. A02 — Tableau de bord administration

Objectif : aider l’administrateur à décider quoi traiter en premier, sans devenir un tableau de bord analytique complexe.

```text
┌───────────────────────────────────────────────────────────┐
│ Tableau de bord                             [Nouvelle offre]│
├───────────────────────────────────────────────────────────┤
│ Offres actives | À actualiser | Soumissions | Signalements │
├───────────────────────────────────────────────────────────┤
│ À traiter en priorité                                      │
│ • Soumissions en attente                         [Examiner] │
│ • Signalements à examiner                       [Examiner] │
│ • Offres à actualiser                           [Consulter]│
├───────────────────────────────────────────────────────────┤
│ Activité récente / raccourcis                              │
└───────────────────────────────────────────────────────────┘
```

- Afficher des comptes calculés à partir des données internes et rendre chaque compteur cliquable vers la liste correspondante.
- Prioriser les actions opérationnelles : soumissions, signalements et offres à actualiser.
- Ne pas afficher de chiffres d’exemple en production ; un état vide doit expliquer qu’aucun élément n’est à traiter.
- Le raccourci « Nouvelle offre » ouvre la création d’une collecte manuelle.

## 15. A03 — Liste et recherche interne des offres

```text
┌─────────────────────────────────────────────────────────────┐
│ Offres                                  [+ Nouvelle offre]   │
│ [Rechercher un titre ou identifiant] [Statut ▼] [Ville ▼]    │
├─────────────────────────────────────────────────────────────┤
│ Titre | Ville | Publication | Disponibilité | Contrôle | ⋯   │
│ ...                                                         │
│ Actions : Ouvrir / Modifier / Prévisualiser / Fermer / Archiver│
└─────────────────────────────────────────────────────────────┘
```

| Fonction | Comportement |
| --- | --- |
| Recherche | Rechercher par identifiant, titre, employeur ou texte clé si disponible. |
| Filtres | Statut de publication, disponibilité, ville, date et source si utile. |
| Actions | Ouvrir, modifier, prévisualiser, dépublier/fermer ou archiver selon les permissions et l’état actuel. |
| Confirmation | Les actions qui retirent une offre de la visibilité publique doivent demander confirmation et expliquer la conséquence. |
| États | Liste vide, aucune correspondance, chargement, erreur et pagination si nécessaire. |

## 16. A04/A05 — Créer, modifier et contrôler une offre

Cet écran est le principal outil de travail. Il doit séparer la rédaction du contenu, la provenance et les contrôles, afin qu’une donnée éditoriale ne soit pas confondue avec une preuve de vérification.

```text
┌────────────────────────────────────────────────────────────┐
│ Nouvelle offre / Modifier une offre                         │
├────────────────────────────────────────────────────────────┤
│ A. CONTENU PUBLIC                                            │
│ Intitulé * · ville * · type · description *                  │
│ missions · profil · salaire · expérience · date limite       │
├────────────────────────────────────────────────────────────┤
│ B. CANDIDATURE                                               │
│ Mode · numéro/URL/email · consignes · dépôt physique         │
├────────────────────────────────────────────────────────────┤
│ C. SOURCES (une ou plusieurs)                                │
│ Type · nom · lien · date originale · date de collecte        │
│ [+ Ajouter une source]                                       │
├────────────────────────────────────────────────────────────┤
│ D. CONTRÔLES                                                 │
│ Source retrouvée [ ] Employeur vérifié [ ]                   │
│ Disponibilité confirmée [ ] · date et note du contrôle       │
├────────────────────────────────────────────────────────────┤
│ E. PUBLICATION                                               │
│ Brouillon / À contrôler / Publiée / Fermée / Archivée        │
│ [Enregistrer] [Prévisualiser] [Publier] [Annuler]            │
└────────────────────────────────────────────────────────────┘
```

| Section | Règles |
| --- | --- |
| Contenu public | Saisir les informations utiles en distinguant données obligatoires des données facultatives. Ne jamais compléter par supposition une information absente. |
| Canal de candidature | Le type de canal pilote les champs requis. Un lien WhatsApp doit être normalisé/validé sans être présenté comme preuve d’identité. |
| Sources multiples | Une même offre peut référencer plusieurs sources. Ajouter une source ne doit pas nécessairement créer une deuxième offre. |
| Contrôles | Chaque marqueur est coché seulement après contrôle réel. Enregistrer la date et une note interne de vérification si nécessaire. |
| Publication | Le statut de publication est distinct de la disponibilité et des contrôles. Le système doit empêcher la publication si les champs minimums requis ne sont pas satisfaits. |
| Historique | Tracer les changements importants : publication, fermeture, contrôle et correction majeure. La politique exacte de conservation sera définie ultérieurement. |

Actions : enregistrer comme brouillon, prévisualiser la fiche publique, soumettre à contrôle, publier, fermer, archiver. Les actions affichées dépendent de l’état actuel. Pour le MVP, la même personne peut réaliser la collecte, le contrôle et la publication ; l’interface doit néanmoins conserver ces étapes distinctes.

## 17. A06/A07 — File des soumissions et examen

La file des soumissions ne doit pas être confondue avec le catalogue des offres : ce sont des propositions qui n’ont pas encore été acceptées.

```text
┌───────────────────────────────────────────────────────────┐
│ Soumissions en attente                                      │
│ Reçue le | Intitulé | Employeur | Source | État             │
│ [Ouvrir pour examen]                                        │
├───────────────────────────────────────────────────────────┤
│ DÉTAIL D’UNE SOUMISSION                                     │
│ Contenu soumis + coordonnées internes + déclarations        │
│ Vérifications / notes                                       │
│ [Créer offre et publier] [Demander correction] [Refuser]    │
└───────────────────────────────────────────────────────────┘
```

- Séparer les coordonnées du soumetteur des coordonnées publiques de candidature.
- Autoriser l’administrateur à demander une correction, refuser avec un motif interne ou accepter la soumission et la transformer en offre gérée dans le catalogue central.
- L’acceptation ne doit pas supprimer la traçabilité de l’origine : conserver le lien entre la soumission reçue et l’offre créée.
- Prévoir les états : en attente, en cours d’examen, correction demandée, acceptée/publiée, refusée, doublon/annulée.
- La communication au soumetteur peut rester manuelle au MVP ; ne pas promettre de notification automatisée tant qu’elle n’existe pas.

## 18. A08 — File des signalements

```text
┌─────────────────────────────────────────────────────────────┐
│ Signalements                                                 │
│ Date | Offre | Motif | Statut | [Examiner]                   │
├─────────────────────────────────────────────────────────────┤
│ Détail : offre + source + motif + précision                   │
│ Décision : maintenir / corriger / actualiser / suspendre /   │
│ fermer                                                       │
│ Note interne [________________________________________]      │
│ [Enregistrer la décision]                                    │
└─────────────────────────────────────────────────────────────┘
```

- États du signalement : nouveau, en cours, résolu, non retenu ; leur liste définitive peut être simplifiée selon les besoins opérationnels.
- Un signalement ne fait pas disparaître une offre automatiquement. Un administrateur peut néanmoins suspendre rapidement une annonce en cas de risque sérieux, selon une procédure à formaliser.
- La résolution enregistre l’action effectuée et une note proportionnée, sans conserver de données inutiles sur le déclarant.

## 19. A09 — Statistiques de base

Objectif : comprendre l’usage sans collecter plus de données que nécessaire. Cet écran n’est pas un outil d’analytics avancé.

```text
┌────────────────────────────────────────────────────────────┐
│ Statistiques                               Période [30 jours▼]│
├────────────────────────────────────────────────────────────┤
│ Pages d’offres vues | Clics sortants | Partages | Recherches│
├────────────────────────────────────────────────────────────┤
│ Offres les plus consultées                                  │
│ Offres avec le plus de clics sortants                       │
│ Termes de recherche fréquents (si disponibles et appropriés)│
└────────────────────────────────────────────────────────────┘
```

- Afficher la période observée et la définition des métriques.
- Distinguer vues de pages, clics sortants et partages. Ne jamais les appeler « candidatures ».
- Éviter les tableaux de bord très détaillés tant que le volume d’utilisation est faible.
- Les exigences de confidentialité, la durée de conservation et les outils exacts de mesure restent à définir dans la conception technique.

## 20. États transversaux et erreurs

| État | Attendu |
| --- | --- |
| Chargement | Indiquer qu’un contenu est en cours de chargement ; éviter les doubles soumissions sur formulaire. |
| Vide | Expliquer pourquoi aucun élément n’est affiché et proposer une action utile, sans inventer des résultats. |
| Erreur de validation | Identifier les champs concernés avec un message en langage simple ; conserver les saisies valides. |
| Erreur serveur | Afficher une erreur compréhensible et un moyen de réessayer ; ne pas exposer de détails techniques. |
| Accès interdit | Refuser l’accès aux pages d’administration sans session autorisée et proposer une connexion. |
| Offre fermée | Rendre le statut évident et désactiver les actions de candidature qui ne sont plus valables. |
| Lien externe indisponible | Informer l’utilisateur si le lien n’est plus disponible et proposer de revenir au catalogue ou de signaler le problème. |
| Action destructive | Demander confirmation avant fermeture, suppression ou action difficile à annuler. |

## 21. Règles responsive, accessibilité et contenu

- Sur petit écran, empiler les sections ; déplacer les filtres secondaires dans un panneau repliable sans cacher la recherche principale.
- Éviter les tableaux larges sur mobile ; utiliser des cartes ou une vue simplifiée dans l’administration.
- Les boutons doivent décrire l’action réelle (« Voir l’offre », « Ouvrir WhatsApp », « Envoyer le signalement »). Éviter les libellés vagues tels que « Cliquer ici ».
- Les icônes ne remplacent pas les libellés essentiels ; les champs ont un label associé et les erreurs sont annoncées de manière accessible.
- Les dates sont affichées dans un format compréhensible localement et les montants précisent la devise si elle est connue.
- Les annonces avec données incomplètes restent utilisables, mais leur fiche doit être honnête sur les informations manquantes.
- Prévoir des images sociales de partage ultérieurement, mais ne pas en faire un prérequis du MVP.

## 22. Critères d’acceptation des écrans

1. Le visiteur peut trouver et ouvrir une offre sans compte.
2. Le catalogue peut être utilisé avec ou sans filtres et reflète seulement les offres publiées et actives.
3. Une fiche explique la provenance et les contrôles effectués sans score de confiance non justifié.
4. Le bouton de candidature ne s’affiche que si le canal correspondant est connu et applicable.
5. Une soumission externe reste non publique jusqu’à approbation administrative.
6. L’administrateur peut créer, modifier, prévisualiser, publier, fermer et archiver une offre.
7. L’administrateur peut retrouver l’origine d’une annonce et traiter les signalements associés.
8. Les états vides, erreurs et offres fermées sont prévus et compréhensibles.
9. L’accès à chaque écran d’administration est protégé côté serveur.
10. Le site reste utilisable sur smartphone et dans des conditions de connexion modestes.

## 23. Décisions ouvertes avant le design visuel

| Décision | Proposition provisoire | Moment où trancher |
| --- | --- | --- |
| Présentation visuelle et statuts | Utiliser une mise en page sobre et des libellés textuels explicites, sans score global. | Avant les maquettes finales et pendant les wireframes détaillés. |
| Filtres exacts | N’exposer que les champs présents et suffisamment fiables dans les données. | Pendant la conception du formulaire de collecte et le modèle détaillé. |
| Pagination / chargement progressif | Prévoir un mécanisme adapté au catalogue, sans fixer la technique. | Pendant la conception technique et les tests de performance. |
| Anti-spam | Prévoir la protection du formulaire dès le lancement. | Détails à arrêter avec la stack technique. |
| Statistiques et confidentialité | Mesures agrégées minimales. | Avant implémentation de l’analytics et publication de la politique de confidentialité. |
| Textes juridiques | Pages prévues, contenu définitif à faire vérifier. | Avant mise en production. |

## 24. Étape suivante

Après revue de ces écrans et de leurs comportements, la prochaine étape sera de produire les wireframes visuels basse fidélité, d’abord pour l’accueil, le catalogue et la fiche d’offre, puis pour le tableau de bord et le formulaire d’administration. Les maquettes serviront ensuite de référence aux composants d’interface et à la planification du développement. La palette, les typographies et le style final seront décidés dans une phase de design dédiée.
