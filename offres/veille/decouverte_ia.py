"""Les adresses que l assistant propose de verifier.

Deux sources d adresses :

1. **le modele** : il propose des sites qu il connait, avec le type de
   site et la raison. Il ne verifie rien lui-meme ;
2. **un moteur de recherche**, si l equipe en a configure un (Brave
   Search ou SearXNG). C est optionnel : sans cle, le modele suffit.

Dans les deux cas, l adresse passe ensuite par la verification de
`decouverte.py`. Aucune adresse n entre dans la collecte sans une
autorisation humaine.
"""

import json
import logging
import re
import urllib.parse

from . import ia
from .decouverte import SourceCandidate, is_forbidden_domain

logger = logging.getLogger(__name__)


def _text_field(value):
    """Renvoie un champ texte propre, ou une chaine vide si son type est invalide."""
    return value.strip() if isinstance(value, str) else ''


SYSTEM_PROMPT = (
    'Tu aides une equipe editoriale qui surveille des offres d emploi au '
    'Burkina Faso. Tu proposes des adresses de pages qui publient des '
    'offres d emploi. Tu ne visites pas les pages : tu proposes, et '
    'l equipe verifie. Tu ne proposes jamais de reseau social '
    '(Facebook, Instagram, LinkedIn, WhatsApp, X, TikTok).'
)

MODELE_PROMPT = """Propose des adresses de pages qui publient des offres d'emploi pour le Burkina Faso.

Contexte de la demande :
{demande}

Types de sources recherchees (dans cet ordre) :
1. Portails d emploi publics et sites institutionnels
2. Organisations, projets et bailleurs
3. Pages carriere d entreprises et d institutions burkinabes
4. Portaux d emploi generalistes et sites de recrutement
5. Journal local et pages emploi de presse

Regles :
- Donne entre 8 et 15 adresses.
- Une adresse par page qui liste des offres (pas la page d accueil seule).
- Les adresses doivent commencer par http:// ou https://.
- N invente pas d adresse : donne seulement des sites que tu connais reellement.
- Si tu ne connais pas assez de sites pour ce type, donne moins d adresses pour ce type plutot que d inventer.

Rends un objet JSON de la forme :
{{
  "sources": [
    {{"url": "https://...", "name": "Nom du site", "type": "type 1 a 5", "why": "une phrase"}},
    ...
  ]
}}
"""


def _parse_candidates(raw):
    """Lit la reponse du modele et rend la liste des adresses proposees."""
    from .schema import parse_json_answer

    try:
        payload = parse_json_answer(raw)
    except ValueError as erreur:
        logger.warning('Reponse du modele illisible : %s', erreur)
        return []

    entrees = payload.get('sources') or payload.get('resultats') or []
    if not isinstance(entrees, list):
        return []

    candidates = []
    for entree in entrees:
        if not isinstance(entree, dict):
            continue
        url = _text_field(entree.get('url'))
        if not url.lower().startswith(('http://', 'https://')):
            continue
        if is_forbidden_domain(url):
            continue
        kind = _text_field(entree.get('type')) or _text_field(entree.get('kind'))
        candidates.append(
            SourceCandidate(
                url=url,
                name=_text_field(entree.get('name')),
                kind=kind,
                why=_text_field(entree.get('why')),
                origin='modele',
            )
        )
    return candidates


def propose_par_modele(demande, adapter=None):
    """Demande au modele des adresses de pages a verifier."""
    adapter = adapter or ia.get_adapter()
    if not adapter.is_configured():
        return []

    prompt = MODELE_PROMPT.format(demande=demande.strip() or 'offres d emploi au Burkina Faso')

    try:
        raw = adapter.complete(prompt, SYSTEM_PROMPT)
    except ia.AiRequestError as erreur:
        logger.warning('Le service n a pas pu proposer de sources : %s', erreur)
        return []

    if not raw:
        return []
    return _parse_candidates(raw)


def _search_brave(requete, cle, nombre=10):
    """Recherche avec l API Brave (offre gratuite avec inscription)."""
    import urllib.request

    url = (
        'https://api.search.brave.com/res/v1/web/search?q=%s&count=%d'
        % (urllib.parse.quote(requete), nombre)
    )
    requete_http = urllib.request.Request(
        url,
        headers={
            'Accept': 'application/json',
            'X-Subscription-Token': cle,
        },
    )
    with urllib.request.urlopen(requete_http, timeout=30) as reponse:
        payload = json.loads(reponse.read().decode('utf-8'))
    resultats = (payload.get('web') or {}).get('results') or []
    return [
        {
            'url': resultat.get('url', ''),
            'name': resultat.get('title', ''),
            'why': resultat.get('description', ''),
        }
        for resultat in resultats
        if resultat.get('url')
    ]


def _search_searxng(requete, adresse, nombre=10):
    """Recherche avec un SearXNG auto-heberge."""
    import urllib.request

    url = '%s/search?q=%s&format=json&language=fr' % (
        adresse.rstrip('/'),
        urllib.parse.quote(requete),
    )
    requete_http = urllib.request.Request(
        url, headers={'User-Agent': 'FasoJob-Veille/1.0'}
    )
    with urllib.request.urlopen(requete_http, timeout=30) as reponse:
        payload = json.loads(reponse.read().decode('utf-8'))
    resultats = payload.get('results') or []
    return [
        {
            'url': resultat.get('url', ''),
            'name': resultat.get('title', ''),
            'why': resultat.get('content', ''),
        }
        for resultat in resultats[:nombre]
        if resultat.get('url')
    ]


def moteur_recherche_disponible():
    """Indique quel moteur de recherche est configure, s'il y en a un."""
    from django.conf import settings

    if getattr(settings, 'BRAVE_SEARCH_API_KEY', ''):
        return 'brave'
    if getattr(settings, 'SEARXNG_URL', ''):
        return 'searxng'
    return ''


def propose_par_recherche(demande, requetes=None, nombre=10):
    """Cherche des adresses avec le moteur configure.

    Renvoie une liste vide si aucun moteur n est configure : la
    recherche est une aide, pas une obligation.
    """
    from django.conf import settings

    requetes = requetes or [
        'offres emploi Burkina Faso site:bf',
        'recrutement Burkina Faso offres',
        'emploi Burkina Faso %s' % (demande.strip() or 'offres'),
    ]

    moteur = moteur_recherche_disponible()
    if not moteur:
        return []

    resultats = []
    for requete in requetes:
        try:
            if moteur == 'brave':
                trouves = _search_brave(requete, settings.BRAVE_SEARCH_API_KEY, nombre)
            else:
                trouves = _search_searxng(requete, settings.SEARXNG_URL, nombre)
        except Exception as erreur:
            logger.warning('Recherche impossible (« %s ») : %s', requete, erreur)
            continue

        for trouve in trouves:
            if is_forbidden_domain(trouve['url']):
                continue
            resultats.append(
                SourceCandidate(
                    url=trouve['url'],
                    name=trouve.get('name', ''),
                    why=trouve.get('why', ''),
                    origin='recherche',
                )
            )
    return resultats


def proposer(demande, adapter=None, avec_recherche=True):
    """Rassemble toutes les adresses proposees, sans doublon.

    L ordre est celui de la demande : le modele d abord, puis ce que
    la recherche a trouve.
    """
    candidates = propose_par_modele(demande, adapter=adapter)

    if avec_recherche:
        for candidat in propose_par_recherche(demande):
            if any(candidat.url == existant.url for existant in candidates):
                continue
            candidates.append(candidat)

    # Domaines vus plusieurs fois : on ne garde qu une adresse.
    uniques = []
    vus = set()
    for candidat in candidates:
        cle = candidat.url.rstrip('/')
        if cle in vus:
            continue
        vus.add(cle)
        uniques.append(candidat)
    return uniques
