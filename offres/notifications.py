"""Notifications e-mail a l equipe Faso Job.

Les notifications sont **desactivees par defaut**. Elles ne partents que si :

- le parametre « notifications e-mail actives » est coche ;
- au moins une adresse destinataire est renseigne.

Les destinataires sont geres depuis l administration : la liste
`NotificationRecipient` permet d ajouter une adresse, d en retirer une ou
de la desactiver temporairement. L adresse d alerte des parametres reste
receveuse meme si elle n est pas dans la liste.

Aucun e-mail n est envoye a un particulier : seules les adresses de
l equipe sont utilisees. Le coursier de developpement est configure sur la
console : en production, un vrai serveur d envoi doit etre configure dans
l environnement.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

APOSTROPHE = chr(39)


def _alert_recipients():
    """Renvoie la liste des adresses destinataires actives.

    La liste est geree par l administration : on ajoute une adresse, on en
    retire une, on la desactive temporairement. L adresse d alerte des
    parametres reste receveuse meme si elle n est pas dans la liste.
    """
    from .models import NotificationRecipient, PlatformSettings

    platform_settings = PlatformSettings.load()
    if not platform_settings.notifications_enabled:
        return []

    recipients = []
    seen = set()

    alert_email = (platform_settings.alert_email or '').strip()
    if alert_email:
        recipients.append(alert_email)
        seen.add(alert_email.lower())

    for recipient in NotificationRecipient.objects.filter(is_active=True).order_by('email'):
        email = (recipient.email or '').strip()
        if not email or email.lower() in seen:
            continue
        seen.add(email.lower())
        recipients.append(email)

    return recipients


def _sender():
    from .models import PlatformSettings

    platform_settings = PlatformSettings.load()
    return settings.DEFAULT_FROM_EMAIL or 'contact@fasojob.local'


def notify_new_submission(submission):
    """Previent l equipe qu une proposition d annonce a ete recue.

    Renvoie True si au moins un e-mail a ete envoye.
    """
    recipients = _alert_recipients()
    if not recipients:
        return False

    subject = 'Nouvelle proposition d' + APOSTROPHE + 'annonce : %s' % submission.title
    body = (
        'Une nouvelle proposition a ete recue sur Faso Job.\n\n'
        'Intitule : %s\n'
        'Entreprise : %s\n'
        'Recue le : %s\n\n'
        'Elle est en attente de verification et n' + APOSTROPHE + 'est pas publiee.\n'
    ) % (
        submission.title,
        submission.company_name,
        submission.created_at.strftime('%d/%m/%Y a %H:%M'),
    )
    return _send(recipients, subject, body)


def notify_new_report(report):
    """Previent l equipe qu un signalement a ete recu."""
    recipients = _alert_recipients()
    if not recipients:
        return False

    subject = 'Nouveau signalement : %s' % report.get_reason_display()
    body = (
        'Un nouveau signalement a ete recu sur Faso Job.\n\n'
        'Motif : %s\n'
        'Annonce ou organisation : %s\n'
        'Recu le : %s\n\n'
        'Un signalement ne retire jamais une offre de la publication : '
        'une verification humaine est necessaire.\n'
    ) % (
        report.get_reason_display(),
        report.suspect_organization or report.suspect_title or 'non precisee',
        report.created_at.strftime('%d/%m/%Y a %H:%M'),
    )
    return _send(recipients, subject, body)


def notify_quarantined_submission(submission):
    """Previent l equipe qu une proposition a ete mise en quarantaine."""
    recipients = _alert_recipients()
    if not recipients:
        return False

    subject = 'Proposition en quarantaine : %s' % submission.title
    body = (
        'Une proposition a ete mise en quarantaine.\n\n'
        'Intitule : %s\n'
        'Entreprise : %s\n'
        'Motif : %s\n\n'
        'Elle reste en attente : elle n' + APOSTROPHE + 'est pas publiee automatiquement.\n'
    ) % (
        submission.title,
        submission.company_name,
        submission.quarantine_reason,
    )
    return _send(recipients, subject, body)


def _send(recipients, subject, body):
    """Envoie la notification a toutes les adresses destinataires.

    Une adresse en echec ne fait pas echouer les autres : chaque envoi est
    isole et le resultat indique si au moins une adresse a ete atteinte.
    """
    if isinstance(recipients, str):
        recipients = [recipients]
    if not recipients:
        return False

    sent = 0
    for recipient in recipients:
        try:
            send_mail(
                subject,
                body,
                _sender(),
                [recipient],
                fail_silently=False,
            )
        except Exception:
            # Une notification ne doit jamais interrompre le traitement.
            logger.exception('Envoi de la notification impossible a %s', recipient)
            continue
        sent += 1
    return sent > 0
