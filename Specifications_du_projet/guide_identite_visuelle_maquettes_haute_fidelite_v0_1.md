# Guide d'identité visuelle et maquettes haute fidélité

**Version :** 0.1 — proposition de direction visuelle  
**Date :** 14 octobre 2026  
**Nom du produit :** « Opportunités » est un nom de travail, non validé  
**Statut :** proposition à relire avant validation de l'identité visuelle

## 1. Intention de design

La plateforme doit paraître fiable, claire, accessible et rapide à utiliser, notamment sur smartphone et avec une connexion modeste. L'interface doit faciliter la recherche et la compréhension d'une offre avant de pousser l'utilisateur vers le canal de candidature annoncé.

Principes directeurs :
- **Lisibilité avant décoration.** Hiérarchie claire, texte lisible, éléments interactifs reconnaissables.
- **Confiance sans promesses excessives.** Les indicateurs de provenance et de contrôle doivent refléter ce qui a réellement été vérifié.
- **Mobile d'abord.** Les actions essentielles restent visibles et faciles à toucher sur un petit écran.
- **Neutralité et sobriété.** Éviter les clichés visuels et laisser les informations de l'offre occuper le premier plan.
- **Cohérence.** Réutiliser les mêmes couleurs, espacements, rayons, cartes et boutons sur l'ensemble du site.

## 2. Palette proposée

| Jeton | Couleur | Utilisation |
|---|---|---|
| `primary` | `#174F7A` | Boutons principaux, liens, éléments actifs |
| `primary-dark` | `#123C5D` | Titres accentués, bandeaux, navigation d'administration |
| `primary-soft` | `#EAF3F9` | Fonds d'icônes et zones de soutien |
| `accent` | `#16856D` | Petits repères, accent éditorial, état positif |
| `accent-soft` | `#E8F6F1` | Fond d'un badge positif |
| `whatsapp` | `#25D366` | Uniquement pour une action de candidature via WhatsApp |
| `canvas` | `#F5F8FB` | Fond général du site |
| `surface` | `#FFFFFF` | Cartes, formulaires, panneaux |
| `ink` | `#142536` | Texte principal |
| `muted` | `#68798A` | Texte secondaire, métadonnées |
| `line` | `#DCE5ED` | Bordures et séparateurs |
| `warning-bg` | `#FFF4D8` | Avertissement ou vérification à confirmer |
| `warning` | `#8A5B00` | Texte associé aux avertissements |
| `danger-bg` | `#FFF0ED` | Erreur ou problème signalé |
| `danger` | `#B42318` | Texte d'erreur ou action à risque |

Cette palette est une proposition, pas une identité de marque définitive. La couleur WhatsApp est réservée au canal WhatsApp et ne doit pas devenir la couleur principale générale du site.

## 3. Typographie et hiérarchie

- **Famille recommandée :** Inter si disponible, avec une pile de secours système (`ui-sans-serif`, `system-ui`, `Segoe UI`, sans-serif). Ne pas dépendre d'un chargement de police externe pour afficher le contenu essentiel.
- **Titres de page :** 30–38 px sur ordinateur ; 26–32 px sur mobile.
- **Titres de section :** 19–24 px.
- **Titre d'une fiche d'offre :** 26–30 px sur ordinateur ; 22–25 px sur mobile.
- **Texte courant :** 15–16 px sur ordinateur ; 14–15 px sur mobile.
- **Métadonnées et libellés :** viser 12 px minimum quand c'est possible ; réserver les tailles inférieures aux mentions secondaires rarement indispensables.
- **Poids :** graisse 600–750 pour les titres et actions, 400–500 pour le texte courant.

## 4. Espacements, rayons et conteneurs

Échelle de base : 4, 8, 12, 16, 24, 32, 40 et 48 px. Utiliser de préférence ces valeurs plutôt que des espacements arbitraires.

- Petits contrôles et champs : rayon 8–10 px.
- Boutons et cartes : rayon 10–16 px.
- Grandes zones de mise en avant : rayon 20–24 px.
- Bordures fines et discrètes ; ombres légères uniquement pour distinguer une surface, pas pour chaque composant.
- Largeur de contenu maximale recommandée : environ 1200 px sur grand écran, avec marges fluides.
- Sur mobile, utiliser des marges de 16 px environ et empiler les colonnes au lieu de compresser les champs.

## 5. Composants et règles visuelles

### Cartes d'offres dans le catalogue
- Intitulé du poste en premier plan.
- Employeur lorsque connu, ville, type d'opportunité et rémunération quand elle est indiquée.
- Statut de provenance ou de contrôle sans laisser croire que tous les critères ont été vérifiés.
- Action claire pour ouvrir la fiche.
- Toute la carte peut être cliquable, mais le lien d'action explicite doit rester visible et accessible au clavier.

### Fiche d'offre
- Chaque groupe d'informations est placé dans une carte distincte : en-tête, informations essentielles, description, source et vérifications.
- Le panneau de candidature est distinct et visible. Sur mobile, il apparaît immédiatement après l'en-tête de l'offre.
- Ne pas afficher d'informations inconnues comme si elles étaient confirmées : utiliser « Non précisé » ou « À confirmer ».
- La provenance et la disponibilité du poste doivent rester des informations séparées.

### Bouton de candidature
- **Offre avec candidature WhatsApp :** bouton vert WhatsApp avec un pictogramme WhatsApp reconnaissable et le libellé **« Postuler sur WhatsApp »**. Le lien doit être construit à partir du contact de candidature explicitement fourni pour l'offre.
- **Autres modes de candidature :** bouton principal avec le libellé exact **« Postuler »**. Il dirige vers le lien externe, l'email, les coordonnées ou les instructions de dépôt correspondants.
- Un seul bouton d'action principal est affiché pour une offre, selon le canal retenu. Les liens secondaires, comme « Consulter l'annonce source », restent visuellement secondaires.
- Les maquettes utilisent des données fictives : aucun numéro, lien ou contact de candidature n'est réel.

### Statuts et badges
- Les états positifs, à confirmer et neutres utilisent respectivement les fonds vert pâle, jaune pâle et gris clair.
- Toujours joindre un libellé textuel à la couleur : la couleur seule ne suffit pas.
- Ne jamais utiliser « Employeur vérifié » ou « Disponibilité confirmée » sans contrôle correspondant.

### Formulaires
- Libellés au-dessus des champs ; champs obligatoires indiqués clairement.
- Instructions courtes et placées près du champ concerné.
- Messages d'erreur utiles, associés au champ ; ne pas vider les informations déjà saisies après une erreur.
- Les champs doivent rester utilisables sur mobile et ne pas imposer de compte au visiteur sans nécessité validée.

### Administration
- Navigation latérale sur grand écran ; navigation compacte ou réorganisée sur mobile.
- Les actions de publication, de fermeture et de retrait doivent être clairement distinctes.
- Les tableaux peuvent défiler horizontalement sur mobile si les colonnes ne peuvent pas être empilées sans perdre leur sens.
- Les données d'exemple affichées dans les maquettes sont fictives.

## 6. Responsive et accessibilité

- Construire d'abord les vues mobiles, puis élargir la disposition pour tablette et ordinateur.
- Cible de confort tactile : zones d'action d'environ 44 × 44 px ou davantage.
- Contraste suffisant entre texte et fond ; ne pas coder un état uniquement par la couleur.
- Parcours de navigation et formulaires utilisables au clavier ; focus visible.
- Les icônes seules ne remplacent pas les libellés des actions essentielles.
- Prévoir les états vides, chargement, erreur, offre expirée et résultats sans correspondance.
- Prévoir l'affichage des champs inconnus et des liens sources manquants sans casser la mise en page.
- Réduire les images décoratives et dépendances externes pour préserver un chargement raisonnable.

## 7. Écrans réalisés dans la maquette

Les images PNG fournies dans le dossier `screenshots/` illustrent :

1. `01_accueil.png` — page d'accueil ;
2. `02_catalogue.png` — catalogue et recherche ;
3. `03_fiche_offre_whatsapp.png` — fiche d'offre dont la candidature se fait par WhatsApp ;
4. `04_fiche_offre_autre_canal.png` — fiche d'offre avec un autre canal et un bouton « Postuler » ;
5. `05_soumettre_offre.png` — formulaire de proposition d'annonce ;
6. `06_admin.png` — tableau de bord d'administration.

Chaque écran dispose d'une version ordinateur et d'une version mobile. Les exemples et les chiffres d'administration sont fictifs.

## 8. Prototype HTML interactif

Le fichier `maquettes_haute_fidelite_v0_1.html` regroupe une prévisualisation interactive autonome : navigation entre écrans, ouverture des fiches, filtres du catalogue, formulaire de soumission simulé et différences de libellé entre les modes de candidature. Le prototype ne stocke pas de données et n'envoie aucune candidature réelle.

Pour l'ouvrir : télécharge le fichier HTML et ouvre-le dans un navigateur moderne. Aucun serveur ni compte n'est nécessaire.

## 9. Décisions à garder provisoires

- Nom définitif, logo définitif et identité de marque.
- Validation finale de la palette de couleurs.
- Libellés exacts des statuts de vérification visibles au public.
- Règles complètes de candidature lorsque plusieurs canaux figurent dans une même source.
- Politique de confirmation, d'expiration et de retrait des annonces.
- Design définitif des pages d'information légale et de confidentialité.

## 10. Suite du travail

Après validation de cette direction visuelle, préciser les composants réutilisables et leurs variantes, puis établir la spécification technique : stack, structure du dépôt, système de styles, routage, composants, données d'exemple, tests et plan de réalisation par incréments. Le développement ne doit pas commencer à partir de captures seules : le guide, les wireframes validés et le modèle de données servent ensemble de référence.
