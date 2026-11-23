"""Client d'intelligence artificielle de la veille.

Le module parle a un service compatible avec l'interface OpenAI
(`/chat/completions`). Cette interface est la plus largement
repandue : Gemini, OpenRouter et d'autres passerelles l exposent
toutes. Seules trois valeurs changent d'un service a l'autre :

- l'adresse du service ;
- la cle d'acces ;
- le nom du modele.

Ces trois valeurs viennent du fichier `.env`. **Changer de modele ne
demande donc aucune modification du code** : on change une ligne de
configuration, et le meme code lit la suite.

Le module ne leve jamais d'exception vers l'appelant : une panne du
reseau ou un refus du service est rendu dans le resultat. Une erreur
de collecte ne doit pas arreter la collecte.

Sur le plan des regles, le module applique une seule politique : rien
n'est publie, rien n'est invente. L'IA propose des valeurs, le module
schema.py les verifie, et une valeur douteuse reste vide.
"""

import json
import logging
import socket
import urllib.error
import urllib.request

from django.conf import settings

from .schema import (
    build_classification_prompt,
    build_extraction_prompt,
    clean_classification,
    clean_extraction,
    parse_json_answer,
)

logger = logging.getLogger(__name__)

# Version du prompt : elle est inscrite avec chaque extraction pour que
# l'equipage sache a quelles consignes la reponse a ete obtenue.
PROMPT_VERSION = 'v1'

SYSTEM_PROMPT = (
    'Tu analyses des annonces d emploi publiees au Burkina Faso.\n'
    'Regles absolues :\n'
    '- Tu n inventes rien. Si une information n est pas ecrite '
    'explicitement dans le texte, tu mets null.\n'
    '- Tu ne completes pas une information manquante, tu ne supposes '
    'pas, tu n extrapoles pas, tu ne deduis pas.\n'
    '- Tu ne traduis pas et tu ne reformules pas les intitules de '
    'poste : tu recopies ce qui est ecrit.\n'
    '- Tu reponds uniquement avec un objet JSON valide, sans texte '
    'autour et sans commentaire.\n'
    '- Tu ne cites que des informations presentes dans le texte '
    'fourni.'
)


class AiRequestError(Exception):
    """Erreur survenue pendant un appel au service d intelligence artificielle."""


class ExtractionResult:
    """Resultat d'une demande faite au service d intelligence artificielle.

    `data` contient les champs valides, `raw` la reponse brute du
    service (conservee pour audit) et `error` le motif de l'echec le
    cas echeant.
    """

    def __init__(self, status, data=None, raw='', error='', provider='', model=''):
        self.status = status
        self.data = data or {}
        self.raw = raw
        self.error = error
        self.provider = provider
        self.model = model

    @property
    def is_ok(self):
        from ..models import CollectedAnnouncement

        return self.status == CollectedAnnouncement.EXTRACTION_DONE

    def __repr__(self):
        return f'<ExtractionResult {self.status}>'


class BaseAdapter:
    """Contrat commun a tous les adaptateurs d intelligence artificielle."""

    name = ''

    def is_configured(self):
        """Indique si le service peut reellement etre interroge."""
        raise NotImplementedError

    def complete(self, prompt, system=''):
        """Envoie la demande et renvoie le texte de la reponse.

        Ne leve pas d'exception : une erreur est rendue par le
        resultat. Renvoie None si le service n est pas configure.
        """
        raise NotImplementedError


class NotConfiguredAdapter(BaseAdapter):
    """Adaptateur par defaut : aucun service n est configure.

    C'est l'adaptateur utilise tant qu'aucune cle n est renseignee.
    Il rend visible dans l'administration ce qui aurait ete extrait,
    sans pretendre qu'une extraction a eu lieu.
    """

    name = 'non-configure'

    def is_configured(self):
        return False

    def complete(self, prompt, system=''):
        return None


class OpenAICompatibleAdapter(BaseAdapter):
    """Client d'un service compatible avec l'interface OpenAI.

    L'adresse, la cle et le modele viennent du fichier `.env`. Aucun
    de ces Elements n'est ecrit dans le code, et aucun n'est affiche
    dans un gabarit.
    """

    name = 'openai-compatible'

    def __init__(self, base_url=None, api_key=None, model=None, timeout=None, json_mode=None):
        self.base_url = self._setting(base_url, 'AI_BASE_URL').rstrip('/')
        self.api_key = self._setting(api_key, 'AI_API_KEY')
        self.model = self._setting(model, 'AI_MODEL')
        self.timeout = timeout or getattr(settings, 'AI_REQUEST_TIMEOUT', 60)
        self.json_mode = (
            bool(json_mode)
            if json_mode is not None
            else bool(getattr(settings, 'AI_JSON_MODE', False))
        )

    @staticmethod
    def _setting(value, name):
        """Renvoie la valeur fournie, sinon celle de l'environnement."""
        if value is not None:
            return str(value).strip()
        return str(getattr(settings, name, '') or '').strip()

    @property
    def endpoint(self):
        """Adresse complete de l operation de discussion."""
        return f'{self.base_url}/chat/completions'

    def is_configured(self):
        """Les trois reglages sont necessaires : sans eux, rien ne part."""
        return bool(self.base_url and self.api_key and self.model)

    def build_payload(self, prompt, system=''):
        """Construit le corps de la demande."""
        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': prompt})

        payload = {
            'model': self.model,
            'messages': messages,
            'temperature': 0,
        }
        if self.json_mode:
            # Manche services acceptent ce reglage et rendent un JSON
            # strict. Ce n est pas le cas de tous : il reste optionnel.
            payload['response_format'] = {'type': 'json_object'}
        return payload

    def complete(self, prompt, system=''):
        """Envoie la demande et renvoie le texte reponse.

        Ne leve pas d'exception vers l'appelant : le motif de l'echec
        est decrit dans `AiRequestError`, que le module transforme en
        resultat.
        """
        if not self.is_configured():
            return None

        body = json.dumps(self.build_payload(prompt, system)).encode('utf-8')
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}',
                'User-Agent': 'FasoJob-Veille/1.0',
            },
            method='POST',
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode('utf-8', errors='replace')
        except urllib.error.HTTPError as error:
            detail = ''
            try:
                detail = error.read().decode('utf-8', errors='replace')[:500]
            except Exception:
                detail = ''
            logger.warning('Appel IA refuse (HTTP %s) : %s', error.code, detail)
            raise AiRequestError(
                'Le service a refuse la demande (HTTP %s). %s'
                % (error.code, detail)
            )
        except urllib.error.URLError as error:
            logger.warning('Appel IA impossible : %s', error)
            raise AiRequestError('Le service est injoignable : %s' % (error.reason,))
        except socket.timeout:
            logger.warning('Appel IA sans reponse dans le delai imparti.')
            raise AiRequestError('Le service ne repond pas dans le delai imparti.')

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise AiRequestError('La reponse du service est illisible.')

        return _answer_text(data)


def _answer_text(data):
    """Retire le texte utile d'une reponse de service."""
    if not isinstance(data, dict):
        return ''

    choices = data.get('choices') or []
    if choices:
        message = choices[0].get('message') or {}
        content = message.get('content')
        if isinstance(content, list):
            # Certains services renvoient le contenu en morceaux.
            parts = []
            for part in content:
                if isinstance(part, dict):
                    parts.append(part.get('text') or '')
                elif isinstance(part, str):
                    parts.append(part)
            return ''.join(parts)
        if isinstance(content, str):
            return content

    # Reponse sans choix : certaines passerelles rendent directement
    # le texte du modele.
    content = data.get('content') or data.get('text')
    return content if isinstance(content, str) else ''


def get_adapter():
    """Renvoie l'adaptateur d intelligence artificielle a utiliser."""
    return OpenAICompatibleAdapter()


def extract_announcement(content, adapter=None):
    """Demande au service d extraire les informations d'une annonce.

    Renvoie un `ExtractionResult`. Le statut vaut `done` quand
    l'extraction a reussi, `failed` sinon. Les champs absents ou
    invalides restent vides : **le service ne complete rien**.
    """
    from ..models import CollectedAnnouncement

    adapter = adapter or get_adapter()
    if not adapter.is_configured():
        return ExtractionResult(
            status=CollectedAnnouncement.EXTRACTION_FAILED,
            error=(
                'Aucun service d intelligence artificielle configure : '
                'renseignez AI_BASE_URL, AI_API_KEY et AI_MODEL dans le '
                'fichier .env.'
            ),
            provider=adapter.name,
        )

    prompt = build_extraction_prompt(content)

    try:
        raw = adapter.complete(prompt, SYSTEM_PROMPT)
    except AiRequestError as error:
        return ExtractionResult(
            status=CollectedAnnouncement.EXTRACTION_FAILED,
            error=str(error),
            provider=adapter.name,
            model=getattr(adapter, 'model', ''),
        )

    if raw is None:
        return ExtractionResult(
            status=CollectedAnnouncement.EXTRACTION_FAILED,
            error='Le service n a rien renvoye.',
            provider=adapter.name,
            model=getattr(adapter, 'model', ''),
        )

    try:
        payload = parse_json_answer(raw)
    except ValueError as error:
        return ExtractionResult(
            status=CollectedAnnouncement.EXTRACTION_FAILED,
            error='Reponse illisible : %s' % error,
            raw=raw,
            provider=adapter.name,
            model=getattr(adapter, 'model', ''),
        )

    cleaned = clean_extraction(payload)
    if not cleaned['title']:
        return ExtractionResult(
            status=CollectedAnnouncement.EXTRACTION_FAILED,
            data=cleaned,
            raw=raw,
            error="L'intitule du poste n'a pas pu etre extrait.",
            provider=adapter.name,
            model=getattr(adapter, 'model', ''),
        )

    supporting_fields = (
        'company_name',
        'description',
        'missions',
        'required_profile',
        'required_education',
        'experience_required',
        'location',
        'employment_type',
        'deadline',
        'application_email',
        'application_phone',
        'whatsapp_number',
        'application_method',
        'application_url',
        'application_instructions',
    )
    if not any(cleaned[field] for field in supporting_fields):
        return ExtractionResult(
            status=CollectedAnnouncement.EXTRACTION_FAILED,
            data=cleaned,
            raw=raw,
            error=(
                "L'extraction ne contient que l'intitule du poste ; "
                "aucune information utile supplementaire n'a ete extraite."
            ),
            provider=adapter.name,
            model=getattr(adapter, 'model', ''),
        )

    return ExtractionResult(
        status=CollectedAnnouncement.EXTRACTION_DONE,
        data=cleaned,
        raw=raw,
        provider=adapter.name,
        model=getattr(adapter, 'model', ''),
    )


def classify_announcement(extracted, categories, adapter=None):
    """Demande au service de classer une annonce dans les categories existantes.

    `categories` est la liste des noms de categories deja enregistres.
    Le classement se fait sur les informations deja extraites : la
    demande est courte et porte sur le fond de l offre.

    Renvoie un `ExtractionResult` dont `data` contient la cle
    `category`. La categorie est vide si le modele propose un nom
    inconnu : la veille ne cree jamais de categorie.
    """
    from ..models import CollectedAnnouncement

    names = [str(name) for name in (categories or ())]
    adapter = adapter or get_adapter()

    if not names:
        return ExtractionResult(
            status=CollectedAnnouncement.EXTRACTION_DONE,
            data={'category': ''},
            provider=adapter.name,
        )

    if not adapter.is_configured():
        return ExtractionResult(
            status=CollectedAnnouncement.EXTRACTION_FAILED,
            error=(
                'Aucun service d intelligence artificielle configure : '
                'le classement est impossible.'
            ),
            provider=adapter.name,
        )

    prompt = build_classification_prompt(extracted, names)

    try:
        raw = adapter.complete(prompt, SYSTEM_PROMPT)
    except AiRequestError as error:
        return ExtractionResult(
            status=CollectedAnnouncement.EXTRACTION_FAILED,
            error=str(error),
            provider=adapter.name,
            model=getattr(adapter, 'model', ''),
        )

    if raw is None:
        return ExtractionResult(
            status=CollectedAnnouncement.EXTRACTION_FAILED,
            error='Le service n a rien renvoye.',
            provider=adapter.name,
            model=getattr(adapter, 'model', ''),
        )

    answer = raw.strip()
    # Le service peut rendre la reponse dans un objet JSON.
    if answer.startswith('{'):
        try:
            payload = parse_json_answer(answer)
        except ValueError:
            payload = {}
        answer = payload.get('category') or ''

    category = clean_classification(answer, names)

    return ExtractionResult(
        status=CollectedAnnouncement.EXTRACTION_DONE,
        data={'category': category},
        raw=raw,
        provider=adapter.name,
        model=getattr(adapter, 'model', ''),
    )
