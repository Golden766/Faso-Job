"""Collecte des annonces : lien saisi, texte saisi, page de liste, flux.

Quatre manieres de trouver une annonce :

- un lien colle par l administrateur ;
- un texte colle par l administrateur ;
- une page de liste d offres, lue regulierement ;
- un flux RSS ou Atom : c'est la forme que prennent la plupart des
  newsletters.

Facebook et WhatsApp ne sont pas collectes automatiquement : leurs
conditions d'utilisation ne le permettent pas. L' administrateur y
colle le texte de l annonce, et la suite est identique.

Aucune de ces methodes ne leve d exception : une source qui tombe en
panne est signalee, les autres continue.
"""

import hashlib
import logging
from datetime import date
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from . import http
from .schema import normalize

logger = logging.getLogger(__name__)

# Nombre d'annonces retenues au maximum lors d'un passage.
DEFAULT_LIMIT = 20


class CollectedItem:
    """Annonce trouvee, avant analyse.

    Elle porte le texte brut et son adresse : c'est la matiere qui sera
    ensuite analysee et confrontee aux doublons.
    """

    def __init__(self, url='', title='', text='', published_at=None):
        self.url = url
        self.title = title
        self.text = text
        self.published_at = published_at

    @property
    def content_hash(self):
        """Empreinte du contenu, insensible a la mise en forme."""
        return content_hash(self.text)

    def __repr__(self):
        return f'<CollectedItem {self.title or self.url}>'


class CollectionResult:
    """Ce qu'un passage de collecte a produit.

    Les erreurs sont rassemblees ici : une source qui echoue est
    signalee, elle n'interrompt pas les autres.
    """

    def __init__(self):
        self.items = []
        self.errors = []

    def add_item(self, item):
        self.items.append(item)

    def add_error(self, message):
        self.errors.append(message)

    @property
    def count(self):
        return len(self.items)

    @property
    def is_empty(self):
        return not self.items

    def __repr__(self):
        return f'<CollectionResult {self.count} annonce(s), {len(self.errors)} erreur(s)>'


def content_hash(text):
    """Empreinte d'un contenu.

    Deux annonces identiques ont la meme empreinte, meme si leur mise
    en forme differe. C'est ce qui evite de collecter deux fois la
    meme annonce.
    """
    return hashlib.sha256(normalize(text).encode('utf-8')).hexdigest()


def parse_html(html):
    """Prepare le HTML pour la lecture.

    Le parseur rapide est utilise quand il est disponible ; sinon le
    parseur de la bibliotheque standard prend le relais.
    """
    try:
        return BeautifulSoup(html, 'lxml')
    except Exception:
        return BeautifulSoup(html, 'html.parser')


def _page_title_and_text(html):
    """Renvoie le titre et le texte lisible d'une page."""
    soup = parse_html(html)
    for tag in soup(['script', 'style', 'noscript', 'nav', 'footer']):
        tag.decompose()

    title = ''
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        heading = soup.find('h1')
        if heading:
            title = heading.get_text(strip=True)

    text = soup.get_text('\n', strip=True)
    return title, text


def _first_link(element, base_url=''):
    """Renvoie le premier lien trouve dans un element."""
    link = element.find('a', href=True)
    if not link:
        return ''
    href = link['href'].strip()
    if not href or href.startswith('#'):
        return ''
    if base_url:
        return urljoin(base_url, href)
    return href


def _element_title(element, text):
    """Renvoie le titre d'une annonce trouvee dans une liste."""
    for name in ('h1', 'h2', 'h3', 'h4'):
        heading = element.find(name)
        if heading:
            title = heading.get_text(strip=True)
            if title:
                return title
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ''


def collect_text(text, url='', title=''):
    """Traite un texte d'annonce saisi a la main."""
    result = CollectionResult()
    if not text or not text.strip():
        result.add_error("Le texte de l'annonce est vide.")
        return result
    result.add_item(CollectedItem(url=url, title=title, text=text.strip()))
    return result


def collect_url(url, delay=None):
    """Lit une page d'annonce et la renvoie."""
    result = CollectionResult()
    fetch = http.fetch(url, delay=delay)
    if not fetch.is_ok:
        result.add_error(fetch.error or 'Page illisible.')
        return result
    title, text = _page_title_and_text(fetch.text)
    if not text:
        result.add_error('La page ne contient aucun texte lisible.')
        return result
    result.add_item(CollectedItem(url=url, title=title, text=text))
    return result


def collect_web_list(url, selector, limit=DEFAULT_LIMIT, delay=None):
    """Lit une page de liste d'annonces et en tire les annonces.

    `selector` designe les elements qui contiennent chaque annonce :
    c'est un selecteur CSS, saisi par l'equipe dans l'administration.
    """
    result = CollectionResult()
    if not selector:
        result.add_error(
            'Aucun selecteur d\'annonces n\'est renseigne pour cette source.'
        )
        return result

    fetch = http.fetch(url, delay=delay)
    if not fetch.is_ok:
        result.add_error(fetch.error or 'Page illisible.')
        return result

    soup = parse_html(fetch.text)
    elements = soup.select(selector)
    if not elements:
        result.add_error(
            'Aucune annonce trouvee sur la page avec le selecteur « %s ». '
            'Le selecteur a peut-etre change sur le site.' % selector
        )
        return result

    for element in elements[:max(1, int(limit))]:
        text = element.get_text('\n', strip=True)
        if not text:
            continue
        result.add_item(
            CollectedItem(
                url=_first_link(element, url),
                title=_element_title(element, text),
                text=text,
            )
        )
    return result


def _local_name(tag):
    """Nom d'une balise, sans son espace de noms."""
    return tag.split('}')[-1].lower()


def _child_text(element, names):
    """Texte du premier enfant portant l'un des noms donnes."""
    for child in element:
        if _local_name(child.tag) in names:
            text = ''.join(child.itertext()).strip()
            if text:
                return text
    return ''


def _child_link(element):
    """Adresse de l'entree d'un flux."""
    for child in element:
        if _local_name(child.tag) != 'link':
            continue
        href = child.attrib.get('href', '').strip()
        if href:
            return href
        text = (child.text or '').strip()
        if text:
            return text
    return ''


def _child_date(element):
    """Date de publication d'une entree de flux."""
    text = _child_text(element, ('pubdate', 'published', 'updated', 'date'))
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).date()
    except (TypeError, ValueError):
        pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def collect_feed(url, limit=DEFAULT_LIMIT, delay=None):
    """Lit un flux RSS ou Atom et en tire les annonces."""
    result = CollectionResult()
    fetch = http.fetch(url, delay=delay)
    if not fetch.is_ok:
        result.add_error(fetch.error or 'Flux illisible.')
        return result

    try:
        root = ElementTree.fromstring(fetch.text)
    except ElementTree.ParseError as error:
        result.add_error('Flux illisible : %s' % error)
        return result

    entries = [
        element for element in root.iter()
        if _local_name(element.tag) in ('item', 'entry')
    ]
    if not entries:
        result.add_error('Le flux ne contient aucune annonce.')
        return result

    for entry in entries[:max(1, int(limit))]:
        title = _child_text(entry, ('title',))
        description = _child_text(entry, ('description', 'summary', 'content'))
        if description:
            description = BeautifulSoup(
                description, 'html.parser'
            ).get_text('\n', strip=True)
        link = _child_link(entry)
        if not title and not description:
            continue
        result.add_item(
            CollectedItem(
                url=link,
                title=title,
                text=description or title,
                published_at=_child_date(entry),
            )
        )
    return result


def candidate_selectors(html, minimum=2):
    """Propose les selecteurs CSS qui designent les annonces d'une page.

    Une page d'emplois ne dit pas ou sont ses annonces : il faut le
    dire. Cette fonction regarde la page et propose les blocs qui se
    repetent — c'est a ces blocs que la veille peut s'interesser.

    Chaque proposition est un couple (selecteur, nombre d'elements).
    """
    soup = parse_html(html)
    counts = {}
    samples = {}

    for element in soup.find_all(True):
        # Un bloc d'annonce contient presque toujours un lien.
        if not element.find('a', href=True):
            continue
        classes = element.get('class') or []
        if not classes:
            continue
        selector = '%s.%s' % (element.name, '.'.join(classes[:2]))
        counts[selector] = counts.get(selector, 0) + 1
        if selector not in samples:
            samples[selector] = element.get_text('\n', strip=True)

    proposals = [
        (selector, count) for selector, count in counts.items() if count >= minimum
    ]
    proposals.sort(key=lambda item: (-item[1], item[0]))
    return [(selector, count, samples[selector]) for selector, count in proposals]


def _positive_int(value, default):
    """Lit un nombre entier positif, sans jamais planter.

    Une valeur absente ou mal saisie prend la valeur de repli : une
    source configuree de travers ne doit pas arreter la collecte.
    """
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def collect_source(source, delay=None):
    """Collecte les annonces d'une source, selon son mode de collecte.

    C'est le point d'entree du pipeline : la source porte son mode,
    son adresse et son selecteur.
    """
    from ..models import Source

    # La configuration est saisie a la main : elle peut contenir
    # n'importe quel JSON. Seul un objet separe par des cles est
    # exploitable ; le reste est ignore sans interrompre la collecte.
    config = source.watch_config
    if not isinstance(config, dict):
        config = {}
    method = source.collection_method

    if method == Source.COLLECTION_METHOD_WEB:
        url = config.get('url') or source.url
        selector = config.get('selector') or ''
        limit = _positive_int(config.get('limit'), DEFAULT_LIMIT)
        return collect_web_list(
            url, selector, limit=limit, delay=delay or config.get('delay_seconds')
        )

    if method in (Source.COLLECTION_METHOD_RSS, Source.COLLECTION_METHOD_NEWSLETTER):
        url = config.get('url') or source.url
        limit = _positive_int(config.get('limit'), DEFAULT_LIMIT)
        return collect_feed(
            url, limit=limit, delay=delay or config.get('delay_seconds')
        )

    result = CollectionResult()
    result.add_error(
        'Le mode de collecte « %s » n\'est pas automatise : l\'annonce est '
        'saisie a la main.' % (source.get_collection_method_display() or method)
    )
    return result
