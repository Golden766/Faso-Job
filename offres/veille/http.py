"""Acces aux pages autorisees pour la veille.

C'est le seul endroit du projet qui sort sur le reseau pour la veille.
Quatre regles s'y appliquent :

1. **un delai d attente entre deux requetes** : la veille ne martele
   pas un site. Le delai par defaut est de 10 secondes et chaque
   source peut en choisir un autre ;
2. **le fichier robots.txt est lu** : une page interdite n est pas
   recuperee, et le fichier n est telecharge qu'une fois par site ;
3. **les erreurs sont rendues, jamais levees** : une source qui tombe
   en panne n arrete pas la collecte des autres ;
4. **la veille s identifie** : elle dit qui elle est.
"""

import inspect
import logging
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

logger = logging.getLogger(__name__)

# Python 3.13 a inverse l ordre des arguments de `can_fetch` :
# l agent vient avant l adresse. Le projet peut tourner sur differentes
# versions de Python : l ordre est verifie une fois, a l import.
_CAN_FETCH_TAKES_USERAGENT_FIRST = (
    'useragent' in inspect.signature(RobotFileParser.can_fetch).parameters
)

# Agent envoye aux sites. Il dit clairement ce qu il est : la veille
# est un outil editorial, pas un robot furtif.
USER_AGENT = 'FasoJob-Veille/1.0'

# Delai minimum entre deux requetes, en secondes.
DEFAULT_DELAY_SECONDS = 10

# Delai maximal d'attente d'une reponse, en secondes.
DEFAULT_TIMEOUT = 30

_delay_seconds = DEFAULT_DELAY_SECONDS
_last_request_at = None
_robots_cache = {}


class FetchResult:
    """Resultat de la lecture d'une page."""

    def __init__(self, url='', status_code=0, text='', error='', blocked=False, elapsed=0.0):
        self.url = url
        self.status_code = status_code
        self.text = text
        self.error = error
        self.blocked = blocked
        self.elapsed = elapsed

    @property
    def is_ok(self):
        """Indique si la page a ete lue."""
        return bool(
            self.status_code == 200
            and self.text
            and not self.error
            and not self.blocked
        )

    def __repr__(self):
        return f'<FetchResult {self.status_code} {self.url}>'


def set_delay(seconds):
    """Fixe le delai minimum entre deux requetes."""
    global _delay_seconds
    _delay_seconds = _positive_int(seconds, DEFAULT_DELAY_SECONDS)


def _positive_int(value, default):
    """Lit un nombre entier positif, sans jamais planter.

    Une valeur absente ou mal saisie prend la valeur de repli : une
    source configuree de travers ne doit pas arreter la collecte.
    """
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def get_delay():
    """Renvoie le delai minimum entre deux requetes."""
    return _delay_seconds


def reset_delay():
    """Rétablit le délai par défaut."""
    global _delay_seconds
    _delay_seconds = DEFAULT_DELAY_SECONDS


def _wait_for_turn(delay):
    """Attend que le délai entre deux requetes soit écoulé."""
    global _last_request_at
    if delay and _last_request_at is not None:
        remaining = delay - (time.monotonic() - _last_request_at)
        if remaining > 0:
            time.sleep(remaining)
    _last_request_at = time.monotonic()


def _robots_parser(url):
    """Renvoie l'analyseur du fichier robots.txt du site.

    Le fichier n'est telecharge qu'une fois par site. Un fichier absent
    ou illisible ne bloque rien : ce qui n'est pas interdit est
    permis.
    """
    parsed = urlparse(url)
    host = parsed.netloc
    if host in _robots_cache:
        return _robots_cache[host]

    parser = RobotFileParser()
    robots_url = f'{parsed.scheme}://{host}/robots.txt'
    try:
        response = requests.get(
            robots_url,
            timeout=DEFAULT_TIMEOUT,
            headers={'User-Agent': USER_AGENT},
        )
        if response.status_code == 200:
            parser.parse(response.text.splitlines())
        else:
            parser.parse([])
    except Exception:
        parser.parse([])

    _robots_cache[host] = parser
    return parser


def clear_robots_cache():
    """Oublie les fichiers robots.txt deja lus (utile dans les tests)."""
    _robots_cache.clear()


def robots_allows(url):
    """Indique si le fichier robots.txt du site autorise cette page."""
    try:
        parser = _robots_parser(url)
        if _CAN_FETCH_TAKES_USERAGENT_FIRST:
            return parser.can_fetch(USER_AGENT, url)
        return parser.can_fetch(url, USER_AGENT)
    except Exception:
        # Un fichier robots.txt illisible ne doit pas arreter la veille.
        return True


def fetch(url, delay=None, respect_robots=True, timeout=None):
    """Lit une page et renvoie son contenu.

    Ne leve jamais d'exception : un refus du site, un delai depasse ou
    une coupure de reseau sont rendus dans le resultat.
    """
    if not url or not url.lower().startswith(('http://', 'https://')):
        return FetchResult(
            url=url,
            error='Adresse invalide : une page se lit par http ou https.',
        )

    waited = get_delay() if delay is None else _positive_int(delay, get_delay())
    _wait_for_turn(waited)

    if respect_robots and not robots_allows(url):
        return FetchResult(
            url=url,
            blocked=True,
            error='Page interdite par le fichier robots.txt du site.',
        )

    started = time.monotonic()
    try:
        response = requests.get(
            url,
            timeout=timeout or DEFAULT_TIMEOUT,
            headers={
                'User-Agent': USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            },
        )
    except requests.exceptions.Timeout:
        return FetchResult(url=url, error='Le site ne repond pas dans le delai imparti.')
    except requests.exceptions.RequestException as error:
        logger.warning('Lecture impossible de %s : %s', url, error)
        return FetchResult(url=url, error='Site injoignable : %s' % error)

    elapsed = time.monotonic() - started

    if response.status_code != 200:
        return FetchResult(
            url=url,
            status_code=response.status_code,
            error='Le site a repondu par le code %s.' % response.status_code,
            elapsed=elapsed,
        )

    return FetchResult(
        url=url,
        status_code=200,
        text=response.text or '',
        elapsed=elapsed,
    )
