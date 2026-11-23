# Plan de d?veloppement d?taill? ? plateforme d'opportunit?s professionnelles

**Version :** 0.2 ? orientation Django retenue  
**Date :** 20 octobre 2026  
**Statut :** proposition ? valider pour la mise en place du d?p?t de code  
**D?pendances :** sp?cification g?n?rale v0.1, architecture fonctionnelle v0.1, mod?le conceptuel de donn?es v0.1, parcours utilisateurs v0.1, sp?cification des ?crans v0.3, wireframes v0.2, guide visuel v0.2 et architecture technique v0.2.

> Ce document d?crit l'ordre de r?alisation, les livrables attendus, les d?pendances et les crit?res de validation. Il ne repr?sente pas un engagement de calendrier. La stack est maintenant orient?e vers Python et Django, avec PostgreSQL, templates Django et administration Django.

## 1. But du plan

D?velopper le MVP en petites unit?s coh?rentes et v?rifiables, avec l'aide d'une IA, sans lui d?l?guer implicitement les d?cisions m?tier. Chaque phase doit laisser un r?sultat fonctionnel ou une base technique v?rifi?e avant que la suivante commence.

## 2. P?rim?tre retenu pour le MVP

Le MVP doit permettre de :

- consulter publiquement des offres sans compte candidat ;
- rechercher et filtrer les offres actives ;
- ouvrir une fiche d'offre structur?e avec source et statuts de contr?le explicites ;
- contacter l'employeur par le canal indiqu?, notamment WhatsApp, un site externe, email, t?l?phone ou d?p?t physique ;
- partager une offre avec une URL stable ;
- collecter et publier manuellement des annonces depuis l'administration ;
- accepter des propositions d'annonces via un formulaire, toujours soumises ? contr?le ;
- traiter des signalements d'offres inexactes, suspectes ou ferm?es ;
- mesurer des interactions de base sans pr?tendre conna?tre les candidatures ou recrutements qui ont lieu hors de la plateforme.

### Hors p?rim?tre du premier lancement

- comptes candidats et CVth?que ;
- candidature h?berg?e, messagerie interne et suivi des candidatures ;
- comptes employeurs autonomes et publication automatique ;
- paiement, annonces sponsoris?es et abonnement ;
- scraping automatis? ;
- matching par IA et classement automatique ;
- application mobile native ;
- d?ploiement multi-pays avec r?gles locales compl?tes.

## 3. Hypoth?ses structurantes

| Sujet | Hypoth?se de d?part | Statut |
|---|---|---|
| March? pilote | Bobo-Dioulasso, ? confirmer avant lancement | Provisoire |
| Catalogue | Un seul catalogue public pour toutes les sources | Valid? au niveau fonctionnel |
| Publication | Toute annonce passe par un contr?le ?ditorial | Valid? au niveau fonctionnel |
| Candidats | Consultation gratuite sans compte obligatoire | Valid? pour le MVP |
| Administration | Un r?le administrateur au lancement | Recommand? pour le MVP |
| Interface | Bleu ciel dominant, vert secondaire, WhatsApp r?serv? au canal sp?cifique | Direction visuelle retenue |
| Stack retenue | Python, Django, PostgreSQL, templates Django, CSS, administration Django | Valid?e |
| H?bergement commercial | Ne pas consid?rer un plan gratuit non commercial comme cible de production | ? confirmer avant d?ploiement |

## 4. Strat?gie de r?alisation

### Approche : monolithe modulaire et tranches verticales

Le site public, l'administration et les r?gles m?tier d?marrent dans une application Django unique. On s?pare le code par domaine (offres, sources, soumissions, signalements, statistiques) sans multiplier les services d?ploy?s.

Chaque fonctionnalit? suit autant que possible une petite tranche compl?te : donn?es et validation, traitement c?t? serveur, interface, tests et documentation. Cela ?vite de construire d'abord toutes les interfaces fictives puis de d?couvrir que les r?gles ou la base ne les prennent pas en charge.

### R?gle de travail avec l'IA

L'IA ne doit pas construire plusieurs phases ? la fois. Pour chaque t?che, elle doit :

1. lire les documents de r?f?rence pertinents ;
2. reformuler l'objectif et les crit?res d'acceptation ;
3. annoncer les fichiers qu'elle pr?voit de cr?er ou modifier ;
4. respecter les d?cisions valid?es et marquer toute nouvelle proposition comme provisoire ;
5. ?crire ou mettre ? jour les tests ;
6. ex?cuter les contr?les disponibles ;
7. r?sumer les changements, r?sultats de test, limites et d?cisions restantes.

## 5. Phases de d?veloppement

### Phase 0 ? Pr?paration et gel des d?cisions minimales

**Objectif :** pr?parer un point de d?part sans chercher ? trancher tous les d?tails secondaires.

**Actions :**
- pr?parer l'environnement Windows avec Python, VS Code et Git ;
- cr?er un environnement virtuel `venv` ;
- confirmer le d?p?t de travail et les d?pendances Python ;
- d?finir la structure globale du projet Django ;
- choisir la strat?gie d'h?bergement compatible avec un lancement commercial ;
- noter les d?cisions ouvertes dans `docs/decision-log.md`.

**Livrables :** dossier `docs/`, journal des d?cisions, environnement de travail pr?t.

**Crit?res de validation :** les documents sont versionn?s ; les d?cisions bloquantes sont prises ou explicitement signal?es ; aucun secret r?el n'est inclus.

### Phase 1 ? Initialisation du projet Django et garde-fous

**Objectif :** obtenir une application minimale ex?cutable et v?rifiable.

**Actions :**
- initialiser le projet Django ;
- configurer le settings, le `venv` et les variables d'environnement ;
- pr?parer PostgreSQL local ou via un environnement de test ;
- v?rifier le lancement local du serveur ;
- cr?er la structure initiale du d?p?t sans g?n?rer des dizaines de fichiers vides ;
- documenter les instructions d'installation et de d?marrage.

**Crit?res de validation :** installation propre, serveur local fonctionnel, configuration Django coh?rente, absence de secrets dans Git.

### Phase 2 ? Fondations UI et composants r?utilisables

**Objectif :** transformer la direction visuelle valid?e en composants coh?rents.

**Composants prioritaires :**
- en-t?te public et pied de page ;
- conteneur de page et syst?mes d'espacement ;
- bouton primaire, secondaire et de lien ;
- carte g?n?rique et carte d'offre ;
- badges de source et de v?rification ;
- champs, s?lecteurs, messages d'erreur, ?tat vide et chargement ;
- bouton de candidature selon le canal ;
- bouton `Voir l'offre` visible sur chaque carte ;
- cat?gories regroup?es dans l'accueil et filtres conserv?s dans les r?sultats.

**Crit?res de validation :** composants visibles sur mobile et ordinateur ; ?tats `focus`, `disabled`, erreur et chargement d?finis ; contraste v?rifi? ; pas de faux badges de confiance.

### Phase 3 ? Mod?le de donn?es, migrations et contr?le d'acc?s

**Objectif :** ?tablir la source de v?rit? avant de raccorder les pages ? des donn?es r?elles.

**Objets de d?part ? mod?liser :**
- offres ;
- sources ;
- relations entre offre et source ;
- cat?gories et localit?s ;
- contr?les de v?rification / historique d'?tat ;
- soumissions en attente ;
- signalements ;
- utilisateurs d'administration / r?les n?cessaires.

**Actions :**
- produire les migrations PostgreSQL versionn?es ;
- fixer les contraintes, cl?s ?trang?res, valeurs autoris?es et r?gles d'unicit? ;
- cr?er un jeu de donn?es fictives ;
- d?finir les r?gles d'acc?s : public en lecture pour les seules offres publi?es ; donn?es internes et soumissions priv?es ; ?critures par formulaires valid?s c?t? serveur ; administration prot?g?e.

**Crit?res de validation :** migrations r?ex?cutables ; les visiteurs ne lisent ni brouillons ni soumissions priv?es ; il n'est pas possible d'attribuer un statut publi? ou v?rifi? sans validation.

### Phase 4 ? D?veloppement du catalogue public

**Objectif :** livrer le parcours de consultation publique et la recherche d'offres.

**Livrables :**
- accueil ;
- catalogue de recherche ;
- fiche d'offre avec source, statut et canal r?el ;
- filtres et r?sultats partageables ;
- ?tats vide, erreur et offre ferm?e ;
- page de soumission d'une offre ou signalement.

**Crit?res de validation :** le parcours accueil ? r?sultats ? fiche ? canal de candidature fonctionne sur mobile et ordinateur ; les filtres persistent apr?s rechargement ; les coordonn?es invent?es ou non v?rifi?es ne sont pas pr?sent?es comme fiables.

### Phase 5 ? Administration, mod?ration et permissions

**Objectif :** s?curiser la publication et la v?rification des offres.

**Actions :**
- utiliser Django Admin comme base de travail ;
- adapter les permissions et les vues d'administration ;
- mettre en place le processus de v?rification des offres avant publication ;
- g?rer les soumissions et les signalements dans un espace s?curis? ;
- conserver l'historique des changements importants ;
- ajouter les autorisations n?cessaires pour le statut ?ditorial.

**Crit?res de validation :** seules les personnes autoris?es peuvent modifier l'?tat des offres ; une offre ne devient publique qu'apr?s contr?le ; une offre ferm?e quitte les r?sultats actifs.

### Phase 6 ? Tests, s?curit? et pr?paration du d?ploiement

**Objectif :** v?rifier la qualit?, la s?curit? et la pr?paration du lancement.

**Actions :**
- tester les r?gles de visibilit?, les filtres et les badges de statut ;
- v?rifier les destinations WhatsApp, t?l?phone, email et liens externes ;
- tester soumission priv?e, signalement et refus d'acc?s admin sans session ;
- s?curiser les secrets et les backups ;
- pr?parer la configuration de production et l'h?bergement futur ;
- confirmer les co?ts et la strat?gie de d?ploiement avant l'exploitation commerciale.

**Crit?res de validation :** parcours critiques test?s ; d?fauts bloquants corrig?s ; limites connues document?es ; donn?es de test ne sont pas publiques.

## 6. R?gles de qualit?

- Une t?che ? la fois, avec validation avant la suivante.
- Explications en fran?ais simple.
- Tests avant validation.
- S?curit? et protection des donn?es avant tout lancement.
- R?gles m?tier non n?gociables : provenance, v?rification, publication et disponibilit? restent distinctes.

## 7. Livrables attendus

- projet Django fonctionnel localement ;
- base PostgreSQL avec mod?les et migrations ;
- catalogue public avec filtres et fiche d'offre ;
- espace d'administration prot?g? ;
- soumissions et signalements ;
- documentation de pr?paration et de d?ploiement.

## 8. R?f?rences utiles

- Django ? site officiel : https://www.djangoproject.com/
- Django ? documentation des vues : https://docs.djangoproject.com/en/stable/topics/http/views/
- Django ? documentation des templates : https://docs.djangoproject.com/en/stable/topics/templates/
- Django Admin : https://docs.djangoproject.com/en/stable/ref/contrib/admin/
- PostgreSQL : https://www.postgresql.org/
- Python venv : https://docs.python.org/fr/3/library/venv.html
