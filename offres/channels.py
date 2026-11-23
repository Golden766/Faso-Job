"""Adaptateurs de messagerie sortante (WhatsApp, SMS, e-mail).

Ce module prepare la **structure** d'envoi sans simuler le moindre envoi.

Aucun fournisseur n'est choisi a ce stade : le choix reste ouvert (voir
PLAN-REFONTE.md, section 7). En attendant, chaque message passe par un
adaptateur « non configure » qui l'**enregistre** dans le journal
`OutboundMessage` avec le statut correspondant, sans contacter qui que ce
soit.

Le contrat attendu d'un adaptateur est volontairement minimal :

    adapter = get_adapter('whatsapp')
    result = adapter.send(recipient='+22670000000', body='...')

`send` renvoie un `SendResult` qui indique toujours l'etat reel de
l'operation. Un adaptateur qui echoue ne leve pas d'exception : il
renvoie un resultat en erreur, que le journal conserve.
"""

import logging

from django.conf import settings

from .models import OutboundMessage

logger = logging.getLogger(__name__)


class SendResult:
    """Resultat d'une tentative d'envoi."""

    def __init__(self, status, provider='', error='', sent_at=None):
        self.status = status
        self.provider = provider
        self.error = error
        self.sent_at = sent_at

    @property
    def is_sent(self):
        return self.status == OutboundMessage.STATUS_SENT

    def __repr__(self):
        return f'<SendResult {self.status} via {self.provider}>'


class BaseAdapter:
    """Contrat commun a tous les adaptateurs."""

    channel = ''
    name = ''

    def is_configured(self):
        """Indique si l'adaptateur peut reellement envoyer."""
        raise NotImplementedError

    def send(self, recipient, body, offer=None, submission=None):
        """Prepare un envoi. Ne leve pas d'exception."""
        raise NotImplementedError


class NotConfiguredAdapter(BaseAdapter):
    """Adaptateur par defaut : enregistre le message, n'envoie rien.

    C'est l'adaptateur utilise tant qu'aucun fournisseur n'est choisi. Il
    rend visible dans l'administration ce qui aurait ete envoye, sans
    pretendre qu'un envoi a eu lieu.
    """

    channel = OutboundMessage.CHANNEL_WHATSAPP
    name = 'non-configure'

    def is_configured(self):
        return False

    def send(self, recipient, body, offer=None, submission=None):
        message = OutboundMessage.objects.create(
            channel=self.channel,
            recipient=recipient,
            body=body,
            status=OutboundMessage.STATUS_NOT_CONFIGURED,
            offer=offer,
            submission=submission,
            provider=self.name,
        )
        logger.info(
            'Message %s prepare pour %s : aucun fournisseur configure.',
            self.channel,
            recipient,
        )
        return SendResult(
            status=OutboundMessage.STATUS_NOT_CONFIGURED,
            provider=self.name,
            error='Aucun fournisseur configure : le message est enregistre mais non envoye.',
        )


class ConsoleAdapter(BaseAdapter):
    """Adaptateur de developpement : ecrit le message dans la console.

    Il sert aux tests et a la demonstration locale. Le message reste
    enregistre avec le statut « en attente » : la console n'est pas un
    canal d'envoi reel.
    """

    def is_configured(self):
        return False

    def send(self, recipient, body, offer=None, submission=None):
        OutboundMessage.objects.create(
            channel=self.channel,
            recipient=recipient,
            body=body,
            status=OutboundMessage.STATUS_PENDING,
            offer=offer,
            submission=submission,
            provider=self.name,
        )
        logger.warning(
            'SIMULATION LOCALE : message %s vers %s. Aucun envoi reel.',
            self.channel,
            recipient,
        )
        return SendResult(
            status=OutboundMessage.STATUS_PENDING,
            provider=self.name,
            error='Adaptateur de developpement : aucun envoi reel.',
        )


class WhatsAppAdapter(NotConfiguredAdapter):
    channel = OutboundMessage.CHANNEL_WHATSAPP
    name = 'whatsapp-non-configure'


class SmsAdapter(NotConfiguredAdapter):
    channel = OutboundMessage.CHANNEL_SMS
    name = 'sms-non-configure'


class EmailAdapter(BaseAdapter):
    """Adaptateur e-mail : utilise le coursier Django.

    Unlike the other channels, the e-mail courseur is a real one. It
    remains off by default in development (console backend) and requires
    a real server configuration in production.
    """

    channel = OutboundMessage.CHANNEL_EMAIL
    name = 'email-django'

    def is_configured(self):
        return bool(getattr(settings, 'DEFAULT_FROM_EMAIL', None))

    def send(self, recipient, body, offer=None, submission=None):
        from django.core.mail import send_mail

        subject = 'Faso Job'
        if offer is not None:
            subject = f'Faso Job — {offer.title}'
        elif submission is not None:
            subject = f'Faso Job — {submission.title}'

        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient])
        except Exception as error:
            message = OutboundMessage.objects.create(
                channel=self.channel,
                recipient=recipient,
                body=body,
                status=OutboundMessage.STATUS_FAILED,
                offer=offer,
                submission=submission,
                provider=self.name,
                error=str(error),
            )
            logger.exception('Envoi e-mail impossible vers %s', recipient)
            return SendResult(
                status=OutboundMessage.STATUS_FAILED,
                provider=self.name,
                error=str(error),
            )

        message = OutboundMessage.objects.create(
            channel=self.channel,
            recipient=recipient,
            body=body,
            status=OutboundMessage.STATUS_SENT,
            offer=offer,
            submission=submission,
            provider=self.name,
        )
        from django.utils import timezone

        message.sent_at = timezone.now()
        message.save(update_fields=['sent_at'])
        return SendResult(
            status=OutboundMessage.STATUS_SENT,
            provider=self.name,
            sent_at=message.sent_at,
        )


ADAPTERS = {
    OutboundMessage.CHANNEL_WHATSAPP: WhatsAppAdapter,
    OutboundMessage.CHANNEL_SMS: SmsAdapter,
    OutboundMessage.CHANNEL_EMAIL: EmailAdapter,
}


def get_adapter(channel):
    """Renvoie l'adaptateur d'un canal.

    Un canal inconnu renvoie l'adaptateur « non configure » : la
    preparation d'un message ne doit jamais lever d'exception.
    """
    adapter_class = ADAPTERS.get(channel, NotConfiguredAdapter)
    return adapter_class()


def send_message(channel, recipient, body, offer=None, submission=None):
    """Prepare un envoi sur un canal et l'enregistre au journal."""
    if not recipient or not body:
        return None
    adapter = get_adapter(channel)
    return adapter.send(
        recipient=recipient,
        body=body,
        offer=offer,
        submission=submission,
    )
