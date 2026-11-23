"""Decouverte des sources : ce que l assistant constate sur une adresse.

Le modele propose des adresses ; ce module va les verifier. Il ne
decide jamais : il constate, il score, il explique. La decision
d autoriser reste a l equipe.

Trois verdicts possibles :

- **source** : la reprise est explicitement permise ;
- **a_verifier** : rien n est dit, ou le site ne parle que de ses
  droits d auteur generiques. L equipe doit alors motiver son
  autorisation ;
- **ecartee** : le site interdit la reprise, la page est protegee par
  robots.txt, ou elle ne contient pas d offres.

Le module respecte toujours les memes regles que la collecte : delai
de dix secondes, fichier robots.txt lu, agent identifie.
"""

import logging
import re
from urllib.parse import urlparse

from . import http
from .collectors import candidate_selectors, parse_html

logger = logging.getLogger(__name__)

# Domaines que l assistant ne doit jamais proposer : leurs conditions
# d utilisation interdisent la reprise automatique, et le projet les
# laisse en saisie manuelle.
DOMAINES_INTERDITS = (
    'facebook.com',
    'fb.com',
    'instagram.com',
    'linkedin.com',
    'lnkd.in',
    'twitter.com',
    'x.com',
    'tiktok.com',
    'whatsapp.com',
    'wa.me',
    'youtube.com',
    't.me',
    'telegram.me',
    'reddit.com',
    'pinterest.com',
    'snapchat.com',
)

# Adresses ou le site peut expliquer ses conditions.
CHEMIN_CONDITIONS = (
    '/mentions-legales',
    '/mentions-legales/',
    '/legal-notice',
    '/legal',
    '/conditions-generales',
    '/conditions-dutilisation',
    '/conditions',
    '/legal-information',
    '/confidentialite',
    '/privacy',
    '/about/legal',
)

# Mots qui montrent qu une page parle d offres d emploi.
MOTS_OFFRES = (
    'offre',
    'offres',
    'emploi',
    'emplois',
    'poste',
    'postes',
    'recrutement',
    'recrute',
    'candidature',
    'candidater',
    'postuler',
    'cv',
    'carriere',
    'vacancy',
    'job',
    'jobs',
)

# Mots qui montrent qu un bloc est bien une annonce.
MOTS_ANNONCE = (
    'offre',
    'emploi',
    'poste',
    'recrutement',
    'postuler',
    'candidature',
    'cv',
    'cdi',
    'cdd',
    'stage',
    'mission',
    'consultant',
    'assistant',
    'charge',
    'responsable',
    'agent',
    'comptable',
    'chauffeur',
    'developpeur',
    'technicien',
    'ingenieur',
    'vendeur',
    'caissiere',
    'magasinier',
    'gardien',
    'cuisinier',
    'conducteur',
)

# Mots des villes et pays : une annonce en contient presque toujours un.
MOTS_LIEUX = (
    'ouagadougou',
    'bobo-dioulasso',
    'ouahigouya',
    'koudougou',
    'banfora',
    'kaya',
    'ouzzou',
    'tenkodogo',
    'fada ngourma',
    'gao',
    'dedougou',
    'ziniare',
    'lemana',
    'boulmi',
    'po',
    'tougan',
    'diapaga',
    'ouirza',
    'mangouya',
    'houndÃ©',
    'boromo',
    'pouytenga',
    'guinguil',
    'daolo',
    'batiÃ©',
    'bobo',
)

# Mots qui montrent qu une phrase parle de reprise de contenu.
MARQUEURS_REPRODUCTION = (
    'reproduction',
    'reprendre',
    'reprise',
    'reproduire',
    'rediffuser',
    'rediffusion',
    'citation',
    'citer',
    'copy',
)

# Mots qui montrent qu une phrase autorise.
MARQUEURS_PERMISSION = (
    'autorise',
    'autorisee',
    'autorises',
    'autorisees',
    'peut reproduire',
    'peut etre reproduit',
    'libre de reproduire',
    'accord de reprise',
    'may be reproduced',
    'permission to reproduce',
    'free to reproduce',
)

# Mots qui montrent qu une phrase refuse. La negation compte : une
# phrase qui dit "n est pas autorisee" est une interdiction.
MARQUEURS_INTERDICTION = (
    'interdit',
    'interdite',
    'interdits',
    'interdites',
    'aucune reproduction',
    'pas autorise',
    'pas autorisee',
    'sans autorisation',
    'reserve tous droits',
    'tous droits reserves',
    'soumise a autorisation',
    'soumises a autorisation',
    'do not reproduce',
    'no reproduction',
    'unauthorized',
)


def _phrases(html):
    """Decoupe un texte en phrases exploitables."""
    morceaux = re.split(r'[.!?;\n]+', html or '')
    return [morceau.strip() for morceau in morceaux if len(morceau.strip()) >= 40]


def _juger_phrase(phrase):
    """Dit si une phrase autorise, interdit, ou ne dit rien.

    Renvoie ('permission'|'interdiction'|'', phrase).
    """
    contenu = normalize_text(phrase)
    if not any(
        normalize_text(marqueur) in contenu
        for marqueur in MARQUEURS_REPRODUCTION
    ):
        return '', phrase
    if any(
        normalize_text(marqueur) in contenu
        for marqueur in MARQUEURS_INTERDICTION
    ):
        return 'interdiction', phrase
    if any(
        normalize_text(marqueur) in contenu
        for marqueur in MARQUEURS_PERMISSION
    ):
        return 'permission', phrase
    return '', phrase

# Signes qu une page est construite en JavaScript : le code ne voit
# alors qu une coquille vide.
SIGNS_JAVASCRIPT = (
    'id="root"',
    "id='root'",
    'id="app"',
    'id="__next"',
    'id="__nuxt"',
    'ng-app',
    'data-reactroot',
)

VERDICT_SOURCE = 'source'
VERDICT_A_VERIFIER = 'a_verifier'
VERDICT_ECARTEE = 'ecartee'


class SourceCandidate:
    """Adresse proposÃ©e comme future source surveillÃ©e."""

    def __init__(self, url='', name='', kind='', why='', origin=''):
        self.url = (url or '').strip()
        self.name = (name or '').strip()
        self.kind = (kind or '').strip()
        self.why = (why or '').strip()
        self.origin = (origin or '').strip()

    def __repr__(self):
        return f'<SourceCandidate {self.url}>'


class VerificationReport:
    """Ce que l assistant a constatÃ© sur une adresse."""

    def __init__(self, url=''):
        self.url = url
        self.verdict = VERDICT_A_VERIFIER
        self.score = 0.0
        self.reasons = []
        self.selector = ''
        self.blocks_count = 0
        self.sample = ''
        self.page_title = ''
        self.kind = ''
        self.conditions_found = []
        self.conditions_quote = ''
        self.error = ''

    @property
    def is_source(self):
        return self.verdict == VERDICT_SOURCE

    @property
    def is_rejected(self):
        return self.verdict == VERDICT_ECARTEE

    def __repr__(self):
        return f'<VerificationReport {self.verdict} {self.url}>'


def domain_of(url):
    """Domaine d'une adresse, sans le Â« www. Â»."""
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return ''
    if host.startswith('www.'):
        host = host[4:]
    return host.split(':')[0]


def is_forbidden_domain(url):
    """Indique si l adresse est sur un site Ã  ne jamais proposer."""
    host = domain_of(url)
    if not host:
        return True
    for forbidden in DOMAINES_INTERDITS:
        if host == forbidden or host.endswith('.' + forbidden):
            return True
    return False


def normalize_text(value):
    """Texte en minuscules, sans accent ni ponctuation."""
    import unicodedata

    decomposed = unicodedata.normalize('NFKD', value or '')
    without_accents = ''.join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r'[^a-z0-9]+', ' ', without_accents.lower()).strip()


MOIS = (
    'janvier',
    'fevrier',
    'mars',
    'avril',
    'mai',
    'juin',
    'juillet',
    'aout',
    'septembre',
    'octobre',
    'novembre',
    'decembre',
)

# Seuil de qualite : en dessous, le bloc est un menu, un pied de page
# ou un encart, pas une annonce.
SEUIL_QUALITE = 3


def quality_of_block(text):
    """Note la ressemblance d un bloc avec une vraie annonce.

    Un menu qui contient le mot "emploi" ne vaut pas un point : une
    annonce porte une date, un bouton de candidature, un intitule de
    poste, un lieu.
    """
    content = normalize_text(text)
    if len(content) < 30:
        return 0

    score = 0
    if any(normalize_text(mot) in content for mot in MOTS_OFFRES):
        score += 1
    if any(normalize_text(mot) in content for mot in MOTS_ANNONCE):
        score += 1
    if any(normalize_text(mot) in content for mot in MOTS_LIEUX):
        score += 1
    if any(mois in content for mois in MOIS) or re.search(r'\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}', content):
        score += 2
    if any(normalize_text(mot) in content for mot in ('postuler', 'candidature', 'cv', 'deposer')):
        score += 2
    if any(normalize_text(mot) in content for mot in ('cdi', 'cdd', 'stage', 'contrat', 'temps plein', 'temps partiel')):
        score += 1
    return score


def looks_like_offer(text):
    """Indique si un bloc de page ressemble a une annonce d emploi."""
    return quality_of_block(text) >= SEUIL_QUALITE


def detect_javascript_page(html):
    """Indique si la page semble etre construite en JavaScript."""
    lowered = (html or '').lower()
    if any(signe.lower() in lowered for signe in SIGNS_JAVASCRIPT):
        return True
    # Une page sans presque aucun texte mais avec beaucoup de scripts :
    # le contenu est construit apres coup.
    soup = parse_html(html or '')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    text = soup.get_text(' ', strip=True)
    scripts = len(soup.find_all('script'))
    return len(text) < 400 and scripts > 3


def read_conditions(url, delay=None):
    """Cherche les conditions de reprise d un site.

    Renvoie (liste des pages trouvees, citation). Rien n est impose :
    une citation est relevee telle quelle, sans interpretation.
    """
    domain = domain_of(url)
    if not domain:
        return [], ''

    base = '%s://%s' % (urlparse(url).scheme or 'https', domain)
    pages = []
    citation = ''
    permission = ''

    for chemin in CHEMIN_CONDITIONS:
        adresse = base + chemin
        reponse = http.fetch(adresse, delay=delay)
        if not reponse.is_ok:
            continue
        if len(normalize_text(reponse.text)) < 120:
            continue
        pages.append(adresse)

        # Une interdiction l'emporte toujours sur une permission.
        for phrase in _phrases(reponse.text):
            verdict, texte = _juger_phrase(phrase)
            if verdict == 'interdiction':
                return pages, texte[:300]
            if verdict == 'permission' and not permission:
                permission = texte[:300]
        if permission:
            break

    return pages, permission


def classify_kind(html, url):
    """Devine le type de site, pour classer les trouvailles."""
    contenu = normalize_text(html)
    if any(normalize_text(mot) in contenu for mot in ('carriere', 'carrieres', 'nous rejoindre', 'rejoignez')):
        return 'Carriere d entreprise ou d institution'
    if any(normalize_text(mot) in contenu for mot in ('ministere', 'ministÃ¨re', 'gouvernement', 'commune', 'province')):
        return 'Site institutionnel'
    if any(normalize_text(mot) in contenu for mot in ('association', 'ong', 'projet', 'bailleur', 'unicef', 'giz', 'world bank')):
        return 'Organisation ou projet'
    if any(normalize_text(mot) in contenu for mot in ('emploi', 'recrutement', 'offre', 'poste')):
        return 'Portail d emploi'
    return 'Autre'


def verify_candidate(candidate, delay=None, deep=True):
    """Verifie une adresse proposee et renvoie son rapport.

    Le rapport dit ce que l assistant a constate. Il ne dit jamais
    Â« cette source est bonne Â» : il dit pourquoi elle convient, ou
    pourquoi elle ne convient pas.
    """
    rapport = VerificationReport(url=candidate.url)
    rapport.kind = candidate.kind or ''

    if is_forbidden_domain(candidate.url):
        rapport.verdict = VERDICT_ECARTEE
        rapport.reasons.append(
            'Ce site fait partie des reseaux sociaux : ses conditions '
            'utilisation interdisent la reprise automatique. La veille reste '
            'manuelle sur ces sources.'
        )
        return rapport

    reponse = http.fetch(candidate.url, delay=delay)
    if not reponse.is_ok:
        rapport.verdict = VERDICT_ECARTEE
        rapport.error = reponse.error
        rapport.reasons.append('Page inaccessible : %s' % reponse.error)
        return rapport

    html = reponse.text

    if detect_javascript_page(html):
        rapport.verdict = VERDICT_ECARTEE
        rapport.reasons.append(
            'La page est construite en JavaScript : la lecture automatique '
            'ne verrait qu une page vide. Une source qui ne se lit pas n est '
            'pas proposee.'
        )
        return rapport

    soup = parse_html(html)
    titre = soup.title.string.strip() if soup.title and soup.title.string else ''
    rapport.page_title = titre

    contenu = normalize_text(html)
    if not any(normalize_text(mot) in contenu for mot in MOTS_OFFRES):
        rapport.verdict = VERDICT_ECARTEE
        rapport.reasons.append(
            'La page ne parle pas d offres d emploi : ce n est pas une source.'
        )
        return rapport

    # On cherche le bloc qui designe les annonces.
    propositions = candidate_selectors(html, minimum=2)
    meilleure = None
    for selecteur, nombre, echantillon in propositions:
        qualite = quality_of_block(echantillon)
        if qualite < SEUIL_QUALITE:
            continue
        # On privilegie la qualite du bloc, puis le nombre d annonces.
        if meilleure is None or (qualite, nombre) > meilleure[3]:
            meilleure = (selecteur, nombre, echantillon, qualite)

    if meilleure is None:
        rapport.verdict = VERDICT_ECARTEE
        rapport.reasons.append(
            'Aucune zone repetitive qui ressemble a une annonce n a ete '
            'trouvee : la structure du site est trop changeante ou trop '
            'originale pour etre lue de facon fiable.'
        )
        return rapport

    rapport.selector = meilleure[0]
    rapport.blocks_count = meilleure[1]
    rapport.sample = meilleure[2]

    if not rapport.kind:
        rapport.kind = classify_kind(html, candidate.url)

    # Conditions de reprise.
    if deep:
        pages, citation = read_conditions(candidate.url, delay=delay)
        rapport.conditions_found = pages
        rapport.conditions_quote = citation
        if citation:
            contenu_conditions = normalize_text(citation)
            if any(
                normalize_text(marqueur) in contenu_conditions
                for marqueur in MARQUEURS_INTERDICTION
            ):
                rapport.verdict = VERDICT_ECARTEE
                rapport.reasons.append(
                    'Le site interdit explicitement la reprise : Â« %s Â». '
                    'Source ecartee.' % citation
                )
                return rapport

    # Score : nombre d annonces trouvees, et_permissions...
    score = 0.0
    score += min(0.5, rapport.blocks_count * 0.05)
    if rapport.selector:
        score += 0.2
    if rapport.conditions_quote:
        score += 0.2
    if rapport.kind:
        score += 0.1
    rapport.score = round(min(score, 1.0), 3)

    if rapport.conditions_quote:
        rapport.verdict = VERDICT_SOURCE
        rapport.reasons.append(
            'Le site autorise explicitement la reprise (Â« %s Â»).' % rapport.conditions_quote
        )
    else:
        rapport.verdict = VERDICT_A_VERIFIER
        rapport.reasons.append(
            'Aucune mention de reprise trouvee sur le site. Les conditions '
            'ne sont pas etablies : l autorisation doit etre motivee par '
            'l equipe.'
        )

    rapport.reasons.append(
        '%d annonce(s) detectee(s) avec le selecteur Â« %s Â».'
        % (rapport.blocks_count, rapport.selector)
    )

    return rapport


def verify_candidates(candidates, delay=None, deep=True):
    """Verifie une liste d adresses et renvoie les rapports."""
    rapports = []
    for candidate in candidates:
        if is_forbidden_domain(candidate.url):
            rapports.append(verify_candidate(candidate, delay=delay, deep=False))
            continue
        rapports.append(verify_candidate(candidate, delay=delay, deep=deep))
    return rapports
