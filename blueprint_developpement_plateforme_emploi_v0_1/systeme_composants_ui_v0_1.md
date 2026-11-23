# Syst?me de composants UI ? plateforme d'opportunit?s professionnelles

**Version :** 0.2  
**Date :** 20 octobre 2026  
**Statut :** proposition adapt?e ? Django et templates HTML/CSS

## 1. Objectif

D?finir les composants r?utilisables, leurs responsabilit?s et les r?gles qui doivent ?tre identiques sur toutes les pages. L'objectif est d'?viter qu'une IA produise plusieurs variantes incoh?rentes du m?me bouton, badge, carte ou champ de formulaire.

## 2. Principes

- Un composant a une responsabilit? principale et une API simple.
- Les composants Django et les templates doivent rester lisibles, r?utilisables et facilement maintenables.
- Le texte d'interface est en fran?ais et reste explicite. Les boutons doivent d?crire l'action : `Voir l'offre`, `Postuler`, `Postuler sur WhatsApp`, `Signaler cette offre`.
- Les composants pr?sentent les ?tats chargement, vide, erreur et d?sactiv? lorsque cela s'applique.
- Toute action doit fonctionner au clavier et ?tre correctement libell?e pour les lecteurs d'?cran.
- Une couleur ne doit jamais ?tre le seul moyen de communiquer un statut.

## 3. Tokens visuels de r?f?rence

| Jeton | Valeur | R?gle d'usage |
|---|---|---|
| `--color-primary` | `#6CABDD` | Bleu ciel dominant pour actions et ?l?ments s?lectionn?s. |
| `--color-primary-strong` | `#245F87` | Liens, ?l?ments o? du texte blanc est requis. |
| `--color-primary-soft` | `#EAF5FC` | Fond secondaire bleu p?le. |
| `--color-accent` | `#16845F` | Vert secondaire, ?l?ments positifs. |
| `--color-accent-soft` | `#E8F6EF` | Fond doux des statuts positifs. |
| `--color-whatsapp` | `#25D366` | Accent de marque WhatsApp ; usage r?serv? ? ce canal. |
| `--color-canvas` | `#F5F9FC` | Fond global. |
| `--color-surface` | `#FFFFFF` | Cartes et formulaires. |
| `--color-ink` | `#142536` | Texte principal. |
| `--color-muted` | `#68798A` | Texte secondaire. |
| `--color-line` | `#D8E7F1` | Bordures. |
| `--color-warning-bg` | `#FFF4D8` | Fonds d'alertes. |
| `--color-warning` | `#8A5B00` | Texte d'alerte. |
| `--color-danger-bg` | `#FFF0ED` | Fonds d'erreurs. |
| `--color-danger` | `#B42318` | Texte d'erreur. |

**Contraste :** ?viter le texte blanc sur `#6CABDD` pour les petits textes. Utiliser le texte `#142536` sur ce fond. V?rifier le contraste des combinaisons finales avant livraison.

**Typographie :** Inter ou une pile syst?me de secours, sans d?pendre d'un appel externe au moment du rendu.

**Espacements :** ?chelle 4, 8, 12, 16, 24, 32, 40, 48 px.  
**Rayons :** 8?10 px pour champs, 10?16 px pour cartes/boutons, 20?24 px pour les panneaux principaux.  
**Conteneur :** largeur maximale indicative 1200 px ; marges 16 px sur t?l?phone.  
**Cibles tactiles :** viser au moins 44 ? 44 px pour les actions primaires.

## 4. Catalogue de composants

### 4.1 Structure et navigation

| Composant | Responsabilit? | ?tats/r?gles |
|---|---|---|
| `SiteHeader` | Logo, liens Accueil/Offres/M?thode et entr?e Soumettre une offre | Menu mobile accessible. |
| `SiteFooter` | Liens ? propos, Contact, Confidentialit?, M?thode de contr?le | Pr?sent sur les pages publiques. |
| `PageContainer` | Aligne la largeur et les marges des pages | Largeur commune et padding responsive. |
| `SectionHeading` | Titre, description et action secondaire d'une section | Hi?rarchie typographique stable. |
| `Breadcrumbs` | Indique le chemin courant | Dernier ?l?ment identifi? comme page courante. |

### 4.2 Offres et d?couverte

| Composant | Responsabilit? | ?tats/r?gles |
|---|---|---|
| `OfferCard` | Pr?sente titre, ville, type, salaire disponible, date, badges et bouton `Voir l'offre` | Le bouton est visible et explicite. |
| `OfferMetadata` | Affiche lieu, contrat, exp?rience, r?mun?ration | Masque les champs inconnus plut?t que d'inventer une valeur. |
| `OfferStatusBadge` | Affiche les statuts de disponibilit?/publication | Texte + couleur ; aucun badge si la condition n'est pas remplie. |
| `SourceBadge` | Affiche `Source retrouv?e` ou `Source ? confirmer` | Ne signifie jamais que l'employeur ou le poste ont ?t? v?rifi?s. |
| `CategoryButton` | Permet de choisir une cat?gorie ou un type | S?lection visible ; ?tat encod? dans l'URL. |
| `SearchBar` | Recherche mots-cl?s, ville et action Rechercher | Labels accessibles ; conserve la requ?te dans l'URL. |
| `FilterPanel` | Filtres par cat?gorie, ville, type et salaire si disponible | Indique les filtres actifs. |
| `ActiveFilterChips` | R?sume les filtres en cours | Chaque chip peut retirer son filtre. |
| `ResultsToolbar` | Nombre de r?sultats et tri disponible | Le nombre doit refl?ter la requ?te r?elle. |
| `EmptyState` | Explique l'absence de r?sultats et propose une action | Texte compr?hensible. |
| `Pagination` | Navigation entre les pages de r?sultats | Conserve les filtres et les mots-cl?s dans les liens. |

### 4.3 Fiche d'offre et candidature

| Composant | Responsabilit? | ?tats/r?gles |
|---|---|---|
| `OfferDetailHeader` | Titre, entreprise si connue, ville, date et badges utiles | Les informations inconnues ne sont pas invent?es. |
| `InfoCard` | Carte r?utilisable pour Informations essentielles, Description, Source, V?rification ou Signalement | Titre explicite. |
| `SourceAttribution` | Nom de la source et lien vers la publication originale | Lien uniquement si existant et autoris?. |
| `VerificationSummary` | Explique ce qui a ?t? v?rifi? et ce qui reste incertain | Ne pas afficher un score num?rique sans m?thode fiable. |
| `ApplyButton` | CTA principal pour les canaux autres que WhatsApp | Libell? exact `Postuler` ; ouvre le bon canal. |
| `WhatsAppApplyButton` | CTA avec pictogramme de marque WhatsApp | Libell? `Postuler sur WhatsApp`. |
| `ReportOfferAction` | Ouvre un formulaire/modal de signalement | Motif requis, pr?cision facultative. |
| `ClosedOfferNotice` | Indique clairement qu'une offre n'est plus active | Aucun CTA actif. |

#### R?gle du CTA selon le canal

- WhatsApp : bouton avec la couleur de marque et libell? `Postuler sur WhatsApp`.
- Site externe, e-mail ou t?l?phone : bouton `Postuler`, avec destination adapt?e (`https`, `mailto:` ou `tel:`).
- D?p?t physique : `Postuler` renvoie vers les informations de d?p?t visibles dans la fiche.
- Offre ferm?e : ne pas afficher un bouton de candidature actif.

## 5. R?gles de composition des ?crans

### Accueil

- `SiteHeader`.
- Carte principale regroupant le message et la recherche.
- Section des offres r?centes.
- CTA pour proposer une offre.
- `SiteFooter`.

### Catalogue

- `SiteHeader`, intro et `SearchBar`.
- `CategoryButton` et filtres.
- `FilterPanel`, `ActiveFilterChips`, `ResultsToolbar`, liste des `OfferCard` et `Pagination`.

### Fiche d'offre

- `SiteHeader` et fil d'Ariane.
- `OfferDetailHeader`.
- Cartes s?par?es pour informations essentielles, description, source et signalement.
- Bouton de candidature adapt? au canal r?el.
- Ajouter du padding inf?rieur pour que le contenu reste lisible.

### Formulaire de soumission

- Explication br?ve : soumission gratuite et publication apr?s contr?le.
- Champs essentiels avec labels, validation et confirmation d'envoi.
- Le formulaire public cr?e une soumission en attente ; il ne cr?e pas directement une offre publi?e.

### Administration

- `AdminShell` et `AdminNavigation`.
- Vue synth?tique de l'?tat du catalogue.
- Files de contr?le pour offres collect?es, soumissions externes et signalements.
- Actions explicites pour pr?visualiser, publier, demander correction, fermer, archiver ou retirer.

## 6. ?tats minimum ? pr?voir

- Chargement, erreur g?n?rale, aucun r?sultat, aucune offre, aucun signalement, formulaire invalide, envoi en cours et envoi r?ussi.
- Source retrouv?e / source ? confirmer.
- Disponibilit? ? confirmer / confirm?e / offre ferm?e.
- Destination de candidature absente ou invalide : ne pas afficher un bouton trompeur ; afficher une explication et permettre le signalement.
- Connexion admin expir?e, acc?s non autoris?, erreur de sauvegarde.

## 7. R?gles techniques li?es aux composants

- Utiliser des noms de composants coh?rents, en PascalCase.
- Les composants d'affichage re?oivent des donn?es typ?es et n'acc?dent pas eux-m?mes ? la base de donn?es.
- Les vues Django restent la source de logique m?tier et les templates g?rent le rendu.
- Les op?rations de mutation se font dans des vues ou formulaires explicites, avec validation, autorisation et gestion d'erreur.
- Garder les couleurs dans des variables CSS/tokens, pas dans de nombreux codes hexad?cimaux r?p?t?s dans les pages.
- Pr?f?rer des composants m?tier simples plut?t que des abstractions trop g?n?rales.

## 8. Crit?res d'acceptation du syst?me UI

- Le m?me bouton principal garde la m?me hauteur et les m?mes ?tats partout.
- Les cartes d'offre ont un bouton `Voir l'offre` compr?hensible et visible.
- Les cat?gories sont des boutons accessibles au clavier et leurs filtres persistent dans l'URL.
- Le bouton WhatsApp est distinct visuellement et utilise la bonne ic?ne de marque.
- Les badges affichent une ?tiquette textuelle, pas seulement une couleur.
- Tous les formulaires ont labels, validation serveur et ?tats de retour.
- Les vues mobile et ordinateur sont test?es pour les principales pages.

## 9. R?f?rences utiles

- Django ? documentation des templates : https://docs.djangoproject.com/en/stable/topics/templates/
- Django ? documentation des formulaires : https://docs.djangoproject.com/en/stable/topics/forms/
- Django Admin : https://docs.djangoproject.com/en/stable/ref/contrib/admin/
- Google Search Central, JobPosting : https://developers.google.com/search/docs/appearance/structured-data/job-posting?hl=fr
