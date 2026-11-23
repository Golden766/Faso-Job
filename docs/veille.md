# Veille automatisée

La veille va chercher des offres d'emploi sur des sources autorisées, les
analyse, signale les doublons et prépare des **brouillons** dans
l'administration.

> **Rien n'est publié automatiquement.** Une annonce collectée devient un
> brouillon en attente de validation. La publication reste une décision
> humaine, prise dans la liste des offres, comme pour toutes les autres.

Ce document décrit le fonctionnement, la configuration et les commandes.
La décision qui a autorisé cette évolution est inscrite dans
`docs/refonte/PLAN-REFONTE.md`.

---

## 1. Les six étapes

```
Collecte  →  Conservation  →  Extraction IA  →  Classement  →  Doublons  →  Brouillon
```

| Étape | Ce qui se passe | Où |
|---|---|---|
| **Collecte** | La page ou le texte est récupéré | `offres/veille/http.py`, `offres/veille/collectors.py` |
| **Conservation** | Une ligne est écrite avec la provenance et le contenu original | `offres/models.py` → `CollectedAnnouncement` |
| **Extraction IA** | Les 16 informations disponibles sont extraites et vérifiées | `offres/veille/ia.py`, `offres/veille/schema.py` |
| **Classement** | L'annonce est classée dans une catégorie **qui existe déjà** | `offres/veille/ia.py` |
| **Doublons** | Le catalogue est passé en revue | `offres/veille/dedup.py` |
| **Brouillon** | Une offre est créée en statut `draft` | `offres/veille/pipeline.py` |

---

## 2. Les quatre méthodes de collecte

| Méthode | Mode | Usage |
|---|---|---|
| Lien collé | `manual_url` | l'équipe colle l'adresse d'une annonce |
| Texte collé | `manual_text` | l'équipe colle le texte d'une annonce (Facebook, WhatsApp, presse) |
| Page de liste | `web` | une page d'emplois lue régulièrement |
| Flux RSS ou Atom | `rss` | la forme que prennent la plupart des newsletters |

**Facebook et WhatsApp ne sont jamais collectés automatiquement.** Leurs
conditions d'utilisation ne le permettent pas. L'équipe y colle le texte de
l'annonce : la suite du traitement est identique.

---

## 3. Configurer le service d'intelligence artificielle

Le service est interchangeable : **changer de modèle ne demande qu'une
modification du fichier `.env`**, jamais de changement de code.

Le code parle à un service compatible avec l'interface OpenAI
(`/chat/completions`). C'est l'interface la plus largement répandue.

### Option A — Gemini (Google AI Studio), modèle gratuit

```
AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
AI_API_KEY=...
AI_MODEL=gemini-2.0-flash-exp
```

### Option B — OpenRouter, modèles gratuits

```
AI_BASE_URL=https://openrouter.ai/api/v1
AI_API_KEY=sk-or-...
AI_MODEL=...:free
```

### Option C — un modèle local (Ollama, llama.cpp…)

```
AI_BASE_URL=http://localhost:11434/v1
AI_API_KEY=une-cle-au-choix
AI_MODEL=llama3.1
```

### Autres réglages

| Variable | Rôle | Défaut |
|---|---|---|
| `AI_REQUEST_TIMEOUT` | délai maximal d'attente, en secondes | `60` |
| `AI_JSON_MODE` | à activer si le service sait rendre un JSON strict | `False` |

La clé reste dans `.env`. Elle n'est jamais versionnée, jamais affichée dans
une page et jamais envoyée au public.

**Sans clé configurée**, les annonces sont conservées dans le Centre de veille,
mais aucun brouillon incomplet n'est créé. Une extraction en échec reste dans
« Annonces détectées », avec son motif, pour être corrigée ou réessayée.

### Vérifier sa configuration

```
python manage.py veille_essai "Nous recrutons un assistant comptable a Ouagadougou."
python manage.py veille_essai --fichier annonce.txt --classer
```

---

## 4. Configurer une source surveillée

Dans l'administration : **Référentiel → Sources**.

| Champ | Rôle |
|---|---|
| **Mode de collecte** | `web`, `rss` ou `newsletter` pour une surveillance automatique |
| **Source surveillée** | coche pour activer la surveillance |
| **Paramètres de surveillance** | JSON : `url`, `selector`, `limit`, `delay_seconds` |
| **Conditions de reprise et autorisation** | **obligatoire** : ce qui autorise la reprise des annonces |
| **Dernière collecte / résultat** | renseignés automatiquement |

### La règle d'autorisation

> Une source n'est collectée que si elle est **surveillée**, **porte une
> autorisation écrite** et utilise un **mode automatisable**.

Sans cette note, la veille ne touche pas la source. Le bandeau « Sans
autorisation » le rappelle dans la liste des sources.

### Trouver le sélecteur d'une page

Une page web ne dit pas où sont ses annonces. Cette commande regarde la page
et propose les blocs qui se répètent :

```
python manage.py veille_selecteur https://emploi.exemple.bf/offres
```

```
Selecteurs possibles sur https://emploi.exemple.bf/offres :
    12 element(s)  article.offre
      Chargé de projets
    8 element(s)  div.job-card
      Assistant comptable
```

Pour vérifier un sélecteur choisi :

```
python manage.py veille_selecteur https://emploi.exemple.bf/offres --exemple "article.offre"
```

### Exemple de paramètres

```json
{
  "url": "https://emploi.exemple.bf/offres",
  "selector": "article.offre",
  "limit": 20,
  "delay_seconds": 10
}
```

---

## 5. Les règles de la veille

Ces règles ne sont pas des recommandations : elles sont appliquées par le code
et vérifiées par les tests.

1. **Aucune publication automatique.** Le brouillon est créé en `draft`, avec
   `is_published`, `is_source_confirmed` et `is_employer_verified` à `False`.
   La règle de publication existante interdit de le publier sans un coche
   humain.
2. **Aucune information inventée.** Ce que le service propose est vérifié
   champ par champ. Une information absente, ambiguë ou malformée reste
   **vide**. Une date illisible n'est jamais devinée.
3. **Aucune suppression automatique.** Un doublon est *signalé*, jamais
   effacé. L'équipe décide.
4. **Aucune double collecte.** L'empreinte du contenu (SHA-256, insensible à
   la mise en forme) permet de reconnaître une annonce déjà collectée.
5. **Aucune source non autorisée.** Trois conditions sont exigées, sans quoi
   la source n'est pas collectée.
6. **Aucun martèlement.** Un délai de 10 secondes sépare deux requêtes, et le
   fichier `robots.txt` du site est respecté : une page interdite n'est pas
   lue.
7. **Aucune donnée personnelle.** Seules les coordonnées de candidature
   présentes dans l'annonce sont reprises.

---

## 6. Le Centre de veille

`/admin/veille/` — un point d'entrée unique dans l'administration.

| Bloc | Ce qu'on y fait |
|---|---|
| **État de la veille** | les compteurs : à vérifier, doublons, détectées, sources, collectes |
| **Collecter maintenant** | collecter une source, coller un lien, coller un texte |
| **Annonces à vérifier** | ouvrir et corriger le brouillon dans la liste des offres |
| **Doublons potentiels** | **confirmer** ou **écarter** le rapprochement |
| **Annonces détectées** | trouvées mais pas encore analysées |
| **Annonces rejetées** | refusées par l'équipe |
| **Sources surveillées** | mode, autorisation, dernière collecte, résultat |
| **Historique des collectes** | les vingt derniers passages |

### Publier une annonce collectée

1. Ouvrir l'annonce dans **Annonces à vérifier**.
2. Corriger et compléter ce qui manque (l'IA ne remplit que ce qui est écrit).
3. Vérifier la source : cocher **« source vérifiée »**.
4. Enregistrer, puis utiliser l'action **« Valider et publier »** de la liste
   des offres.

---

## 7. L'assistant de decouverte des sources

Trouver soi-meme les sites d'emplois, et deviner le selecteur qui
designe les annonces, cela prend du temps et cela ne se fait bien que
si l'on connait deja le web burkinabe. L'assistant prend cette
recherche en charge.

### Le principe : deux tetes

Un modele de conversation ne navigue pas sur le web. Il propose donc,
et le code verifie :

| Qui | Fait quoi |
|---|---|
| **Le modele** | propose des adresses de pages d'offres qu'il connait, avec le type de site et la raison |
| **Le code** | va verifier chaque adresse et repond : page d'offres ? combien d'annonces ? quel selecteur ? |
| **Le moteur de recherche** | en option, elargit la decouverte (Brave Search ou SearXNG) |
| **L'equipe** | autorise ou refuse, c'est elle qui decide |

### Lancer une decouverte

Depuis le Centre de veille : section **Sources proposées par l'assistant**.

Depuis le terminal :

```
python manage.py veille_decouverte
python manage.py veille_decouverte "offres d'emploi pour des ONG au Burkina Faso"
python manage.py veille_decouverte --maximum 5 --delai 20
```

Le rapport est reparti en trois sections : les sources proposees, celles
a verifier, et celles ecartees.

### Ce que verifie l'assistant

| Verification | Comment |
|---|---|
| Est-ce une source d'offres ? | mots-cles d'offres dans la page |
| Ou sont les annonces ? | blocs qui se repetent, notes selon la presence d'une date, d'un bouton « postuler », d'un intitule de poste, d'un lieu |
| La reprise est-elle permise ? | lecture de `/mentions-legales`, `/conditions`, `/legal`, `/privacy`... et jugement phrase par phrase |
| Est-ce un reseau social ? | liste de domaines exclus : la veille y reste manuelle |
| La page est-elle lisible ? | les pages construites en JavaScript sont ecartees |

### Les trois verdicts

| Verdict | Quand | Ce que l'equipe doit faire |
|---|---|---|
| **source** | le site **autorise explicitement** la reprise | autoriser, sans reserve |
| **a verifier** | le site ne dit rien, ou ne parle que de « tous droits reserves » | motiver l'autorisation dans la note |
| **ecartee** | le site **interdit** la reprise, robots.txt bloque, page morte ou en JavaScript, pas un site d'offres | rien |

**Une interdiction l'emporte toujours sur une autorisation** : si une
phrase dit « la reproduction est interdite », la source est ecartee
meme si une autre dit « autorisee ».

### Autoriser une source

Dans le Centre de veille, chaque proposition propose une **note
d'autorisation** pre-remplie avec le constat de l'assistant. Quand la
reprise n'est pas etablie par le site, cette note est **obligatoire** :
c'est l'equipe qui ecrit pourquoi elle accorde cette autorisation.

Au moment d'autoriser, la page est **reverifiee** : une proposition peut
avoir ete faite plusieurs jours plus tot, et le site a pu changer. Si
la page n'est plus lisible, l'autorisation est refusee et il faut
relancer une decouverte.

La source creee rejoint la collecte automatique, avec les memes regles
que les autres : delai de dix secondes, robots.txt, et **jamais de
publication automatique**.

### Le moteur de recherche, en option

Sans rien configurer, l'assistant s'appuie sur les adresses que le
modele propose. Avec un moteur, il elargit :

```
# Brave Search (inscription gratuite sur brave.com/search/api)
BRAVE_SEARCH_API_KEY=...

# ou SearXNG (auto-heberge, gratuit)
SEARXNG_URL=https://...
```

### Les limites, à connaître

1. Le modele ne visite pas les pages : il propose, le code verifie.
2. La selection du bon bloc reste une heuristique : l'echantillon est
   montre avant l'autorisation.
3. Les sites en JavaScript sont ecartees. Les lire demanderait un
   navigateur sans interface.
4. Chaque verification respecte le delai de dix secondes : huit
   adresses, c'est environ une minute et demie.

---

## 8. Les commandes

| Commande | Rôle |
|---|---|
| `python manage.py collect_offers` | collecte toutes les sources autorisées |
| `python manage.py collect_offers --source "Emploi du Faso"` | collecte une seule source |
| `python manage.py collect_offers --dry-run` | liste les sources qui seraient collectées |
| `python manage.py collect_offers --scheduled` | utilisé par la tâche planifiée |
| `python manage.py veille_essai "…"` | teste le service d'IA sur un texte |
| `python manage.py veille_selecteur <url>` | trouve le sélecteur d'une page |

---

## 9. Activer la collecte automatique

Comme les sauvegardes, la veille ne se planifie pas toute seule : elle repose
sur une tâche planifiée installée sur la machine qui héberge le site.

Les commandes prêtes à copier sont affichées dans le Centre de veille
(section « Activer la collecte automatique »).

**Sous Linux (cron)**, toutes les six heures :

```
0 */6 * * * cd /chemin/vers/le/projet && /chemin/vers/le/projet/.venv/bin/python manage.py collect_offers --scheduled
```

**Sous Windows (Tâche planifiée)** :

```
schtasks /Create /SC HOURLY /MO 6 /TN "Faso Job Veille" /TR "…" /F
```

---

## 10. Ce qui a été ajouté au projet

### Modèles

| Modèle | Rôle |
|---|---|
| `CollectedAnnouncement` | la trace de chaque annonce collectée |
| `VeilleRun` | l'historique des passages de collecte |
| `Source` | cinq champs ajoutés : mode de collecte, surveillance, paramètres, autorisation, dernier résultat |
| `Offer` | trois champs ajoutés : `missions`, `required_profile`, `required_education` |

### Migration

`offres/migrations/0018_offer_missions_offer_required_education_and_more.py`

### Code

| Fichier | Rôle |
|---|---|
| `offres/veille/http.py` | la seule sortie réseau : délai, `robots.txt`, erreurs |
| `offres/veille/collectors.py` | les quatre méthodes de collecte |
| `offres/veille/ia.py` | le client du service d'IA et l'orchestration des appels |
| `offres/veille/schema.py` | le contrat d'extraction, les prompts, la validation |
| `offres/veille/dedup.py` | le rapprochement avec le catalogue |
| `offres/veille/pipeline.py` | le parcours complet, de la collecte au brouillon |
| `offres/veille/admin_views.py` | le Centre de veille |
| `offres/veille/scheduling.py` | les instructions de planification |
| `offres/veille/decouverte.py` | la verification des adresses proposees |
| `offres/veille/decouverte_ia.py` | les propositions du modele et le moteur de recherche |
| `offres/veille/decouverte_admin.py` | l enregistrement des propositions et la decision de l'equipe |

### Tests

| Fichier | Ce qu'il couvre |
|---|---|
| `offres/test_veille.py` | les modèles et les règles de publication |
| `offres/test_veille_ia.py` | l'extraction, la validation, le transport |
| `offres/test_veille_collectors.py` | les collecteurs, le délai, `robots.txt` |
| `offres/test_veille_dedup.py` | le rapprochement et les motifs |
| `offres/test_veille_pipeline.py` | le parcours complet, de la collecte au brouillon |
| `offres/test_veille_admin.py` | le Centre de veille et ses actions |
| `offres/test_veille_decouverte.py` | la verification des sources proposees |
| `offres/test_veille_decouverte_admin.py` | la decision de l'equipe sur une proposition |

Aucun test ne sort sur le réseau : les requêtes sont simulées.
