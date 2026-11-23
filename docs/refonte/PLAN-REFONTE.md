# Refonte Faso Job — plan de chantier

Ce document est la référence unique de la refonte. Il sert à savoir où on en est,
ce qui est décidé et ce qui reste à trancher. Une case ne se coche qu'après
validation du lot correspondant.

## 1. Décisions actées

- **Nom du site : Faso Job**
- **Sous-titre : Opportunités professionnelles au Burkina Faso**
- **Accueil distinct :** `/` devient la page d'accueil, le catalogue reste sur `/catalogue/`.
- **« Comment ça marche ? » :** page publique unique `/comment-ca-marche/`, qui
  regroupe le parcours de vérification, les 5 badges, les 4 lignes rouges et la FAQ.
- **« Contrôle des annonces » :** pointe vers `/comment-ca-marche/#controle-des-annonces`.
  Décision du 2026-11-10 : une page unique plutôt que deux pages concurrentes.
- **Périmètre : public d'abord**, puis administration.
- **Administration : Django Admin restylé**, pas de console sur mesure.
- **Liste noire, statistiques, paramètres et alertes : à implémenter**, après le public.
- **Polices : système** (`Segoe UI`, `system-ui`, fallback sans-serif). Pas de police web externe.
- **Icônes : SVG locales**, pas de police d'icônes.
- **Stack inchangée :** Django, templates Django, CSS natif. Pas de Tailwind, pas de framework frontend.
- **Méthode :** un lot à la fois, tests avant validation, migration Supabase après sauvegarde.
- **Assistant de découverte :** l'équipe ne doit plus trouver elle-même les
  sites à surveiller. Décidé le 2026-11-16 : un assistant propose des
  adresses, le code les vérifie, **l'équipe autorise chacune d'elles**.
  Une source n'est jamais collectée sans autorisation écrite.
- **Veille automatisée :** évolution assumée, décidée le 2026-11-16. La veille
  collecte des annonces sur des sources autorisées, les analyse et prépare des
  **brouillons**. Voir la section 9 et `docs/veille.md`.
  **La publication automatique reste interdite** : une annonce collectée
  n'est jamais publique sans une validation humaine explicite.

## 2. Principe de la refonte

Les fichiers du dossier `stitch_plateforme_opportunit_s_burkina_faso/` sont des
maquettes statiques générées avec Tailwind via CDN. Ils ne sont pas réutilisables
tels quels :

- classes Tailwind non installées dans le projet ;
- polices et icônes chargées depuis Google ;
- images hébergées en externe ;
- liens `href="#"` ;
- accents corrompus dans certains exports ;
- données inventées (chiffres, abonnés, montants).

On **réimplémente** la structure et le langage visuel en Django + CSS natif, avec
les vrais modèles et les vrais contenus. Aucune donnée de démonstration ne doit
apparaître en production.

## 3. Cartographie des écrans

### Public

| Écran maquette | Route / template cible | État actuel | Travail |
|---|---|---|---|
| Accueil desktop/mobile | `/` → `refonte/home.html` | fait (lot 1) | — |
| Catalogue desktop/mobile | `/catalogue/` → `refonte/catalogue.html` | existe (ancien design) | Refonte complète |
| Fiche d'offre desktop/mobile | `/offre/<slug>/` → `refonte/offer_detail.html` | existe (ancien design) | Refonte complète |
| Proposer une annonce desktop/mobile | `/proposer-une-annonce/` → `refonte/submit_offer.html` | existe (ancien design) | Refonte + champs |
| Signaler une arnaque desktop/mobile | `/signaler-une-arnaque/` + `/offre/<slug>/signaler/` | fait (lot 5) | — |
| Comment ça marche desktop/mobile | `/comment-ca-marche/` → `refonte/method.html` | fait (lot 6) | — |
| Contrôle des annonces | `/comment-ca-marche/#controle-des-annonces` | fait (lot 6) | Page unique avec la méthode |

### Administration

| Écran maquette | Route / template cible | État actuel | Travail |
|---|---|---|---|
| Tableau de bord | `/admin/` | fait (lot 7) | Restyle + vrais chiffres |
| Modération d'une annonce | `/admin/offres/offer/<id>/change/` | fait (lot 7) | Panneau de vérification |
| Offres en ligne | `/admin/offres/offer/` | fait (lot 7) | Colonnes, filtres, actions |
| Traitement des signalements | `/admin/offres/offerreport/` et `/admin/offres/fraudreport/` | fait (lot 7) | Modèle + admin |
| Liste noire et sécurité | `/admin/offres/blacklistedcontact/` | fait (lot 7) | Modèle + admin |
| Rapports et statistiques | `/admin/rapports/` | fait (lot 7) | Vue calculée + export |
| Paramètres plateforme | `/admin/parametres/` | fait (lot 7) | Modèle singleton + admin |

## 4. Lots de travail

### Lot 0 — Fondations et charte

- [x] Tokens CSS : couleurs, typographie, espacements, rayons, ombres.
- [x] Feuilles de style : base, composants, coquille publique.
- [x] Sprite SVG local et partial d'icône réutilisable.
- [x] Coquille `templates/refonte/base.html` : en-tête, navigation mobile, pied de page, messages.
- [x] Page interne `/styleguide/` visible uniquement en `DEBUG`.
- [x] Tests du styleguide (200 en DEBUG, 404 hors DEBUG).
- **Validation :** styleguide consultable, aucun asset externe, pages existantes intactes.
- **Validé le 2026-11-06 :** `manage.py check` OK, 38 tests OK, `/styleguide/`
  rendu sans erreur console, aucune ressource externe, `/`, `/catalogue/` et
  `/proposer-une-offre/` toujours en 200.

### Lot 1 — Accueil

- [x] Vue `home_view` et URL `/`.
- [x] Héros, recherche, types d'opportunités, dernières offres, parcours, transparence.
- [x] Navigation active et fil d'Ariane.
- **Validation :** recherche vers le catalogue, responsive, aucune donnée inventée.
- **Validé le 2026-11-06 :** 43 tests OK, `/` distinct de `/catalogue/`,
  recherche fonctionnelle, types et villes calculés depuis la base, aucun lien mort.
  Contrôle visuel fin des largeurs 360/390 px reporté à la recette (lot 9).

### Lot 2 — Catalogue

- [x] Desktop : résultats + filtres collants.
- [x] Mobile : recherche, filtres en `<dialog>`, onglets, cartes.
- [x] Carte d'offre complète et cliquable, échéance colorée.
- [x] Pagination et conservation des filtres.
- **Validation :** tests de filtres et de pagination au vert ; Lighthouse 1.0 en accessibilité, bonnes pratiques et SEO sur `/catalogue/`.

### Lot 3 — Fiche d'offre

- [x] En-tête, badges, informations clés.
- [x] Description unique et dossier de candidature (pas de champs structurés
  ajoutés).
- [x] Colonne de candidature et barre mobile conditionnelle.
- [x] Traçabilité et avertissement anti-fraude.
- **Validation :** canaux WhatsApp, e-mail, téléphone et dépôt physique inchangés.
- **Validé le 2026-11-09 :** 54 tests OK, `manage.py check` sans erreur.
  Lighthouse 1.0 accessibilité / bonnes pratiques / SEO sur `/`, `/catalogue/`,
  `/offre/agent-commercial/` et `/offre/informaticien/`. Partage du lien vérifié
  au clic réel (copie presse-papier + repli).

### Lot 4 — Proposer une annonce

- [x] Formulaire en cinq sections numérotées, champs requis et résumé d’erreurs.
- [x] Encart de vérification, rappel anti-fraude et confidentialité des coordonnées.
- [x] Champs backend : rôle du déclarant, engagement éthique, téléphone.
- **Validation :** soumission en attente, jamais publiée automatiquement.
- **Validé le 2026-11-09 :** 63 tests OK, `manage.py check` sans erreur.
  Migration `0007` appliquée après sauvegarde des données
  (`backups/fasojob-2026-11-09-raw.json`). Lighthouse 1.0 accessibilité /
  bonnes pratiques / SEO sur le formulaire, y compris avec erreurs affichées.

### Lot 5 — Signaler une arnaque

- [x] Page globale et lien prérempli depuis une offre.
- [x] Modèle de signalement de fraude, preuve jointe, configuration `MEDIA`.
- [x] Admin de traitement.
- **Validation :** aucun changement automatique du statut d'une offre.
- **Validé le 2026-11-10 :** 77 tests OK, `manage.py check` sans erreur,
  `makemigrations --check` sans changement. Motifs et canaux codés (migration
  `0008`), anciens libellés convertis (migration `0009`), sauvegarde préalable
  dans `backups/fasojob-2026-11-09-lot5-before.json`. Preuve limitée à 5 Mo
  (PNG, JPG, WEBP, PDF) et jamais servie publiquement : téléchargement réservé
  au personnel via `/admin/signalements/<pk>/preuve/`. Lighthouse 1.0 / 1.0 /
  1.0 sur la page globale et sur la page liée à une offre. Captures :
  `docs/refonte/captures/lot5-signaler-desktop.png` et
  `lot5-signaler-mobile.png`.

### Lot 6 — Comment ça marche

- [x] Parcours en 4 étapes, 5 badges, 4 lignes rouges, FAQ.
- [x] Page unique `/comment-ca-marche/` et navigation mise à jour (en-tête,
  menu mobile, barre inférieure, pied de page).
- **Validation :** contenu relu, aucune promesse non tenue.
- **Validé le 2026-11-10 :** 85 tests OK, `manage.py check` sans erreur,
  `makemigrations --check` sans changement. Aucune statistique, aucun délai ni
  numéro inventé ; les badges reprennent exactement les libellés de la fiche
  d’offre. Lighthouse 1.0 / 1.0 / 1.0 sur `/comment-ca-marche/`. Captures :
  `docs/refonte/captures/lot6-methode-desktop.png` et
  `lot6-methode-mobile.png`.

### Lot 7 — Admin restylé

- [x] CSS admin aligné sur la charte.
- [x] Tableau de bord, offres, modération, soumissions, signalements.
- [x] Liste noire et paramètres.
- [x] Rapport d'activité + export CSV.
- **Validation :** tests de rôles et de permissions au vert.

> Le lot 7 livre le **registre** de la liste noire et l'**écran** de paramètres.
> Le lot 8 ajoute le **croisement automatique** entre la liste noire et les
> offres, et les comportements pilotés par les paramètres (filtres,
> quarantaine, archivage). Voir § 7.

### Lot 8 — Fonctions avancées

- [x] Liste noire et croisement automatique.
- [x] Paramètres plateforme.
- [x] Filtres de mots-clés et quarantaine.
- [x] Archivage automatique des offres expirées.
- [x] Statistiques et export.
- [x] Compteur de vues.
- [x] Notifications e-mail.
- [x] Adaptateurs WhatsApp / SMS.
- [x] Double authentification.
- [x] Sauvegardes automatiques.

> **Croisement automatique.** Depuis le 2026-11-13, chaque offre et
> chaque proposition sont croisees avec la liste noire des leur creation, et
> inscrire un contact signale aussitot les annonces deja publiees qui
> utilisent ses coordonnees. Un contact **bloque definitivement** ne peut
> jamais etre publie ; un contact **sous surveillance** bloque la
> publication tant qu un controle humain n est pas enregistre. La liste
> noire signale, elle ne suspend pas : le retrait d une offre publiee
> reste une decision humaine. L action « Recontroler toutes les offres et
> propositions » est la seule voie qui leve une quarantaine devenue sans
> objet.

> Les dix chantiers sont livres (2026-11-12). L automatisation des
> sauvegardes est **preparee et configurable depuis l administration** ; seul
> le declenchement periodique demande une tache planifiee sur le serveur
> qui heberge le site. Voir § 7 et la page `/admin/sauvegardes/`.

> WhatsApp, SMS, PDF, 2FA et sauvegardes dépendent de comptes externes, de
> dépendances ou de l'hébergement. Le code préparera les modèles et les
> interfaces, sans simuler un envoi réel.

### Lot 9 — Recette

- [x] Tests 360, 390, 768, 1024 et 1280 px.
- [x] Contraste, focus clavier, labels, dialogues accessibles.
- [x] Aucun asset externe.
- [x] Réécriture des tests qui ciblent des classes CSS.
- [x] Captures avant/après.

> Recette automatisée reproductible :
> `python manage.py check_accessibility` (contrastes, ressources externes,
> focus, étiquettes) et les scripts `docs/refonte/recette_*.py` pilotent
> Chrome via le protocole DevTools pour mesurer le viewport réel.
> Trente captures sont archivées dans `docs/refonte/captures/`.

## 5. Impact backend du lot public

| Besoin | Changement | Poids |
|---|---|---|
| Accueil distinct | 1 vue + 1 URL | Faible |
| Comment ça marche | 1 vue + 1 URL | Faible |
| Sections de la fiche | 2 ou 3 champs `Offer` + migration | Faible |
| Formulaire de proposition | 3 champs + migration | Faible |
| Signalement global | 1 modèle + preuve + migration | Moyen |
| Fichiers envoyés | `MEDIA_ROOT` / `MEDIA_URL` | Faible |

## 6. Règles anti-confusion

1. Un lot à la fois, une page à la fois.
2. Ne jamais mélanger CSS, template et migration dans la même étape.
3. Le styleguide est la référence unique des couleurs et composants.
4. Aucune donnée inventée : vrais calculs ou état vide.
5. Ne copier aucun HTML Stitch : réécrire markup, textes et liens.
6. Tests en SQLite d'abord ; sauvegarde avant migration Supabase.
7. Conserver les anciens templates jusqu'à validation du nouveau.

## 7. Points encore ouverts

- Quels fournisseurs pour WhatsApp et SMS ?
- ~~La liste noire doit-elle être publique ou réservée à l'administration ?~~
  **Tranché le 2026-11-12 : réservée à l'administration.** Le registre n'a
  aucune route publique ; il est filtré par permission `view_blacklistedcontact`
  et ne peut pas modifier le statut d'une offre.

## 9. Veille automatisée

**Décision du 2026-11-16.** La veille automatisée entre dans le périmètre du
projet. Elle répond à un besoin réel : les offres publiées sur les sites
d'emplois, les pages d'entreprises et les groupes locaux ne parviennent pas
au catalogue Faso Job tant que personne ne les recopie à la main.

Ce que la veille est, et ce qu'elle n'est pas :

| La veille est | La veille n'est pas |
|---|---|
| un outil de **collecte** sur des sources autorisées | une publication automatique |
| une **analyse** des annonces par intelligence artificielle | une invention de données : l'IA propose, le code valide |
| un **signalement** des doublons | une suppression automatique |
| une préparation de **brouillons** | un second système de publication |

### Les règles, appliquées par le code

1. **Aucune publication automatique.** Le brouillon est créé en `draft`, avec
   les deux vérifications de publication à `False`. La règle existante de
   `Offer.clean()` interdit alors de le publier : il faut un coche humain,
   comme pour une soumission reçue par le formulaire public.
2. **Aucune information inventée.** Les informations absentes restent vides.
   Une date illisible n'est pas devinée, un e-mail invalide est écarté. La
   réponse brute du service est conservée pour audit.
3. **Aucune suppression automatique.** Un doublon est signalé à
   l'administration avec le motif du rapprochement ; l'équipe confirme ou
   écarte.
4. **Aucune source non autorisée.** Une source n'est surveillée qu'avec une
   autorisation écrite, un mode de collecte automatisable et l'accord de
   l'équipe. Facebook et WhatsApp restent en saisie manuelle : leurs
   conditions d'utilisation ne permettent pas la collecte automatique.
5. **Aucun martèlement.** Délai de 10 secondes entre deux requêtes et respect
   du fichier `robots.txt` du site.
6. **Aucun second système de publication.** La veille réutilise le modèle
   `Offer`, les statuts existants, la modération automatique et les actions
   d'administration. Le formulaire public n'est pas modifié.

### Le périmètre retenu

| Retenu | Écarté, et pourquoi |
|---|---|
| Collecte d'une page de liste d'emplois | Publication sur les réseaux sociaux : hors périmètre |
| Découverte assistée des sources à surveiller | Récupération automatique sur les réseaux sociaux : hors périmètre |
| Collecte d'un flux RSS ou Atom | Collecte automatique de Facebook et WhatsApp : conditions d'utilisation |
| Saisie manuelle d'un lien ou d'un texte | Envoi automatique de messages : aucun fournisseur n'est configuré |
| Analyse par intelligence artificielle | Notation automatique des candidats : hors périmètre |

### L'assistant de découverte

Trouver soi-même les sites d'emplois, et deviner le petit bout de code
qui désigne les annonces, ne passe pas à l'échelle du pays. L'assistant
prend cette recherche en charge, **sans jamais décider** :

1. le modèle propose des adresses de pages qui publient des offres ;
2. le code va réellement les vérifier : est-ce un site d'offres ? où sont
   les annonces ? combien y en a-t-il ? quel sélecteur ?
3. le code va lire les conditions du site et relever ce qu'il dit sur la
   reprise ;
4. l'équipe autorise ou refuse, en motivant son refus quand le site ne
   dit rien.

**Aucune source n'est collectée sans autorisation humaine.** L'assistant
ne contourne ni `robots.txt`, ni les conditions d'utilisation, ni les
pages construites en JavaScript ; les réseaux sociaux restent exclus.

### Le point à trancher

`Specifications_du_projet/README.md` liste « scraping automatisé » et
« publication automatique » parmi les éléments **hors périmètre du MVP**.
La veille ne contourne pas la seconde règle, mais elle consomme la première
pour les pages d'emplois. **La mise à jour de cette liste doit être validée
explicitement** : elle n'a pas été faite d'office.

### Où trouver le détail

- Le fonctionnement, la configuration et les commandes : `docs/veille.md`.
- Le Centre de veille : `/admin/veille/`.

---

## 8. Journal

- **2026-11-06 — Lot 0 démarré.** Nom retenu : Faso Job. Création des fondations.
- **2026-11-06 — Lot 0 validé.** `manage.py check` sans erreur ; 38 tests OK
  (dont 2 nouveaux sur le styleguide) ; `/styleguide/` rendu sans erreur console,
  sans ressource externe ; `/`, `/catalogue/` et `/proposer-une-offre/` répondent 200.
- **2026-11-06 — Arbitrages rendus.** Accueil distinct confirmé ; sous-titre
  « Opportunités professionnelles au Burkina Faso » ; « Contrôle des annonces »
  deviendra une page publique méthode + signalement (lot 6, ancre provisoire).
- **2026-11-06 — Lot 1 validé.** `home_view` sur `/`, catalogue conservé sur
  `/catalogue/`. Types d'opportunité et villes calculés depuis la base, aucune
  donnée inventée. Recherche vers le catalogue opérationnelle. 43 tests OK.
  Prochaine étape : Lot 2 (catalogue).
- **2026-11-06 — Lot 2 validé.** Catalogue reconstruit : filtres collants en
  desktop, dialogue de filtres en mobile, onglets de types calculés depuis la
  base, tri (récent, échéance, vérifiées, rémunération), filtres actifs
  retirables et pagination conservant la requête. Carte d'offre réutilisable,
  échéances colorées et carte entièrement cliquable. 48 tests OK ;
  `manage.py check` sans erreur. Lighthouse : 1.0 accessibilité, 1.0 bonnes
  pratiques, 1.0 SEO sur `/` et `/catalogue/` (corrections ARIA, cibles
  tactiles et meta description). Prochaine étape : Lot 3 (fiche d'offre).
- **2026-11-09 — Lot 3 validé.** Fiche d'offre reconstruite : fil d'Ariane,
  en-tête employeur, méta, badges, informations essentielles, description,
  dossier de candidature, traçabilité, avertissement anti-fraude, conseils,
  signalement et offres similaires. Candidature et barre mobile conditionnées
  à l'état de l'offre ; aucune donnée inventée. Partage du lien par copie avec
  repli `execCommand` et annonce accessible. Contrastes des badges et de l'état
  « fermée » corrigés dans les tokens. 54 tests OK ; `manage.py check` sans
  erreur ; Lighthouse 1.0 / 1.0 / 1.0 sur l'accueil, le catalogue et les deux
  fiches. Décision : un seul champ `description`, pas de migration.
  Prochaine étape : Lot 4 (proposer une annonce).
- **2026-11-09 — Lot 4 validé.** Formulaire de proposition reconstruit en cinq
  sections numérotées : opportunité, description et rémunération, source et
  candidature, contact du déclarant, charte éthique. Encarts de vérification,
  rappel anti-fraude et confidentialité dans une colonne latérale. Résumé
  d'erreurs accessible, champs `declarant_role`, `contact_phone` et
  `ethics_commitment` ajoutés (migration `0007`). Sauvegarde préalable des
  données dans `backups/fasojob-2026-11-09-raw.json`, puis migration appliquée
  sur Supabase. 63 tests OK ; `manage.py check` sans erreur ; Lighthouse
  1.0 / 1.0 / 1.0 sur le formulaire et sur son état d'erreur. Aucune promesse
  de délai ni statistique inventée. URL publique alignée sur le libellé :
  `/proposer-une-annonce/`, l'ancienne `/proposer-une-offre/` redirige en 301.
  Prochaine étape : Lot 5 (signaler une arnaque).
- **2026-11-10 — Lot 5 validé.** Page globale `/signaler-une-arnaque/` et page
  préremplie `/offre/<slug>/signaler/` : règle de tolérance zéro, trois sections
  numérotées, motifs et canaux codés, preuve jointe optionnelle, aside de suivi
  et état de confirmation. Le formulaire ne modifie jamais le statut ni la
  disponibilité d'une offre. Preuve privée (5 Mo, PNG/JPG/WEBP/PDF) stockée sous
  `MEDIA_ROOT/signalements/%Y/%m/` et téléchargeable uniquement par le personnel.
  Modèle `OfferReport` étendu, admin de traitement (filtres, recherche, action
  « Ignorer », note interne, lien de preuve protégé). Migrations `0008` et
  `0009` appliquées après sauvegarde
  `backups/fasojob-2026-11-09-lot5-before.json`. Les formulaires de proposition
  et de signalement passent en `novalidate` : le résumé d'erreurs accessible
  remplace la bulle native du navigateur. 77 tests OK ; Lighthouse 1.0 / 1.0 /
  1.0 sur les deux pages ; petit écran vérifié à 500 px (largeur minimale du
  Chrome sans interface). Prochaine étape : Lot 6 (comment ça marche).
- **2026-11-10 — Lot 6 validé.** Page unique `/comment-ca-marche/` : en-tête de
  méthode, quatre principes (accès libre, gratuité, vérification humaine,
  signalement), parcours de vérification en 4 étapes, référentiel des 5 badges,
  4 lignes rouges avec renvoi vers le signalement, FAQ en `<details>` et deux
  appels à l’action. Aucun chiffre, délai ou numéro inventé ; les badges
  « Source vérifiée », « Employeur vérifié », « Disponibilité confirmée »,
  « Source non vérifiée » et « Candidature fermée » reprennent les libellés
  réels des fiches. Navigation harmonisée : « Comment ça marche ? » vers la
  page, « Contrôle des annonces » vers son ancre, marge de défilement ajoutée
  pour le header collant. 85 tests OK ; Lighthouse 1.0 / 1.0 / 1.0 ; captures
  desktop et mobile. Prochaine étape : Lot 7 (admin restylé).
- **2026-11-12 — Lot 7 validé.** Administration restylée complétée.
  Modèles `BlacklistedContact` (registre privé, statuts bloqué / sous
  surveillance / neutralisés) et `PlatformSettings` (ligne unique) ajoutés ;
  migration `0010`. Panneau de vérification sur la fiche offre : rappel des
  trois contrôles distincts (source, employeur, disponibilité), champs
  manquants pour la publication et signalements en cours. Action admin
  « Ajouter les contacts signalés à la liste noire » : elle n'inscrit que le
  contact et ne modifie jamais le statut d'une offre ni celui du signalement.
  Rôle `editeur` : lecture seule de la liste noire et des paramètres ; rôle
  `moderateur` : ajout et modification. Compteurs de liste noire ajoutés au
  tableau de bord et au rapport d'activité (section « Sécurité et liste
  noire »), export CSV complété. Commande `dump_database` ajoutée pour la
  sauvegarde avant migration. 132 tests OK (38 nouveaux) ; `manage.py check`
  sans erreur ; `makemigrations --check` sans changement. Sauvegarde
  `backups/fasojob-2026-11-12-lot7-before.json` puis migration appliquée sur
  Supabase. Vérification navigateur : tableau de bord, liste noire, paramètres,
  rapport d'activité et fiche offre sans erreur. Prochaine étape : Lot 8.
- **2026-11-12 — Lot 8, tranche A livrée.** Huit chantiers sur dix sont
  terminés. **Croisement automatique** : le module `offres/moderation.py`
  compare chaque offre et chaque proposition aux contacts de la liste noire
  sur le numéro, l'e-mail et l'organisation, avec normalisation des formats
  (`+226 70-11 22.33` = `22670112233`). **Mots-clés et quarantaine** : les
  mots-clés sont saisis dans les paramètres, un par ligne ; une annonce qui
  en contient un est signalée et sa publication est refusée tant qu'un
  contrôle humain n'est pas enregistré. La quarantaine n'ajoute pas de
  statut éditorial : elle ne modifie jamais une offre déjà publiée et ne
  retire jamais une offre du catalogue. **Archivage automatique** : commande
  `archive_expired_offers`, avec `--dry-run`, délai réglable dans les
  paramètres (0 désactive). **Compteur de vues** : une consultation par
  session et par offre, compteur interne jamais affiché au public, aucune
  donnée personnelle conservée. **Notifications e-mail** : désactivées par
  défaut, elles exigent une adresse d'alerte renseignée et un interrupteur
  explicite. **Statistiques et export** : le rapport d'activité et le CSV
  gains des consultations, des clics sortants par canal, des offres les plus
  consultées et des consultations mensuelles. **Adaptateurs WhatsApp / SMS**
  : interface commune et journal `OutboundMessage` ; aucun fournisseur n'est
  configuré, les messages restent au statut « aucun fournisseur configuré »
  et aucun envoi n'est simulé. Action admin « préparer un message pour le
  déclarant » : le message est enregistré, pas envoyé. Migrations `0011`,
  `0012` et `0013` appliquées sur Supabase après sauvegarde
  (`backups/fasojob-2026-11-12-lot8-before.json`). 197 tests OK (65
  nouveaux) ; `manage.py check` sans erreur ; `makemigrations --check` sans
  changement. Vérification navigateur : rapport d'activité, export CSV,
  journal des messages sortants et action de préparation, sans erreur.
  Restent ouverts : double authentification et sauvegardes automatiques,
  qui dépendent d'un service externe non choisi et d'une tâche planifiée
  d'hébergement. Prochaine étape : Lot 9 (recette) ou choix des fournisseurs.
- **2026-11-12 — Lot 8, tranche B livrée.** **Double authentification par
  code temporel (TOTP, RFC 6238)** : compatible Google Authenticator,
  Authy et Aegis. Aucune donnée ne transite par un tiers : le secret
  partagé est calculé localement par le téléphone et par le serveur. Le
  secret est stocké **chiffré** (AES-GCM via `cryptography`), jamais en
  clair en base. L’algorithme a été comparé à la bibliothèque de référence
  `pyotp` sur cinq décalages horaires : les codes sont strictement
  identiques. QR code généré en SVG, sans dépendance graphique, avec clé
  de saisie manuelle en repli. Huit **codes de secours** à usage unique
  sont remis à l’activation et ne sont plus jamais réaffichés ; seules
  leurs empreintes sont conservées. Un middleware exige un code valide à
  chaque session d’administration : un mot de passe volé ne suffit plus à
  publier une annonce ni à modifier la liste noire. Le site public reste
  accessible sans code. Commande de secours
  `disable_two_factor --username` pour le cas où le téléphone **et** les
  codes de secours sont perdus. **Liste des destinataires de
  notification** : modèle `NotificationRecipient` géré depuis l’admin —
  on ajoute une adresse, on la désactive temporairement ou on la
  supprime ; les notifications partent à toutes les adresses actives.
  `goldendevstudio@gmail.com` est enregistrée comme destinataire, les
  notifications sont activées, et le coursier SMTP Gmail est paramétré
  dans `.env` (mot de passe d’application à renseigner). Dépendances
  ajoutées : `pyotp`, `cryptography`, `qrcode`. Migrations `0014` et
  `0015` appliquées sur Supabase après sauvegarde. 236 tests OK (39
  nouveaux) ; `manage.py check` sans erreur ; `makemigrations --check`
  sans changement. Vérification navigateur : QR code et clé manuelle
  affichés, activation, codes de secours remis, verrouillage à la
  connexion, déverrouillage par code TOTP et par code de secours, site
  public non bloqué. Reste ouvert : sauvegardes automatiques, qui dépendent
  d’une tâche planifiée d’hébergement.
- **2026-11-12 — Lot 8, tranche C livrée. Lot 8 terminé.** **Sauvegardes
  automatiques** : tout ce qui se configure se configure désormais depuis
  l’administration, page `/admin/sauvegardes/`. Destination, préfixe des
  fichiers, nombre de copies conservées, fréquence, compression et
  inclusion éventuelle des fichiers joints. Un bouton « Sauvegarder
  maintenant » produit un fichier immédiat ; l’historique affiche le
  résultat, la durée, la taille et le nombre de lignes de chaque
  sauvegarde, y compris les échecs. **Restauration** : la commande
  `restore_database` restaure une sauvegarde et **simule par défaut** ;
  rien n'est ecrit sans `--apply`. Le vidage et le re-insert suivent
  l’ordre de dépendance des clés étrangères, et les compteurs
  auto-incrémentés sont remis à jour : une offre créée après restauration
  ne entre pas en collision avec une ligne restaurée. Ce point a été
  vérifié sur PostgreSQL après correction de trois défauts : ordre de
  suppression, appel de vidage modifié dans Django 6.1, et tables sans
  colonne `id`. **Activation** : la commande à copier-coller pour cron
  (Linux) ou Tâche planifiée (Windows) est générée dans l’administration,
  avec le vrai chemin du projet et la fréquence choisie. Elle respecte
  l’interrupteur « sauvegarde automatique activée » : tant qu’il est
  décoché, une exécution planifiée ne fait rien. Configuration
  `BackupConfiguration` (ligne unique) et historique `BackupRun`.
  Migration `0016` appliquée sur Supabase après sauvegarde. 270 tests OK
  (34 nouveaux) ; `manage.py check` sans erreur ; `makemigrations
  --check` sans changement. Vérification navigateur : configuration
  enregistrée, sauvegarde manuelle réussie, commande d’activation
  affichée, historique affiché. **Les dix chantiers du lot 8 sont
  livrés.** Prochaine étape : Lot 9 (recette).

- **2026-11-12 — Envoi e-mail operationnel.** Le coursier SMTP Gmail est
  configure et valide : une notification interne de la plateforme part
  reellement vers l adresse de l equipe. Deux points appris a cette
  occasion, a consigner pour l avenir : Google affiche le mot de passe
  d application par groupes de quatre separes par des espaces, et ces
  espaces ne font pas partie du secret ; le mot de passe doit etre copie
  sans eux. Le destinataire de reference est gere dans
  `/admin/offres/notificationrecipient/` : on peut en ajouter, en
  desactiver ou en supprimer, et les notifications partent a toutes les
  adresses actives. L adresse d alerte des parametres reste receveuse
  meme si elle n est pas dans la liste. Un e-mail qui echoue n interrompt
  jamais le traitement en cours et le journal des messages sortants
  conserve la trace.
- **2026-11-12 — Lot 9 validé : recette.** Le site a été contrôlé
  page par page, aux cinq résolutions cibles, avec des mesures réelles et
  reproductibles. **Recette automatisée** : la commande
  `python manage.py check_accessibility` vérifie les contrastes WCAG, les
  ressources externes, la présence d’un focus clavier et l’étiquetage des
  champs ; les scripts `docs/refonte/recette_resolutions.py` et
  `docs/refonte/recette_cibles_tactiles.py` pilotent Chrome via le
  protocole DevTools pour fixer le **viewport réel** — une mesure faite en
  simulant une largeur sur le corps de page ne déclenche pas les media
  queries et ne prouve rien. **Aucun débordement horizontal** sur les six
  pages publiques aux cinq résolutions (360, 390, 768, 1024 et 1280 px).
  **Cibles tactiles** : toutes les cibles mesurables atteignent désormais
  44 px de haut, ou sont des liens situés dans un bloc de texte, que la
  norme exclut explicitement (WCAG 2.5.5). **Défauts corrigés** : le
  texte blanc du bouton WhatsApp ne tenait que 1,98:1 de contraste — le
  texte est désormais sombre, ce qui porte le bouton à 9,00:1 tout en
  conservant le vert officiel de la marque ; le contour du bouton
  secondaire ne tenait que 1,48:1 ; les boutons, onglets, listes de
  sélection, liens de navigation, fil d’Ariane, lien « Retour », lien de
  pied de page et champ de fichier ont reçu une zone tactile confortable ;
  le titre d’une carte d’offre, qui doublonnait le lien de la carte, a
  été dégagé. **Contrastes** : les vingt-cinq paires de texte utilisées
  atteignent le niveau AA. **Ressources externes** : aucune. **Étiquettes** :
  tous les champs de formulaire en ont une. **Tests** : le test de la FAQ
  ne vérifie plus les noms de classes CSS mais le comportement attendu —
  quatre questions lisibles, `<details>` et `<summary>` associés — et il a
  été prouvé qu’il échoue bien si la FAQ disparaît. **Captures** : trente
  captures de la recette sont archivées dans `docs/refonte/captures/`.
  270 tests OK ; `manage.py check` sans erreur ; `makemigrations --check`
  sans changement. **Le plan de refonte est terminé.**
- **2026-11-13 — Croisement automatique liste noire et offres branché.**
  Le lot 8 annonçait la structure ; le croisement, lui, fonctionne
  désormais. **À la création**, chaque offre et chaque proposition sont
  croisées avec la liste noire et les mots-clés de quarantaine : une
  annonce correspondante est signalée avant même d’être enregistrée.
  **À l’inscription d’un contact**, les offres et propositions qui
  utilisent ses coordonnées sont recontrôlées sur-le-champ, y compris
  celles déjà publiées. **Gravité** : un contact *bloqué définitivement*
  ne peut jamais être publié, même après un contrôle humain ; un contact
  *sous surveillance* bloque la publication tant qu’un contrôle n’est pas
  enregistré ; un contact dont les coordonnées ont été *neutralisées* ne
  bloque plus rien. **La liste noire signale, elle ne suspend pas** :
  l’offre reste publiée et c’est l’équipe qui décide de la suspendre, à
  travers une action explicite. L’action « Recontrôler toutes les offres
  et propositions » est la seule voie qui lève une quarantaine devenue
  sans objet. Quatre défauts ont été corrigés en route : la recherche des
  annonces liées ne trouvait rien parce qu’un numéro saisi avec des
  espaces n’est pas une sous-chaîne du même numéro sans espaces ; la
  sélection des candidats exclait par erreur les offres ne portant qu’un
  seul des deux numéros ; l’enregistrement du motif de quarantaine
  butait sur la règle de publication, ce qui rendait impossible de
  signaler une offre déjà publiée ; et deux méthodes `save()` coexistaient
  sur le contact de la liste noire, la seconde écrasant la première et
  empêchant la date de diffusion d’être posée. 292 tests OK (22 nouveaux
  dans `offres/test_lot8_croisement.py`) ; `manage.py check` sans
  erreur ; `makemigrations --check` sans changement. Migration `0017`
  appliquée sur Supabase après sauvegarde
  (`backups/fasojob-2026-11-13-croisement-before.json`). Vérifié sur la
  base réelle : l’inscription d’un contact a signalé immédiatement l’offre
  publiée correspondante, sans en modifier le statut.
- **2026-11-16 — Veille automatisée livrée.** Sept lots : modèles
  (`CollectedAnnouncement`, `VeilleRun`, cinq champs `Source`, trois champs
  `Offer`), module d'intelligence artificielle interchangeable (un seul client
  compatible OpenAI : le fournisseur et le modèle se changent dans le
  `.env`), collecteurs (lien, texte, page de liste, flux RSS/Atom) avec délai
  de 10 secondes et respect de `robots.txt`, détection de doublons par
  rapprochement du titre, de l'entreprise, du lieu, de la date limite, du
  lien et du contenu, orchestration complète, Centre de veille dans
  `/admin/veille/`, trois commandes (`collect_offers`, `veille_essai`,
  `veille_selecteur`). Migration `0018`. 457 tests OK ; `manage.py check` sans
  erreur ; `makemigrations --check` sans changement. **Aucune annonce
  collectée n'est publiée sans validation humaine.**

- **2026-11-16 — Assistant de découverte livré.** L'équipe ne trouve plus
  elle-même les sources à surveiller : `veille_decouverte` propose des
  adresses (modèle, plus Brave Search ou SearXNG en option), le code les
  vérifie et rend un rapport en trois verdicts — reprise explicitement
  autorisée, reprise non établie, source écartée. Les propositions sont
  enregistrées (`SourceProposal`, migration `0019`) et tranchées dans le
  Centre de veille : **autoriser** crée la source après reverification de
  la page, **refuser** la trace. Une source dont la reprise n'est pas
  établie exige une autorisation motivée par l'équipe. 490 tests OK ;
  `manage.py check` sans erreur ; sauvegarde avant migration Supabase.
  Aucune source n'est collectée sans validation humaine.
