"""Controles de moderation automatiques de Faso Job.

Trois mecanismes complementaires, tous signales a l administration et
jamais appliques silencieusement au public :

1. le **croisement avec la liste noire** : un numero, un e-mail ou une
   organisation deja inscrits au registre prive signalent l offre ou la
   proposition concernee ;
2. les **mots-cles de quarantaine** : les termes saisis dans les
   parametres de la plateforme signalent l annonce ;
3. la **gravite** de la correspondance : un contact bloque definitivement
   ne peut jamais etre publie, un contact sous surveillance peut l etre
   apres un controle humain enregistre.

Deux reges ne sont jamais depassees :

- un signalement ne retire jamais une offre de la publication ;
- poser ou lever une quarantaine ne modifie jamais le statut editorial
  d une offre deja publiee. Seule l equipe decide de suspendre une offre,
  et elle le fait de maniere explicite.
"""

import re
import unicodedata

_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")
_NON_DIGIT = re.compile(r"\D+")

# Gravites, de la plus faible a la plus forte.
SEVERITY_NONE = "none"
SEVERITY_WATCH = "watch"
SEVERITY_BLOCKED = "blocked"

_SEVERITY_ORDER = {
    SEVERITY_NONE: 0,
    SEVERITY_WATCH: 1,
    SEVERITY_BLOCKED: 2,
}


def normalize_digits(value):
    """Reduit un numero a ses seuls chiffres pour comparer deux saisies."""
    return _NON_DIGIT.sub("", value or "")


def normalize_email(value):
    """Normalise une adresse e-mail pour la comparaison."""
    return (value or "").strip().lower()


def normalize_text(value):
    """Minuscules, sans accent ni ponctuation, espaces normalises."""
    decomposed = unicodedata.normalize("NFKD", value or "")
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return _NON_ALPHANUMERIC.sub(" ", without_accents.lower()).strip()


def parse_keywords(raw_value):
    """Decoupe une liste de mots-cles : un par ligne, lignes vides ignorees."""
    keywords = []
    for line in (raw_value or "").splitlines():
        cleaned = line.strip()
        if cleaned and not cleaned.startswith("#"):
            keywords.append(cleaned)
    return keywords


def worst_severity(first, second):
    """Renvoie la gravite la plus forte entre deux valeurs."""
    if _SEVERITY_ORDER.get(second, 0) > _SEVERITY_ORDER.get(first, 0):
        return second
    return first


def find_keyword_matches(texts, keywords):
    """Renvoie les mots-cles trouves dans les textes fournis.

    La recherche est insensible a la casse et aux accents. Un mot-cle vide
    ou compose uniquement de ponctuation est ignore.
    """
    haystack = " ".join(normalize_text(text) for text in texts if text)
    haystack = f" {haystack} "
    matches = []
    for keyword in keywords:
        needle = normalize_text(keyword)
        if not needle:
            continue
        if f" {needle} " in haystack:
            matches.append(keyword)
    return matches


def contact_severity(contact):
    """Gravite d un contact de la liste noire.

    Un contact bloque definitivement est un risque maximal : il ne peut
    jamais etre publie. Un contact sous surveillance demande un controle
    humain. Un contact dont les coordonnees ont ete neutralisees ne pose
    plus de probleme.
    """
    from .models import BlacklistedContact

    if contact.status == BlacklistedContact.STATUS_BLOCKED:
        return SEVERITY_BLOCKED
    if contact.status == BlacklistedContact.STATUS_WATCH:
        return SEVERITY_WATCH
    return SEVERITY_NONE


def _blacklist_matches(phone="", email="", organization="", contacts=None):
    """Compare une annonce aux contacts de la liste noire.

    Renvoie une liste de couples (motif, gravite).
    """
    if contacts is None:
        from .models import BlacklistedContact

        contacts = BlacklistedContact.objects.all()

    digits = normalize_digits(phone)
    mail = normalize_email(email)
    name = normalize_text(organization)

    matches = []
    for contact in contacts:
        severity = contact_severity(contact)
        if severity == SEVERITY_NONE:
            # Coordonnees neutralisees : ce contact ne bloque plus rien.
            continue
        status_label = contact.get_status_display()
        if (
            digits
            and contact.normalized_number
            and digits == contact.normalized_number
        ):
            matches.append(
                (
                    f"Numéro présent sur la liste noire ({status_label}) : "
                    f"{contact.organization}.",
                    severity,
                )
            )
        contact_mail = normalize_email(contact.email)
        if mail and contact_mail and mail == contact_mail:
            matches.append(
                (
                    f"E-mail présent sur la liste noire ({status_label}) : "
                    f"{contact.organization}.",
                    severity,
                )
            )
        contact_name = normalize_text(contact.organization)
        if name and contact_name and name == contact_name:
            matches.append(
                (
                    f"Organisation présente sur la liste noire ({status_label}) : "
                    f"{contact.organization}.",
                    severity,
                )
            )
    return matches


def find_blacklist_matches(
    *,
    phone="",
    email="",
    organization="",
    contacts=None,
):
    """Compare une annonce aux contacts inscrits sur la liste noire.

    Renvoie la liste des motifs de correspondance, sous forme de textes
    lisibles par l administration. Une comparaison exacte est utilisee sur
    les numeros, les e-mails et les noms d organisation : une ressemblance
    partielle creerait trop de faux positifs.
    """
    return [
        reason
        for reason, _severity in _blacklist_matches(
            phone=phone,
            email=email,
            organization=organization,
            contacts=contacts,
        )
    ]


def evaluate_offer(offer):
    """Evalue une offre et renvoie (motifs, gravite).

    La fonction ne modifie rien : l appelant decide d enregistrer.
    """
    from .models import PlatformSettings

    settings = PlatformSettings.load()

    reasons = []
    severity = SEVERITY_NONE

    for reason, contact_level in _blacklist_matches(
        phone=offer.application_phone or offer.whatsapp_number,
        email=offer.application_email,
        organization=offer.company_name,
    ):
        reasons.append(reason)
        severity = worst_severity(severity, contact_level)

    for reason, contact_level in _blacklist_matches(
        phone=offer.whatsapp_number,
        organization=offer.company_name,
    ):
        if reason in reasons:
            continue
        reasons.append(reason)
        severity = worst_severity(severity, contact_level)

    keywords = parse_keywords(settings.quarantine_keywords)
    for keyword in find_keyword_matches(
        [
            offer.title,
            offer.description,
            offer.company_name,
            offer.application_instructions,
            offer.required_documents,
        ],
        keywords,
    ):
        reasons.append(f"Mot-clé de quarantaine détecté : « {keyword} ».")
        # Un mot-clé peut être un faux positif : il reste revisable.
        severity = worst_severity(severity, SEVERITY_WATCH)

    return reasons, severity


def evaluate_submission(submission):
    """Evalue une proposition recue et renvoie (motifs, gravite)."""
    from .models import PlatformSettings

    settings = PlatformSettings.load()

    reasons = []
    severity = SEVERITY_NONE

    for reason, contact_level in _blacklist_matches(
        phone=submission.contact_phone,
        email=submission.contact_email,
        organization=submission.company_name,
    ):
        reasons.append(reason)
        severity = worst_severity(severity, contact_level)

    for reason, contact_level in _blacklist_matches(
        phone=submission.whatsapp_number or submission.application_phone,
        email=submission.application_email,
        organization=submission.company_name,
    ):
        if reason in reasons:
            continue
        reasons.append(reason)
        severity = worst_severity(severity, contact_level)

    keywords = parse_keywords(settings.quarantine_keywords)
    for keyword in find_keyword_matches(
        [
            submission.title,
            submission.details,
            submission.company_name,
            submission.application_instructions,
            submission.required_documents,
        ],
        keywords,
    ):
        reasons.append(f"Mot-clé de quarantaine détecté : « {keyword} ».")
        severity = worst_severity(severity, SEVERITY_WATCH)

    return reasons, severity


def quarantine_text(reasons):
    """Concatene les motifs de quarantaine en un texte stockable."""
    return " ".join(reasons)


def screen_offer(offer):
    """Recalcule les motifs de quarantaine d'une offre.

    Renvoie la liste des motifs. La fonction ne modifie rien : l appelant
    decide de les enregistrer.
    """
    reasons, _severity = evaluate_offer(offer)
    return reasons


def screen_submission(submission):
    """Recalcule les motifs de quarantaine d'une proposition recue."""
    reasons, _severity = evaluate_submission(submission)
    return reasons


def apply_offer_screening(offer, clear_when_no_match=False):
    """Applique le resultat du controle a une offre et l enregistre.

    Le motif n est jamais efface automatiquement : seul un controle
    complet demande par l administration peut lever une quarantaine. Le
    controle humain est invalide des que le motif change.
    """
    reasons, severity = evaluate_offer(offer)

    if not reasons:
        if clear_when_no_match and offer.quarantine_reason:
            offer.quarantine_reason = ""
            offer.quarantined_at = None
            offer.quarantine_severity = SEVERITY_NONE
            offer.quarantine_reviewed_at = None
            offer.quarantine_reviewed_by = None
            offer.save(
                update_fields=[
                    "quarantine_reason",
                    "quarantined_at",
                    "quarantine_severity",
                    "quarantine_reviewed_at",
                    "quarantine_reviewed_by",
                ],
                skip_quarantine_check=True,
            )
            return False
        return False

    text = quarantine_text(reasons)
    if offer.quarantine_reason != text:
        # Le motif a change : le controle humain precedent ne vaut plus.
        offer.quarantine_reviewed_at = None
        offer.quarantine_reviewed_by = None

    offer.quarantine_reason = text
    offer.quarantine_severity = severity
    offer.quarantined_at = _now()
    # La regle de publication est ecartee : signaler une offre deja
    # publiee ne doit pas echouer, et son statut ne change pas.
    offer.save(
        update_fields=[
            "quarantine_reason",
            "quarantine_severity",
            "quarantined_at",
            "quarantine_reviewed_at",
            "quarantine_reviewed_by",
        ],
        skip_quarantine_check=True,
    )
    return True


def apply_submission_screening(submission, clear_when_no_match=False):
    """Applique le resultat du controle a une proposition recue."""
    reasons, severity = evaluate_submission(submission)

    if not reasons:
        if clear_when_no_match and submission.quarantine_reason:
            submission.quarantine_reason = ""
            submission.quarantined_at = None
            submission.quarantine_severity = SEVERITY_NONE
            submission.save(
                update_fields=[
                    "quarantine_reason",
                    "quarantined_at",
                    "quarantine_severity",
                ]
            )
            return False
        return False

    submission.quarantine_reason = quarantine_text(reasons)
    submission.quarantine_severity = severity
    submission.quarantined_at = _now()
    submission.save(
        update_fields=[
            "quarantine_reason",
            "quarantine_severity",
            "quarantined_at",
        ]
    )
    return True


def screen_offers(offers, clear_when_no_match=False):
    """Applique le controle a un ensemble d'offres.

    Renvoie le nombre d'offres placees en quarantaine par ce passage.

    `clear_when_no_match` n'est vrai que pour un controle complet demande
    par l administration : c'est la seule voie qui autorise a lever une
    quarantaine devenue sans objet.
    """
    quarantined = 0
    for offer in offers:
        if apply_offer_screening(offer, clear_when_no_match=clear_when_no_match):
            quarantined += 1
    return quarantined


def screen_submissions(submissions, clear_when_no_match=False):
    """Applique le controle a des propositions recues."""
    quarantined = 0
    for submission in submissions:
        if apply_submission_screening(
            submission, clear_when_no_match=clear_when_no_match
        ):
            quarantined += 1
    return quarantined


def _matching_offers(phone="", email="", organization=""):
    """Renvoie les offres dont les coordonnees correspondent a un contact.

    L e-mail et l organisation sont compares directement en base : la
    comparaison est exacte, elle ne depend pas du format de saisie.

    Le numero est compare en Python, apres un premier tri en base sur les
    seules offres qui portent un numero. C est necessaire parce qu un
    numero peut etre saisi avec ou sans indicatif pays, avec des espaces
    ou avec des tirets : une recherche par sous chaine de chiffres ne
    trouverait rien dans une chaine formatee.
    """
    from .models import Offer

    queryset = Offer.objects.none()

    if email:
        queryset = queryset | Offer.objects.filter(
            application_email__iexact=email
        )

    if organization:
        queryset = queryset | Offer.objects.filter(
            company_name__iexact=organization
        )

    if phone:
        digits = normalize_digits(phone)
        # Une offre est candidate des qu elle porte l un des deux numeros.
        candidates = Offer.objects.exclude(application_phone="") | (
            Offer.objects.exclude(whatsapp_number="")
        )
        for offer in candidates:
            numbers = {
                normalize_digits(offer.application_phone),
                normalize_digits(offer.whatsapp_number),
            }
            if digits in numbers:
                queryset = queryset | Offer.objects.filter(pk=offer.pk)

    return queryset.distinct()


def rescreen_for_contact(contact):
    """Recontrole les offres et propositions liees a un contact de la liste.

    Appelee quand la liste noire change : une offre deja publiee dont le
    contact vient d etre inscrit doit etre signalee a l equipe. Son
    statut n est pas modifie : la suspension reste une decision humaine.
    """
    from .models import OfferSubmission

    flagged_offers = 0
    flagged_submissions = 0

    offers = _matching_offers(
        phone=contact.phone_number,
        email=contact.email,
        organization=contact.organization,
    )
    for offer in offers:
        if apply_offer_screening(offer):
            flagged_offers += 1

    submissions = OfferSubmission.objects.none()
    if contact.organization:
        submissions = submissions | OfferSubmission.objects.filter(
            company_name__iexact=contact.organization
        )
    if contact.email:
        submissions = submissions | OfferSubmission.objects.filter(
            contact_email__iexact=contact.email
        )
    if contact.phone_number:
        digits = normalize_digits(contact.phone_number)
        candidates = OfferSubmission.objects.exclude(contact_phone="") | (
            OfferSubmission.objects.exclude(whatsapp_number="")
        ) | (OfferSubmission.objects.exclude(application_phone=""))
        for candidate in candidates:
            numbers = {
                normalize_digits(candidate.contact_phone),
                normalize_digits(candidate.whatsapp_number),
                normalize_digits(candidate.application_phone),
            }
            if digits in numbers:
                submissions = submissions | OfferSubmission.objects.filter(
                    pk=candidate.pk
                )
    for submission in submissions.distinct():
        if apply_submission_screening(submission):
            flagged_submissions += 1

    return flagged_offers, flagged_submissions


def _now():
    from django.utils import timezone

    return timezone.now()
