"""Contrat de l'extraction : champs attendus, prompt, lecture et validation.

Ce module ne connait aucun fournisseur d'intelligence artificielle. Il
definit ce que la veille attend d'une annonce et comment verifier la
reponse recue :

- une reponse est un objet JSON dont les cles sont connues ;
- une valeur absente reste vide ;
- une valeur mal formee est ecartee ;
- le texte brut de la reponse est conserve pour audit.

La regle est simple : **l'IA propose, le code valide**. Aucune valeur
n'est completee ni inventee de son propre chef. Si l'IA se trompe, le
champ reste vide et l'equipe le voit.
"""

import json
import re
import unicodedata
from datetime import datetime

# Les champs extractibles, dans l'ordre du pipeline. Chaque entree est
# (cle JSON, explication donnee au modele).
EXTRACT_FIELDS = (
    ('title', 'intitule exact du poste, ou null'),
    ('company_name', 'nom de l entreprise ou de l organisation, ou null'),
    ('description', 'description generale de l offre, ou null'),
    ('missions', 'missions et taches demandees, ou null'),
    ('required_profile', 'profil recherche, ou null'),
    ('required_education', 'niveau d etudes demande, ou null'),
    ('experience_required', 'experience demandee, ou null'),
    ('location', 'ville ou lieu de l offre, ou null'),
    ('employment_type', 'type de contrat ou d opportunite (CDI, CDD, stage, mission...), ou null'),
    ('published_at', 'date de publication de l annonce au format AAAA-MM-JJ, ou null'),
    ('deadline', 'date limite de candidature au format AAAA-MM-JJ, ou null'),
    ('application_email', 'adresse e-mail de candidature, ou null'),
    ('application_phone', 'numero de telephone de candidature, ou null'),
    ('whatsapp_number', 'numero WhatsApp de candidature, ou null'),
    ('application_method', 'mode de candidature, ou null'),
    ('application_url', 'lien de candidature, ou null'),
    ('application_instructions', 'autres modalites de candidature, ou null'),
)

# Longueur maximale de chaque champ. Les limites reprennent celles des
# champs du modele `Offer` : une valeur trop longue est raccourcie,
# jamais inventee.
TEXT_LIMITS = {
    'title': 250,
    'company_name': 200,
    'description': 20000,
    'missions': 20000,
    'required_profile': 20000,
    'required_education': 120,
    'experience_required': 120,
    'location': 200,
    'employment_type': 100,
    'application_email': 254,
    'application_phone': 30,
    'whatsapp_number': 30,
    'application_method': 20,
    'application_url': 200,
    'application_instructions': 20000,
}

# Les modes de candidature acceptes : ce sont ceux que l'offre sait
# deja Interpretter. Le modele peut rendre le libelle ou le code, les
# deux sont reconnus.
APPLICATION_METHOD_ALIASES = {
    'online': 'online',
    'en ligne': 'online',
    'enligne': 'online',
    'via le site': 'online',
    'email': 'email',
    'e-mail': 'email',
    'mail': 'email',
    'courriel': 'email',
    'par e-mail': 'email',
    'par email': 'email',
    'phone': 'phone',
    'telephone': 'phone',
    'par telephone': 'phone',
    'appel': 'phone',
    'whatsapp': 'whatsapp',
    'physical': 'physical',
    'depot physique': 'physical',
    'depot': 'physical',
    'sur place': 'physical',
    'other': 'other',
    'autre': 'other',
    'autre modalite': 'other',
    'non precise': '',
    'non precisee': '',
}

_EMAIL_PATTERN = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[A-Za-z]{2,}$")
_MULTIPLE_SPACES = re.compile(r"[ \t]+")
_MULTIPLE_BLANK_LINES = re.compile(r"\n{3,}")
_NOT_DIGIT = re.compile(r"\D+")

_MOIS_FR = {
    'janvier': 1,
    'fevrier': 2,
    'mars': 3,
    'avril': 4,
    'mai': 5,
    'juin': 6,
    'juillet': 7,
    'aout': 8,
    'septembre': 9,
    'octobre': 10,
    'novembre': 11,
    'decembre': 12,
}

_DATE_FORMATS = ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y', '%d %m %Y', '%Y/%m/%d')
_DATE_TEXT_PATTERN = re.compile(r"(\d{1,2})\s+([a-z]+)\.?\s+(\d{4})")


def normalize(value):
    """Minuscules, sans accent ni ponctuation, espaces normalises.

    La meme normalisation que celle du controle de moderation : deux
    textes compares le sont de la meme facon.
    """
    decomposed = unicodedata.normalize('NFKD', value or '')
    without_accents = ''.join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r'[^a-z0-9]+', ' ', without_accents.lower()).strip()


def clean_text(value, limit=0):
    """Nettoie un texte : espaces, lignes vides, longueur maximale.

    Une valeur qui n est pas un texte est ecartee. Une valeur trop
    longue est raccourpie : elle est conservee au lieu d etre perdue.
    """
    if not isinstance(value, str):
        return ''
    text = value.replace('\r\n', '\n').replace('\r', '\n')
    text = _MULTIPLE_SPACES.sub(' ', text)
    text = _MULTIPLE_BLANK_LINES.sub('\n\n', text).strip()
    if limit and len(text) > limit:
        text = text[:limit].rstrip()
    return text


def clean_date(value):
    """Lit une date et la rend au format AAAA-MM-JJ.

    Les ecritures courantes en francais sont acceptees. Une date
    incomplete ou incomprehensible est ecartee : une date inventee
    ferait expirer une offre a la mauvaise date.
    """
    if not isinstance(value, str):
        return ''
    text = value.strip()
    if not text:
        return ''

    # Une date complete avec l'heure : on garde la partie date.
    if len(text) > 10 and text[4] == '-' and text[7] == '-':
        text = text[:10]

    for date_format in _DATE_FORMATS:
        try:
            return datetime.strptime(text, date_format).strftime('%Y-%m-%d')
        except ValueError:
            continue

    # Â« 12 mai 2026 Â»
    match = _DATE_TEXT_PATTERN.search(normalize(text))
    if match:
        day, month_name, year = match.groups()
        month = _MOIS_FR.get(month_name)
        if month:
            return '%04d-%02d-%02d' % (int(year), month, int(day))
    return ''


def clean_email(value):
    """Valide une adresse e-mail. Une adresse fausse reste vide."""
    if not isinstance(value, str):
        return ''
    text = value.strip()
    if not text:
        return ''
    if not _EMAIL_PATTERN.match(text):
        return ''
    return text[:254]


def clean_url(value):
    """Valide un lien. Seuls http et https sont acceptes."""
    if not isinstance(value, str):
        return ''
    text = value.strip()
    if not text:
        return ''
    if not text.lower().startswith(('http://', 'https://')):
        return ''
    if len(text) > 200:
        return ''
    return text


def clean_phone(value):
    """Valide un numero de telephone.

    Le numero est conserve tel quel (prefixe international, espaces ou
    tirets). Seuls les chiffres comptent pour verifier qu il est
    plausible.
    """
    if not isinstance(value, str):
        return ''
    text = value.strip()
    if not text:
        return ''
    allowed = set('0123456789 +.-()/')
    if any(character not in allowed for character in text):
        return ''
    if len(_NOT_DIGIT.sub('', text)) < 8:
        return ''
    return text[:30]


def clean_application_method(value):
    """Ramene le mode de candidature a l'une des valeurs de l'offre."""
    if not isinstance(value, str):
        return ''
    text = normalize(value)
    if not text:
        return ''
    if text in APPLICATION_METHOD_ALIASES:
        return APPLICATION_METHOD_ALIASES[text]
    return ''


def clean_extraction(payload):
    """Valide une reponse d'extraction champ par champ.

    Renvoie un dictionnaire ou chaque cle du contrat a une valeur
    propre, prete a etre enregistree dans une offre. Une valeur
    absente, d'un autre type ou mal formee devient une chaine vide :
    **rien n'est invente**.
    """
    if not isinstance(payload, dict):
        payload = {}

    cleaned = {}
    for key, _label in EXTRACT_FIELDS:
        raw_value = payload.get(key)
        if key == 'published_at' or key == 'deadline':
            cleaned[key] = clean_date(raw_value)
        elif key == 'application_email':
            cleaned[key] = clean_email(raw_value)
        elif key == 'application_url':
            cleaned[key] = clean_url(raw_value)
        elif key in ('application_phone', 'whatsapp_number'):
            cleaned[key] = clean_phone(raw_value)
        elif key == 'application_method':
            cleaned[key] = clean_application_method(raw_value)
        else:
            cleaned[key] = clean_text(raw_value, TEXT_LIMITS.get(key, 0))
    return cleaned


def clean_classification(answer, categories):
    """Garde la categorie seulement si elle existe deja.

    La veille ne cree jamais une categorie. Si le modele propose un
    nom inconnu, la categorie reste vide : l'equipe decide.
    """
    if not isinstance(answer, str):
        return ''
    text = answer.strip()
    if not text:
        return ''

    wanted = normalize(text)
    for category_name in categories or ():
        if normalize(category_name) == wanted:
            return category_name
    return ''


def parse_json_answer(raw):
    """Lit la reponse JSON du modele.

    Les modeles libres n echappent pas toujours au JSON nu : un bloc
    de code ou un court commentaire autour est tolere. En cas d'echec,
    une erreur explicite est levee.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError('la reponse est vide')

    text = raw.strip()
    if text.startswith('```'):
        text = re.sub(r'^```[A-Za-z0-9_-]*\s*', '', text)
        text = re.sub(r'```\s*$', '', text).strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find('{')
        end = text.rfind('}')
        if start == -1 or end == -1 or end <= start:
            raise ValueError('la reponse ne contient aucun objet JSON')
        try:
            payload = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            raise ValueError("l'objet JSON de la reponse est illisible")

    if not isinstance(payload, dict):
        raise ValueError('la reponse n est pas un objet JSON')
    return payload


def build_extraction_prompt(content):
    """Construit la demande d'extraction."""
    from ..models import Offer

    lines = []
    for key, label in EXTRACT_FIELDS:
        lines.append('  "%s": %s' % (key, label))

    application_lines = []
    for value, label in Offer.APPLICATION_METHOD_CHOICES:
        if value:
            application_lines.append('  - %s : %s' % (value, label))
    if application_lines:
        application_lines.append('  - "" : mode non precise')

    return (
        'Voici une annonce d emploi. Analyse-la et rends les informations '
        'qu elle contient.\n\n'
        '<annonce>\n%s\n</annonce>\n\n'
        'Rends un objet JSON qui contient exactement les cles suivantes, dans '
        'cet ordre, et rien d autre :\n%s\n\n'
        'Regles :\n'
        '- Une information qui n est pas ecrite dans l annonce vaut null. '
        'Ne complete jamais, ne suppose jamais, n extrapole jamais.\n'
        '- Si une information est ecrite de facon vague, garde le texte '
        'tel quel, ne le reformule pas.\n'
        '- Une date s ecrit AAAA-MM-JJ. Si le jour est ambigu, mets null.\n'
        '- Le mode de candidature est l un de ceux-ci :\n%s\n'
        '- Reponds uniquement avec l objet JSON, sans texte autour.'
        % (
            content.strip(),
            '\n'.join(lines),
            '\n'.join(application_lines),
        )
    )


def build_classification_prompt(extracted, categories):
    """Construit la demande de classement.

    Le classement se fait sur les informations deja extraites : la
    demande est courte et porte sur le fond de l offre.
    """
    summary = '\n'.join(
        '%s : %s' % (label, extracted.get(key) or '(non precise)')
        for key, label in (
            ('title', 'Intitule'),
            ('company_name', 'Entreprise'),
            ('description', 'Description'),
            ('missions', 'Missions'),
        )
    )
    category_lines = '\n'.join('  - %s' % name for name in categories or ())

    return (
        'Voici une offre d emploi, decrite par les informations extraites :\n\n'
        '%s\n\n'
        'Choisis la categorie qui lui correspond le mieux parmi celles-ci :\n%s\n\n'
        'Regles :\n'
        '- Reponds uniquement avec le nom exact d une categorie de la liste.\n'
        '- Si aucune categorie ne convient, reponds null.\n'
        '- N invente jamais une categorie qui n est pas dans la liste.'
        % (summary, category_lines)
    )
