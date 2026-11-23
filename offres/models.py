from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

MAX_EVIDENCE_SIZE = 5 * 1024 * 1024


def validate_evidence_size(value):
    if value.size > MAX_EVIDENCE_SIZE:
        raise ValidationError('La preuve jointe ne doit pas dépasser 5 Mo.')


class Source(models.Model):
    """Origine d'une offre.

    Une source peut être utilisée de deux façons :

    - simple reference : elle est rattachee a des offres publiees ou en
      attente ;
    - source surveillee : la veille vient y chercher des annonces, selon
      un mode de collecte et des conditions de reprise.

    Une source surveillee ne collecte jamais sans autorisation ecrite :
    la surveillance est un choix de l equipe, pas une consequence
    technique.
    """

    COLLECTION_METHOD_MANUAL_URL = 'manual_url'
    COLLECTION_METHOD_MANUAL_TEXT = 'manual_text'
    COLLECTION_METHOD_WEB = 'web'
    COLLECTION_METHOD_RSS = 'rss'
    COLLECTION_METHOD_NEWSLETTER = 'newsletter'
    COLLECTION_METHOD_FACEBOOK = 'facebook'
    COLLECTION_METHOD_WHATSAPP = 'whatsapp'
    COLLECTION_METHOD_CHOICES = [
        (COLLECTION_METHOD_MANUAL_URL, 'Lien saisi à la main'),
        (COLLECTION_METHOD_MANUAL_TEXT, 'Texte saisi à la main'),
        (COLLECTION_METHOD_WEB, 'Page web surveillée'),
        (COLLECTION_METHOD_RSS, 'Flux RSS ou Atom'),
        (COLLECTION_METHOD_NEWSLETTER, 'Newsletter'),
        (COLLECTION_METHOD_FACEBOOK, 'Facebook (saisie semi-automatique)'),
        (COLLECTION_METHOD_WHATSAPP, 'WhatsApp (saisie semi-automatique)'),
    ]

    # Modes automatisables. Les autres modes demandent une intervention
    # humaine : la veille les prepares, elle ne va pas les chercher.
    WATCHABLE_METHODS = (
        COLLECTION_METHOD_WEB,
        COLLECTION_METHOD_RSS,
        COLLECTION_METHOD_NEWSLETTER,
    )

    name = models.CharField('nom de la source', max_length=200)
    url = models.URLField('adresse web', blank=True)
    description = models.TextField('description', blank=True)
    is_verified = models.BooleanField('source vérifiée', default=False)
    collection_method = models.CharField(
        'mode de collecte',
        max_length=20,
        choices=COLLECTION_METHOD_CHOICES,
        blank=True,
        help_text=(
            'Comment la veille obtient-elle les annonces de cette source ? '
            'Facebook et WhatsApp restent des saisies semi-automatiques.'
        ),
    )
    is_watched = models.BooleanField(
        'source surveillée',
        default=False,
        help_text='La veille passe-t-elle dans cette source de son propre chef ?',
    )
    watch_config = models.JSONField(
        'paramètres de surveillance',
        default=dict,
        blank=True,
        help_text=(
            'Réglages propres à cette source : adresse de la liste, '
            'sélecteur des annonces, limite d’annonces par passage.'
        ),
    )
    authorization_note = models.TextField(
        'conditions de reprise et autorisation',
        blank=True,
        help_text=(
            'Ce qui autorise la reprise des annonces de cette source : '
            'accord, conditions d’utilisation respectées, mention '
            '« republication autorisée ». Une surveillance ne démarre pas '
            'sans cette note.'
        ),
    )
    last_collected_at = models.DateTimeField('dernière collecte le', null=True, blank=True)
    last_status = models.CharField('dernier résultat de collecte', max_length=20, blank=True)
    created_at = models.DateTimeField('créée le', auto_now_add=True)

    class Meta:
        verbose_name = 'source'
        verbose_name_plural = 'sources'
        ordering = ['name']

    @property
    def is_watchable(self):
        """Indique si la veille peut surveiller cette source.

        Trois conditions sont reunies : la source est marquee comme
        surveillee, elle porte une autorisation ecrite, et son mode de
        collecte est automatisable. Une source sans autorisation ne
        collecte jamais, quel que soit le reste.
        """
        return bool(
            self.is_watched
            and (self.authorization_note or '').strip()
            and self.collection_method in self.WATCHABLE_METHODS
        )

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField('nom', max_length=120, unique=True)
    slug = models.SlugField('identifiant URL', max_length=120, unique=True)
    description = models.TextField('description', blank=True)

    class Meta:
        verbose_name = 'catégorie'
        verbose_name_plural = 'catégories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class OfferQuerySet(models.QuerySet):
    """Jeux de requetes sur les offres.

    `public()` porte la regle d'affichage du site public : une offre n'est
    visible que si elle est publiee, encore disponible et que sa date limite de
    candidature n'est pas depassee. Les offres sans date limite restent
    visibles en permanence.
    """

    def published(self):
        """Offres publiees, visibles et encore disponibles."""
        return self.filter(
            status=Offer.STATUS_PUBLISHED,
            is_published=True,
            is_available=True,
        )

    def not_expired(self, now=None):
        """Exclut les offres dont la date limite de candidature est depassee.

        Une offre qui clot aujourd'hui reste visible jusqu'a son heure de
        cloture. Une offre sans date limite reste visible.
        """
        now = now or timezone.localtime()
        today = now.date()
        current_time = now.time().replace(tzinfo=None, microsecond=0)
        return self.filter(
            Q(deadline__isnull=True)
            | Q(deadline__gt=today)
            | Q(deadline=today, deadline_time__isnull=True)
            | Q(deadline=today, deadline_time__gt=current_time)
        )

    def public(self, now=None):
        """Offres visibles sur le site public."""
        return self.published().not_expired(now)


class Offer(models.Model):
    EMPLOYER_COMPANY = 'company'
    EMPLOYER_INDIVIDUAL = 'individual'
    EMPLOYER_KIND_CHOICES = [
        (EMPLOYER_COMPANY, 'Entreprise'),
        (EMPLOYER_INDIVIDUAL, 'Particulier'),
    ]
    APPLICATION_METHOD_CHOICES = [
        ('', 'Non précisé'),
        ('online', 'En ligne'),
        ('email', 'Par e-mail'),
        ('phone', 'Par téléphone'),
        ('whatsapp', 'Par WhatsApp'),
        ('physical', 'Dépôt physique'),
        ('other', 'Autre modalité'),
    ]

    STATUS_DRAFT = 'draft'
    STATUS_PENDING = 'pending_review'
    STATUS_PUBLISHED = 'published'
    STATUS_REJECTED = 'rejected'
    STATUS_CLOSED = 'closed'
    STATUS_ARCHIVED = 'archived'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_PENDING, 'En attente de validation'),
        (STATUS_PUBLISHED, 'Publiée'),
        (STATUS_REJECTED, 'Rejetée'),
        (STATUS_CLOSED, 'Fermée'),
        (STATUS_ARCHIVED, 'Archivée'),
    ]

    title = models.CharField('intitulé du poste', max_length=250)
    slug = models.SlugField('identifiant URL', max_length=250, unique=True)
    company_name = models.CharField('entreprise', max_length=200, blank=True)
    employer_kind = models.CharField('type d’employeur', max_length=20, choices=EMPLOYER_KIND_CHOICES, default=EMPLOYER_COMPANY)
    category = models.ForeignKey(Category, verbose_name='catégorie', on_delete=models.SET_NULL, null=True, blank=True, related_name='offers')
    source = models.ForeignKey(Source, verbose_name='source de l’offre', on_delete=models.SET_NULL, null=True, blank=True, related_name='offers')
    location = models.CharField('lieu', max_length=200, blank=True)
    employment_type = models.CharField('type de contrat', max_length=100, blank=True)
    description = models.TextField('description du poste', blank=True)
    missions = models.TextField('missions du poste', blank=True)
    required_profile = models.TextField('profil recherché', blank=True)
    required_education = models.CharField(
        'niveau d’études demandé',
        max_length=120,
        blank=True,
    )
    salary_min = models.DecimalField('rémunération minimale', max_digits=12, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField('rémunération maximale', max_digits=12, decimal_places=2, null=True, blank=True)
    salary_currency = models.CharField('devise', max_length=10, blank=True)
    salary_note = models.CharField('précision sur la rémunération', max_length=200, blank=True)
    experience_required = models.CharField('expérience demandée', max_length=120, blank=True)
    deadline = models.DateField('date limite de candidature', null=True, blank=True)
    deadline_time = models.TimeField('heure limite de candidature', null=True, blank=True)
    schedule = models.CharField('horaires', max_length=120, blank=True)
    application_method = models.CharField('mode principal de candidature', max_length=20, choices=APPLICATION_METHOD_CHOICES, blank=True)
    application_url = models.URLField('lien de candidature', blank=True)
    application_email = models.EmailField('adresse e-mail de candidature', blank=True)
    whatsapp_number = models.CharField('numéro WhatsApp', max_length=30, blank=True)
    application_phone = models.CharField('téléphone de candidature', max_length=30, blank=True)
    application_instructions = models.TextField('autres modalités de candidature', blank=True)
    required_documents = models.TextField('dossier de candidature à fournir', blank=True)
    is_source_confirmed = models.BooleanField('source vérifiée', default=False)
    is_employer_verified = models.BooleanField('employeur vérifié', default=False)
    is_published = models.BooleanField('publiée', default=False)
    is_available = models.BooleanField('toujours disponible', default=True)
    availability_confirmed_at = models.DateTimeField('disponibilité vérifiée le', null=True, blank=True)
    status = models.CharField('statut éditorial', max_length=40, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    quarantine_reason = models.TextField(
        'motif de quarantaine',
        blank=True,
        help_text=(
            'Calculé automatiquement à partir de la liste noire et des '
            'mots-clés de quarantaine. Tant que ce motif est présent et non '
            'contrôlé, la publication est refusée.'
        ),
    )
    quarantined_at = models.DateTimeField('mise en quarantaine le', null=True, blank=True)
    quarantine_reviewed_at = models.DateTimeField('contrôle effectué le', null=True, blank=True)
    quarantine_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='contrôle effectué par',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quarantine_reviews',
    )
    quarantine_severity = models.CharField(
        'gravité de la quarantaine',
        max_length=20,
        blank=True,
        help_text=(
            'none : pas de quarantaine ; watch : sous surveillance, '
            'publication possible après contrôle humain ; blocked : contact '
            'bloqué définitivement, publication impossible.'
        ),
    )
    view_count = models.PositiveIntegerField(
        'consultations',
        default=0,
        help_text='Nombre de fiches consultées. Compteur interne, jamais affiché au public.',
    )
    created_at = models.DateTimeField('créée le', auto_now_add=True)
    updated_at = models.DateTimeField('modifiée le', auto_now=True)
    published_at = models.DateTimeField('publiée le', null=True, blank=True)

    objects = OfferQuerySet.as_manager()

    class Meta:
        verbose_name = 'offre'
        verbose_name_plural = 'offres'
        ordering = ['-created_at']

    def is_expired(self, now=None):
        """Indique si la date limite de candidature est depassee.

        Une offre sans date limite n'expire jamais. Une offre qui clot le jour
        meme reste ouverte jusqu'a l'heure de cloture indiquee.
        """
        if not self.deadline:
            return False
        now = now or timezone.localtime()
        today = now.date()
        if self.deadline > today:
            return False
        if self.deadline < today:
            return True
        if self.deadline_time:
            return self.deadline_time <= now.time().replace(
                tzinfo=None, microsecond=0
            )
        return False

    def clean(self):
        super().clean()
        if self.salary_min is not None and self.salary_max is not None and self.salary_min > self.salary_max:
            raise ValidationError({'salary_max': 'La rémunération maximale doit être supérieure ou égale au minimum.'})
        if self.status == self.STATUS_PUBLISHED:
            if not self.title.strip():
                raise ValidationError({'title': 'Le titre est obligatoire pour publier une offre.'})
            if not self.description.strip():
                raise ValidationError({'description': 'La description est obligatoire pour publier une offre.'})
            if not self.company_name.strip():
                raise ValidationError({'company_name': 'Le nom de l’entreprise est obligatoire pour publier une offre.'})
            if not (self.is_source_confirmed or self.is_employer_verified):
                raise ValidationError('Une offre publiée doit avoir une source ou un employeur vérifié.')
            if (
                self.quarantine_reason
                and not getattr(self, '_skip_quarantine_rule', False)
            ):
                if self.quarantine_severity == 'blocked':
                    # Un contact bloque definitivement ne peut jamais etre
                    # publie, meme apres un controle humain : c est la
                    # regle de la liste noire.
                    raise ValidationError(
                        {
                            'status': (
                                'Cette offre correspond a un contact bloque '
                                'definitivement sur la liste noire. Elle ne peut '
                                'pas etre publiee.'
                            )
                        }
                    )
                if not self.quarantine_reviewed_at:
                    raise ValidationError(
                        {
                            'status': (
                                'Cette offre est en quarantaine et son controle '
                                'n est pas encore enregistre. Verifiez le motif '
                                'avant de publier.'
                            )
                        }
                    )

    def _validate_without_quarantine(self):
        """Valide l offre sans tenir compte du motif de quarantaine.

        Reserve a l administration : poser ou lever une quarantaine ne doit
        pas etre bloque par la regle de publication. Tous les autres
        controles restent appliques.
        """
        if self.status != self.STATUS_PUBLISHED:
            return
        if not self.title.strip():
            raise ValidationError({'title': 'Le titre est obligatoire pour publier une offre.'})
        if not self.description.strip():
            raise ValidationError({'description': 'La description est obligatoire pour publier une offre.'})
        if not self.company_name.strip():
            raise ValidationError({'company_name': 'Le nom de l entreprise est obligatoire pour publier une offre.'})
        if not (self.is_source_confirmed or self.is_employer_verified):
            raise ValidationError('Une offre publiee doit avoir une source ou un employeur verifie.')

    @staticmethod
    def _quarantine_only_fields(kwargs):
        """Indique si la sauvegarde ne touche qu'a la quarantaine.

        Dans ce cas la regle de publication ne doit pas s'appliquer : poser
        ou lever une quarantaine ne modifie ni le contenu ni le statut
        editorial de l'offre.
        """
        update_fields = kwargs.get('update_fields')
        if not update_fields:
            return False
        quarantine_fields = {
            'quarantine_reason',
            'quarantined_at',
            'quarantine_reviewed_at',
            'quarantine_reviewed_by',
        }
        return set(update_fields) <= quarantine_fields

    def _screen_against_blacklist(self):
        """Croise l offre avec la liste noire et les mots-cles.

        Le motif n est jamais efface ici : une quarantaine posee par
        l equipe reste en place tant qu un controle complet ne l a pas
        levee.
        """
        from . import moderation

        reasons, severity = moderation.evaluate_offer(self)
        if not reasons:
            return

        text = moderation.quarantine_text(reasons)
        if self.quarantine_reason != text:
            # Le motif a change : un controle humain est redemande.
            self.quarantine_reviewed_at = None
            self.quarantine_reviewed_by = None
        self.quarantine_reason = text
        self.quarantine_severity = severity
        if self.quarantined_at is None:
            self.quarantined_at = timezone.now()

    def save(self, *args, skip_quarantine_check=False, **kwargs):
        if not self.slug:
            generated_slug = slugify(self.title)
            self.slug = generated_slug or 'offre'

        # Le croisement avec la liste noire est automatique : une offre
        # qui correspond a un contact inscrit est signalee avant meme
        # d etre enregistree.
        self._screen_against_blacklist()

        if skip_quarantine_check:
            # Utilise par l'administration pour poser ou lever une quarantaine
            # sans repasser par la regle de publication.
            self._validate_without_quarantine()
        else:
            self._skip_quarantine_rule = self._quarantine_only_fields(kwargs)
            try:
                self.full_clean()
            finally:
                self._skip_quarantine_rule = False

        if self.status == self.STATUS_PUBLISHED:
            self.is_published = True
            if self.published_at is None:
                self.published_at = timezone.now()
        elif self.status in {
            self.STATUS_DRAFT,
            self.STATUS_PENDING,
            self.STATUS_REJECTED,
            self.STATUS_CLOSED,
            self.STATUS_ARCHIVED,
        }:
            self.is_published = False
            self.published_at = None
            self.availability_confirmed_at = None

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    @property
    def whatsapp_url(self):
        phone_number = ''.join(character for character in self.whatsapp_number if character in '0123456789')
        if not phone_number:
            return ''
        return f'https://wa.me/{phone_number}'

    @property
    def application_action_url(self):
        if self.application_method == 'physical':
            return '#application'
        if self.application_method == 'whatsapp' or (
            not self.application_method and self.whatsapp_number
        ):
            return self.whatsapp_url or self.application_url
        if self.application_method == 'email':
            return f'mailto:{self.application_email}' if self.application_email else ''
        if self.application_method == 'phone':
            return f'tel:{self.application_phone}' if self.application_phone else ''
        if self.application_method == 'online':
            return self.application_url
        if self.application_method == 'other':
            return '#application' if self.application_instructions else ''
        if self.application_url:
            return self.application_url
        if self.application_email:
            return f'mailto:{self.application_email}'
        if self.application_phone:
            return f'tel:{self.application_phone}'
        if self.application_instructions:
            return '#application'
        return ''

    @property
    def application_action_label(self):
        if self.application_method == 'physical':
            return 'Dépôt physique'
        return 'Postuler'

    @property
    def application_channel_label(self):
        explicit_labels = {
            'online': 'Candidature en ligne',
            'email': 'Dépôt de candidature par e-mail',
            'phone': 'Dépôt de candidature par téléphone',
            'whatsapp': 'Dépôt de candidature par WhatsApp',
            'physical': 'Dépôt physique',
        }
        if self.application_method in explicit_labels:
            return explicit_labels[self.application_method]
        if self.application_method == 'other':
            return 'Autre modalité de candidature'
        if self.application_action_is_whatsapp:
            return 'Dépôt de candidature par WhatsApp'
        if self.application_email:
            return 'Dépôt de candidature par e-mail'
        if self.application_phone:
            return 'Dépôt de candidature par téléphone'
        if self.application_url:
            return 'Candidature en ligne'
        if self.application_instructions:
            return 'Modalités précisées dans les instructions'
        return 'Modalité de candidature non précisée'

    @property
    def application_action_is_whatsapp(self):
        if self.application_method == 'whatsapp':
            return True
        if self.application_method:
            return False
        application_url = self.application_url.lower()
        return bool(self.whatsapp_number) or 'wa.me/' in application_url or 'whatsapp.com/' in application_url

    @property
    def employer_verification_label(self):
        if self.employer_kind == self.EMPLOYER_INDIVIDUAL:
            return 'Employeur vérifié' if self.is_employer_verified else 'Employeur non vérifié'
        return 'Entreprise vérifiée' if self.is_employer_verified else 'Entreprise non vérifiée'


class OfferSubmission(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'En attente'),
        (STATUS_ACCEPTED, 'Acceptée'),
        (STATUS_REJECTED, 'Rejetée'),
    ]
    DECLARANT_EMPLOYER = 'employer'
    DECLARANT_WITNESS = 'witness'
    DECLARANT_ROLE_CHOICES = [
        (DECLARANT_EMPLOYER, 'Recruteur ou entreprise émettrice'),
        (DECLARANT_WITNESS, 'Veilleur ou candidat'),
    ]

    company_name = models.CharField('entreprise', max_length=200)
    employer_kind = models.CharField('type d’employeur', max_length=20, choices=Offer.EMPLOYER_KIND_CHOICES, default=Offer.EMPLOYER_COMPANY)
    title = models.CharField('intitulé du poste', max_length=250)
    location = models.CharField('ville ou lieu', max_length=200, blank=True)
    employment_type = models.CharField('type d’opportunité', max_length=100, blank=True)
    salary_min = models.DecimalField('rémunération minimale', max_digits=12, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField('rémunération maximale', max_digits=12, decimal_places=2, null=True, blank=True)
    salary_currency = models.CharField('devise', max_length=10, blank=True)
    salary_note = models.CharField('précision sur la rémunération', max_length=200, blank=True)
    experience_required = models.CharField('expérience demandée', max_length=120, blank=True)
    deadline = models.DateField('date limite de candidature', null=True, blank=True)
    deadline_time = models.TimeField('heure limite de candidature', null=True, blank=True)
    schedule = models.CharField('horaires', max_length=120, blank=True)
    contact_email = models.EmailField('e-mail de contact', blank=True)
    contact_phone = models.CharField('téléphone de contact', max_length=30, blank=True)
    declarant_role = models.CharField(
        'rôle du déclarant',
        max_length=20,
        choices=DECLARANT_ROLE_CHOICES,
        default=DECLARANT_EMPLOYER,
    )
    ethics_commitment = models.BooleanField('engagement éthique', default=False)
    details = models.TextField('détails de l’offre', blank=True)
    source_name = models.CharField('nom de la source', max_length=200, blank=True)
    source_url = models.URLField('lien de l’annonce originale', blank=True)
    application_method = models.CharField('mode principal de candidature', max_length=20, choices=Offer.APPLICATION_METHOD_CHOICES, blank=True)
    application_url = models.URLField('lien de candidature', blank=True)
    application_email = models.EmailField('e-mail de candidature', blank=True)
    whatsapp_number = models.CharField('numéro WhatsApp', max_length=30, blank=True)
    application_phone = models.CharField('téléphone de candidature', max_length=30, blank=True)
    application_instructions = models.TextField('autres modalités de candidature', blank=True)
    required_documents = models.TextField('dossier de candidature à fournir', blank=True)
    status = models.CharField('décision éditoriale', max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDING)
    quarantine_reason = models.TextField(
        'motif de quarantaine',
        blank=True,
        help_text=(
            'Calculé automatiquement à partir de la liste noire et des '
            'mots-clés de quarantaine. Une proposition mise en quarantaine '
            'reste en attente : elle n’est jamais publiée automatiquement.'
        ),
    )
    quarantined_at = models.DateTimeField('mise en quarantaine le', null=True, blank=True)
    quarantine_severity = models.CharField(
        'gravité de la quarantaine',
        max_length=20,
        blank=True,
    )
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='traitée par', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_submissions')
    reviewed_at = models.DateTimeField('traitée le', null=True, blank=True)
    offer = models.OneToOneField(Offer, verbose_name='offre créée', on_delete=models.SET_NULL, null=True, blank=True, related_name='submission')
    created_at = models.DateTimeField('reçue le', auto_now_add=True)

    class Meta:
        verbose_name = 'soumission'
        verbose_name_plural = 'soumissions'
        ordering = ['-created_at']

    def _screen_against_blacklist(self):
        """Croise la proposition avec la liste noire et les mots-cles.

        Une proposition signalee reste en attente : elle n est jamais
        publiee automatiquement.
        """
        from . import moderation

        reasons, severity = moderation.evaluate_submission(self)
        if not reasons:
            return

        self.quarantine_reason = moderation.quarantine_text(reasons)
        self.quarantine_severity = severity
        if self.quarantined_at is None:
            self.quarantined_at = timezone.now()

    def save(self, *args, **kwargs):
        self._screen_against_blacklist()
        super().save(*args, **kwargs)

    def create_offer_from_submission(self):
        if self.status != self.STATUS_ACCEPTED:
            raise ValueError('Une soumission doit être acceptée avant de créer une offre.')
        if self.offer_id:
            return self.offer

        base_slug = slugify(self.title) or 'offre'
        slug = base_slug
        suffix = 1
        while Offer.objects.filter(slug=slug).exists():
            slug = f'{base_slug}-{suffix}'
            suffix += 1

        source = None
        if self.source_name or self.source_url:
            source = Source.objects.filter(url=self.source_url).first() if self.source_url else None
            if source is None and self.source_name:
                source = Source.objects.filter(name=self.source_name, url='').first()
            if source is None:
                source = Source.objects.create(
                    name=self.source_name or f'Source de la proposition — {self.company_name}',
                    url=self.source_url,
                    is_verified=False,
                )

        offer = Offer.objects.create(
            title=self.title,
            slug=slug,
            company_name=self.company_name,
            employer_kind=self.employer_kind,
            location=self.location,
            employment_type=self.employment_type,
            description=self.details or 'Description fournie par la soumission.',
            salary_min=self.salary_min,
            salary_max=self.salary_max,
            salary_currency=self.salary_currency,
            salary_note=self.salary_note,
            experience_required=self.experience_required,
            deadline=self.deadline,
            deadline_time=self.deadline_time,
            schedule=self.schedule,
            source=source,
            application_method=self.application_method,
            application_url=self.application_url,
            application_email=self.application_email,
            whatsapp_number=self.whatsapp_number,
            application_phone=self.application_phone,
            application_instructions=self.application_instructions,
            required_documents=self.required_documents,
            is_source_confirmed=False,
            is_employer_verified=False,
            is_published=False,
            status=Offer.STATUS_PENDING,
        )
        self.offer = offer
        self.reviewed_at = timezone.now()
        self.save(update_fields=['offer', 'reviewed_at'])
        return offer

    def __str__(self):
        return f"{self.title} - {self.company_name}"


class OfferReport(models.Model):
    STATUS_OPEN = 'open'
    STATUS_REVIEWED = 'reviewed'
    STATUS_RESOLVED = 'resolved'
    STATUS_IGNORED = 'ignored'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Ouvert'),
        (STATUS_REVIEWED, 'En cours de vérification'),
        (STATUS_RESOLVED, 'Résolu'),
        (STATUS_IGNORED, 'Ignoré'),
    ]

    REASON_FEES = 'fees'
    REASON_FAKE_COMPANY = 'fake_company'
    REASON_IMPERSONATION = 'impersonation'
    REASON_MLM = 'mlm'
    REASON_DANGEROUS_MEETING = 'dangerous_meeting'
    REASON_MISLEADING = 'misleading'
    REASON_INVALID_LINK = 'invalid_link'
    REASON_OTHER = 'other'
    REASON_CHOICES = [
        (REASON_FEES, 'Demande de frais (Mobile Money, Wave, espèces)'),
        (REASON_FAKE_COMPANY, 'Entreprise fictive ou faux employeur'),
        (REASON_IMPERSONATION, 'Usurpation d’identité (ministère, ONG, entreprise connue)'),
        (REASON_MLM, 'Réseau MLM ou vente pyramidale'),
        (REASON_DANGEROUS_MEETING, 'Lieu de rendez-vous dangereux'),
        (REASON_MISLEADING, 'Informations inexactes ou annonce déjà pourvue'),
        (REASON_INVALID_LINK, 'Lien de candidature invalide'),
        (REASON_OTHER, 'Autre comportement anormal'),
    ]

    CHANNEL_WHATSAPP = 'whatsapp'
    CHANNEL_FACEBOOK = 'facebook'
    CHANNEL_WEBSITE = 'website'
    CHANNEL_IN_PERSON = 'in_person'
    CHANNEL_FASOJOB = 'fasojob'
    CHANNEL_OTHER = 'other'
    CHANNEL_CHOICES = [
        (CHANNEL_WHATSAPP, 'WhatsApp'),
        (CHANNEL_FACEBOOK, 'Facebook'),
        (CHANNEL_WEBSITE, 'Site web ou messagerie'),
        (CHANNEL_IN_PERSON, 'De bouche à oreille'),
        (CHANNEL_FASOJOB, 'Sur Faso Job'),
        (CHANNEL_OTHER, 'Autre canal'),
    ]

    offer = models.ForeignKey(
        Offer,
        verbose_name='offre concernée',
        on_delete=models.CASCADE,
        related_name='reports',
        null=True,
        blank=True,
    )
    reason = models.CharField(
        'motif principal',
        max_length=30,
        choices=REASON_CHOICES,
        default=REASON_OTHER,
    )
    suspect_title = models.CharField('intitulé du poste suspect', max_length=250, blank=True)
    suspect_organization = models.CharField(
        'entreprise ou organisation mise en cause',
        max_length=200,
        blank=True,
    )
    suspect_phone = models.CharField(
        'téléphone ou identifiant Mobile Money',
        max_length=60,
        blank=True,
    )
    suspect_channel = models.CharField(
        'canal de provenance',
        max_length=20,
        choices=CHANNEL_CHOICES,
        blank=True,
    )
    suspect_url = models.CharField('lien ou canal de provenance', max_length=300, blank=True)
    amount_requested = models.DecimalField(
        'montant réclamé (FCFA)',
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    location_mentioned = models.CharField('ville ou lieu évoqué', max_length=200, blank=True)
    details = models.TextField('description des faits', blank=True)
    evidence = models.FileField(
        'preuve jointe',
        upload_to='signalements/%Y/%m/',
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(['png', 'jpg', 'jpeg', 'webp', 'pdf']),
            validate_evidence_size,
        ],
    )
    reporter_name = models.CharField('nom du déclarant', max_length=200, blank=True)
    reporter_email = models.EmailField('e-mail du déclarant', blank=True)
    reporter_phone = models.CharField('téléphone du déclarant', max_length=30, blank=True)
    status = models.CharField('état du signalement', max_length=30, choices=STATUS_CHOICES, default=STATUS_OPEN)
    admin_note = models.TextField('note interne de traitement', blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='traité par', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_reports')
    reviewed_at = models.DateTimeField('traité le', null=True, blank=True)
    created_at = models.DateTimeField('reçu le', auto_now_add=True)

    class Meta:
        verbose_name = 'signalement'
        verbose_name_plural = 'signalements'
        ordering = ['-created_at']

    def clean(self):
        super().clean()
        has_identifier = any(
            (
                self.suspect_title,
                self.suspect_organization,
                self.suspect_phone,
                self.suspect_url,
            )
        )
        if self.offer_id is None and not has_identifier:
            raise ValidationError(
                'Indiquez au moins un élément permettant d’identifier l’annonce, '
                'l’entreprise ou la personne mise en cause.'
            )

    def mark_reviewed(self, user):
        self.status = self.STATUS_REVIEWED
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

    def mark_resolved(self, user):
        self.status = self.STATUS_RESOLVED
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

    def __str__(self):
        if self.offer_id:
            return f"Signalement - {self.offer.title}"
        return (
            f"Signalement - {self.suspect_title or self.suspect_organization or 'annonce non précisée'}"
        )


class BlacklistedContact(models.Model):
    """Registre privé des contacts et entités signalés comme frauduleux.

    Ce registre est réservé à l'administration : il n'est jamais exposé
    publiquement et ne modifie jamais automatiquement le statut d'une offre.
    Un signalement reçu ne suffit pas à bloquer un contact : l'équipe
    éditoriale décide elle-même du statut.
    """

    STATUS_BLOCKED = 'blocked'
    STATUS_WATCH = 'watch'
    STATUS_NEUTRALIZED = 'neutralized'
    STATUS_CHOICES = [
        (STATUS_BLOCKED, 'Bloqué actif (définitif)'),
        (STATUS_WATCH, 'Sous surveillance'),
        (STATUS_NEUTRALIZED, 'Coordonnées neutralisées'),
    ]

    OPERATOR_ORANGE = 'orange_money'
    OPERATOR_MOOV = 'moov_money'
    OPERATOR_OTHER = 'other'
    OPERATOR_CHOICES = [
        (OPERATOR_ORANGE, 'Orange Money'),
        (OPERATOR_MOOV, 'Moov Money'),
        (OPERATOR_OTHER, 'Autre opérateur ou non précisé'),
    ]

    phone_number = models.CharField('numéro ou identifiant Mobile Money', max_length=60)
    email = models.EmailField('e-mail associé au contact', blank=True)
    operator = models.CharField(
        'opérateur réseau',
        max_length=20,
        choices=OPERATOR_CHOICES,
        default=OPERATOR_ORANGE,
    )
    declared_name = models.CharField('nom SIM déclaré', max_length=200, blank=True)
    organization = models.CharField('entité ou entreprise usurpée', max_length=200)
    reason = models.CharField(
        'motif principal',
        max_length=30,
        choices=OfferReport.REASON_CHOICES,
        default=OfferReport.REASON_OTHER,
    )
    amount_requested = models.DecimalField(
        'somme extorquée (FCFA)',
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    status = models.CharField(
        'statut',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_WATCH,
    )
    details = models.TextField('vecteurs d’escroquerie constatés', blank=True)
    report = models.ForeignKey(
        OfferReport,
        verbose_name='signalement à l’origine',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blacklist_entries',
    )
    alert_disseminated = models.BooleanField(
        'alerte WhatsApp diffusée manuellement',
        default=False,
        help_text=(
            'À cocher par l’équipe après diffusion manuelle de l’alerte. '
            'La plateforme n’envoie aucun message automatiquement.'
        ),
    )
    alert_disseminated_at = models.DateTimeField(
        'alerte diffusée le',
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='inscrit par',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blacklist_entries',
    )
    created_at = models.DateTimeField('inscrit le', auto_now_add=True)
    updated_at = models.DateTimeField('modifié le', auto_now=True)


    class Meta:
        verbose_name = 'contact sur liste noire'
        verbose_name_plural = 'contacts sur liste noire'
        ordering = ['-created_at']

    def clean(self):
        super().clean()
        if not self.phone_number.strip():
            raise ValidationError(
                {'phone_number': 'Indiquez le numéro ou l’identifiant Mobile Money.'}
            )
        if not self.organization.strip():
            raise ValidationError(
                {'organization': 'Indiquez l’entité ou l’entreprise mise en cause.'}
            )

    @property
    def normalized_number(self):
        """Numéro réduit aux seuls chiffres, pour les rapprochements ultérieurs."""
        return ''.join(character for character in self.phone_number if character.isdigit())

    def save(self, *args, **kwargs):
        """Enregistre le contact et recontrole les annonces liees.

        Inscrire un contact sur la liste noire doit avoir un effet
        immediat : les offres et propositions qui utilisent ses
        coordonnees sont signalees aussitot.

        Le statut de ces annonces n est pas modifie : leur suspension
        reste une decision humaine.
        """
        # La date de diffusion est portee par le cocheur : elle n est pas
        # saisie et suit l etat de la case.
        if self.alert_disseminated and self.alert_disseminated_at is None:
            self.alert_disseminated_at = timezone.now()
        if not self.alert_disseminated:
            self.alert_disseminated_at = None

        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new:
            self.rescreen_linked_offers()

    def rescreen_linked_offers(self):
        """Recontrole les offres et propositions liees a ce contact.

        Renvoie le couple (offres signalees, propositions signalees).
        """
        from . import moderation

        try:
            return moderation.rescreen_for_contact(self)
        except Exception:
            # Un controle indisponible ne doit jamais empecher
            # l enregistrement d une decision de l equipe.
            return 0, 0

    def __str__(self):
        return f'{self.organization} — {self.phone_number}'


class PlatformSettings(models.Model):
    """Paramètres opérationnels de la plateforme (ligne unique)."""

    DEFAULT_SITE_NAME = 'Faso Job'
    DEFAULT_SITE_TAGLINE = 'Opportunités professionnelles au Burkina Faso'

    site_name = models.CharField(
        'nom de la plateforme',
        max_length=120,
        default=DEFAULT_SITE_NAME,
    )
    site_tagline = models.CharField(
        'sous-titre',
        max_length=200,
        default=DEFAULT_SITE_TAGLINE,
    )
    contact_email = models.EmailField('e-mail de contact de la plateforme', blank=True)
    alert_email = models.EmailField('adresse d’alerte critique', blank=True)
    emergency_phone = models.CharField('téléphone d’urgence (BF)', max_length=30, blank=True)
    emergency_whatsapp = models.CharField(
        'numéro WhatsApp d’urgence (BF)',
        max_length=30,
        blank=True,
    )
    moderation_guideline = models.TextField(
        'règle de modération en vigueur',
        blank=True,
        help_text=(
            'Règle écrite appliquée par l’équipe lors du contrôle des annonces. '
            'Ce texte est affiché à l’administration, pas au public.'
        ),
    )
    quarantine_keywords = models.TextField(
        'mots-clés de quarantaine',
        blank=True,
        help_text=(
            'Un mot-clé par ligne. Une annonce contenant l’un de ces termes est '
            'signalée à l’administration et ne peut pas être publiée sans un '
            'contrôle humain enregistré. Exemple : frais de dossier, caution.'
        ),
    )
    auto_archive_days = models.PositiveIntegerField(
        'archivage automatique après (jours)',
        default=0,
        help_text=(
            'Nombre de jours après la date limite au-delà duquel une offre '
            'publiée est archivée automatiquement. 0 désactive l’archivage '
            'automatique.'
        ),
    )
    view_counter_enabled = models.BooleanField(
        'compteur de vues actif',
        default=True,
        help_text=(
            'Compte les consultations de fiche d’offre. Aucun compteur n’est '
            'affiché au public et aucune donnée personnelle n’est conservée.'
        ),
    )
    notifications_enabled = models.BooleanField(
        'notifications e-mail actives',
        default=False,
        help_text=(
            'Envoie un e-mail à l’équipe lorsqu’une proposition ou un '
            'signalement est reçu. Désactivé par défaut : aucune adresse '
            'n’est envoyée tant qu’aucune adresse d’alerte n’est renseignée.'
        ),
    )
    updated_at = models.DateTimeField('modifié le', auto_now=True)


    class Meta:
        verbose_name = 'paramètres de la plateforme'
        verbose_name_plural = 'paramètres de la plateforme'

    def save(self, *args, **kwargs):
        # Ligne unique garantie : les paramètres sont toujours la même entrée.
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """Renvoie la ligne de paramètres, en la créant au premier accès."""
        instance, _created = cls.objects.get_or_create(pk=1)
        return instance

    @classmethod
    def reset_to_defaults(cls):
        """Restaure les valeurs par défaut et enregistre la ligne unique."""
        instance = cls(
            pk=1,
            site_name=cls.DEFAULT_SITE_NAME,
            site_tagline=cls.DEFAULT_SITE_TAGLINE,
            contact_email='',
            alert_email='',
            emergency_phone='',
            emergency_whatsapp='',
            moderation_guideline='',
            quarantine_keywords='',
            auto_archive_days=0,
            view_counter_enabled=True,
            notifications_enabled=False,
        )
        instance.save()
        return instance

    def __str__(self):
        return self.site_name


class OfferView(models.Model):
    """Consultation d'une fiche d'offre.

    Une ligne par session et par offre : elle sert a ne pas compter deux
    fois la meme consultation. Aucun identifiant personnel n'est conserve.
    """

    offer = models.ForeignKey(
        Offer,
        verbose_name='offre consultée',
        on_delete=models.CASCADE,
        related_name='views',
    )
    session_key = models.CharField('clé de session', max_length=60)
    created_at = models.DateTimeField('consultée le', auto_now_add=True)

    class Meta:
        verbose_name = 'consultation'
        verbose_name_plural = 'consultations'
        ordering = ['-created_at']

    def __str__(self):
        return f'Consultation - {self.offer_id}'


class OfferClick(models.Model):
    """Clic vers le canal de candidature d'une offre."""

    CHANNEL_WHATSAPP = 'whatsapp'
    CHANNEL_EMAIL = 'email'
    CHANNEL_PHONE = 'phone'
    CHANNEL_ONLINE = 'online'
    CHANNEL_PHYSICAL = 'physical'
    CHANNEL_OTHER = 'other'
    CHANNEL_CHOICES = [
        (CHANNEL_WHATSAPP, 'WhatsApp'),
        (CHANNEL_EMAIL, 'E-mail'),
        (CHANNEL_PHONE, 'Téléphone'),
        (CHANNEL_ONLINE, 'En ligne'),
        (CHANNEL_PHYSICAL, 'Dépôt physique'),
        (CHANNEL_OTHER, 'Autre'),
    ]

    offer = models.ForeignKey(
        Offer,
        verbose_name='offre concernée',
        on_delete=models.CASCADE,
        related_name='clicks',
    )
    channel = models.CharField('canal', max_length=20, choices=CHANNEL_CHOICES)
    session_key = models.CharField('clé de session', max_length=60)
    created_at = models.DateTimeField('clique le', auto_now_add=True)

    class Meta:
        verbose_name = 'clic sortant'
        verbose_name_plural = 'clics sortants'
        ordering = ['-created_at']

    def __str__(self):
        return f'Clic - {self.offer_id} ({self.channel})'


class OutboundMessage(models.Model):
    """Journal des messages sortants prepares par la plateforme.

    Ce registre est une **preparation**, pas un envoi. Aucun fournisseur
    n'est configure par defaut : tant qu aucun adaptateur n'est configure,
    les messages restent au statut « non configure » et aucun envoi reel
    n'est simule.

    Les coordonnees du destinataire ne sont conservees que pour le temps
    du traitement : ce registre est reserve a l'administration.
    """

    CHANNEL_WHATSAPP = 'whatsapp'
    CHANNEL_SMS = 'sms'
    CHANNEL_EMAIL = 'email'
    CHANNEL_CHOICES = [
        (CHANNEL_WHATSAPP, 'WhatsApp'),
        (CHANNEL_SMS, 'SMS'),
        (CHANNEL_EMAIL, 'E-mail'),
    ]

    STATUS_NOT_CONFIGURED = 'not_configured'
    STATUS_PENDING = 'pending'
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_NOT_CONFIGURED, 'Aucun fournisseur configure'),
        (STATUS_PENDING, 'En attente d envoi'),
        (STATUS_SENT, 'Envoye'),
        (STATUS_FAILED, 'Echec de l envoi'),
    ]

    channel = models.CharField('canal', max_length=20, choices=CHANNEL_CHOICES)
    recipient = models.CharField('destinataire', max_length=120)
    body = models.TextField('contenu du message')
    status = models.CharField(
        'etat',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_NOT_CONFIGURED,
    )
    offer = models.ForeignKey(
        Offer,
        verbose_name='offre concernee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='outbound_messages',
    )
    submission = models.ForeignKey(
        OfferSubmission,
        verbose_name='proposition concernee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='outbound_messages',
    )
    provider = models.CharField(
        'adaptateur utilise',
        max_length=60,
        blank=True,
        help_text='Nom de l adaptateur qui a prepare le message.',
    )
    error = models.TextField('erreur rencontree', blank=True)
    created_at = models.DateTimeField('prepare le', auto_now_add=True)
    sent_at = models.DateTimeField('envoye le', null=True, blank=True)

    class Meta:
        verbose_name = 'message sortant'
        verbose_name_plural = 'messages sortants'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_channel_display()} vers {self.recipient} ({self.get_status_display()})'


class NotificationRecipient(models.Model):
    """Adresse destinataire des notifications envoyees par la plateforme.

    La liste est geree par l administration : on ajoute une adresse, on en
    retire une, on la desactive temporairement. Les notifications sont
    envoyees a toutes les adresses actives.

    Le champ `alert_email` des parametres reste la premiere adresse
    utilisee : la liste le complete, elle ne le remplace pas.
    """

    email = models.EmailField('adresse e-mail', unique=True)
    label = models.CharField(
        'role',
        max_length=120,
        blank=True,
        help_text='Ex. : moderation, support, direction.',
    )
    is_active = models.BooleanField(
        'active',
        default=True,
        help_text='Une adresse desactivee ne recoit plus de notification.',
    )
    created_at = models.DateTimeField('ajoutee le', auto_now_add=True)
    updated_at = models.DateTimeField('modifiee le', auto_now=True)

    class Meta:
        verbose_name = 'destinataire de notification'
        verbose_name_plural = 'destinataires de notification'
        ordering = ['email']

    def __str__(self):
        return self.label or self.email


class TwoFactorDevice(models.Model):
    """Appareil d'authentification a deux facteurs d un membre de l equipe.

    Le secret partage est stocke chiffre (AES-GCM). Il ne doit jamais etre
    envoye par e-mail ni affiche en clair : seul le QR code et la cle de
    configuration manuelle le revelent, au moment de l activation.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name='utilisateur',
        on_delete=models.CASCADE,
        related_name='two_factor_device',
    )
    secret = models.CharField('secret chiffre', max_length=255)
    is_active = models.BooleanField('active', default=True)
    confirmed_at = models.DateTimeField('activee le', null=True, blank=True)
    last_used_at = models.DateTimeField('derniere utilisation le', null=True, blank=True)
    created_at = models.DateTimeField('creee le', auto_now_add=True)

    class Meta:
        verbose_name = 'double authentification'
        verbose_name_plural = 'double authentification'
        ordering = ['user']

    def __str__(self):
        return f'Double authentification - {self.user}'

    @property
    def is_confirmed(self):
        return self.is_active and self.confirmed_at is not None


class TwoFactorRecoveryCode(models.Model):
    """Code de secours a usage unique, permet de se reconnecter sans telephone.

    Seuls les empreintes des codes sont conservees : la liste en clair
    n'est montree qu'une fois, a l'activation.
    """

    device = models.ForeignKey(
        TwoFactorDevice,
        verbose_name='appareil',
        on_delete=models.CASCADE,
        related_name='recovery_codes',
    )
    code_hash = models.CharField('empreinte du code', max_length=64)
    is_used = models.BooleanField('utilise', default=False)
    created_at = models.DateTimeField('cree le', auto_now_add=True)
    used_at = models.DateTimeField('utilise le', null=True, blank=True)

    class Meta:
        verbose_name = 'code de secours'
        verbose_name_plural = 'codes de secours'
        ordering = ['-created_at']

    def __str__(self):
        return 'Code de secours utilise' if self.is_used else 'Code de secours disponible'


class BackupConfiguration(models.Model):
    """Configuration des sauvegardes automatiques (ligne unique).

    Elle est entierement geree depuis l administration : destination,
    nombre de copies conservees, frequence, format et inclusion des
    fichiers joints.

    Ce que l administration ne peut pas faire : declencher elle-meme la
    sauvegarde au bon moment. L activation demande une tache planifiee
    sur la machine qui heberge le site. La commande a copier-coller est
    affichee dans l administration.
    """

    FREQUENCY_HOURLY = 'hourly'
    FREQUENCY_DAILY = 'daily'
    FREQUENCY_WEEKLY = 'weekly'
    FREQUENCY_CHOICES = [
        (FREQUENCY_HOURLY, 'Toutes les heures'),
        (FREQUENCY_DAILY, 'Chaque nuit'),
        (FREQUENCY_WEEKLY, 'Chaque semaine'),
    ]

    enabled = models.BooleanField(
        'sauvegarde automatique activee',
        default=False,
        help_text=(
            'A activer apres avoir installe la tache planifiee sur le '
            'serveur. Tant que la tache n est pas en place, la sauvegarde '
            'manuelle reste disponible.'
        ),
    )
    destination = models.CharField(
        'dossier de destination',
        max_length=80,
        default='backups',
        help_text='Dossier du projet ou sont ecrites les sauvegardes.',
    )
    filename_prefix = models.CharField(
        'prefixe des fichiers',
        max_length=40,
        default='fasojob',
        help_text='Les fichiers sont horodates : fasojob-2026-11-12-030000.json',
    )
    retention_count = models.PositiveIntegerField(
        'nombre de sauvegardes conservees',
        default=14,
        help_text='Les sauvegardes les plus anciennes sont supprimees. 0 conserve tout.',
    )
    frequency = models.CharField(
        'frequence souhaitee',
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default=FREQUENCY_DAILY,
    )
    compress = models.BooleanField(
        'compresser les fichiers',
        default=True,
        help_text='Les fichiers sont compresses : ils occupent moins de place.',
    )
    include_media = models.BooleanField(
        'inclure les fichiers joints',
        default=False,
        help_text=(
            'Ajoute les preuves jointes aux signalements dans la sauvegarde. '
            'Ces fichiers contiennent des donnees personnelles.'
        ),
    )
    last_run_at = models.DateTimeField('derniere sauvegarde le', null=True, blank=True)
    last_status = models.CharField('dernier resultat', max_length=20, blank=True)
    last_message = models.CharField('dernier message', max_length=255, blank=True)
    updated_at = models.DateTimeField('modifie le', auto_now=True)

    class Meta:
        verbose_name = 'configuration des sauvegardes'
        verbose_name_plural = 'configuration des sauvegardes'

    def save(self, *args, **kwargs):
        # Ligne unique garantie.
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """Renvoie la configuration unique, en la creant au premier acces."""
        instance, _created = cls.objects.get_or_create(pk=1)
        return instance

    def __str__(self):
        return 'Configuration des sauvegardes'


class BackupRun(models.Model):
    """Historique des sauvegardes et des installations realisees."""

    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_FAILURE = 'failure'
    STATUS_CHOICES = [
        (STATUS_RUNNING, 'En cours'),
        (STATUS_SUCCESS, 'Reussie'),
        (STATUS_FAILURE, 'Echec'),
    ]

    TRIGGER_MANUAL = 'manual'
    TRIGGER_SCHEDULED = 'scheduled'
    TRIGGER_RESTORE = 'restore'
    TRIGGER_CHOICES = [
        (TRIGGER_MANUAL, 'Manuelle'),
        (TRIGGER_SCHEDULED, 'Automatique'),
        (TRIGGER_RESTORE, 'Installation'),
    ]

    configuration = models.ForeignKey(
        BackupConfiguration,
        verbose_name='configuration',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='runs',
    )
    triggered_by = models.CharField(
        'declenchee par',
        max_length=20,
        choices=TRIGGER_CHOICES,
        default=TRIGGER_MANUAL,
    )
    status = models.CharField(
        'resultat',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_RUNNING,
    )
    started_at = models.DateTimeField('demarree le')
    finished_at = models.DateTimeField('terminee le', null=True, blank=True)
    duration_seconds = models.PositiveIntegerField('duree (secondes)', default=0)
    actor = models.CharField(
        'realisee par',
        max_length=150,
        blank=True,
        help_text='Compte de l administration a l origine de l operation.',
    )
    file_path = models.CharField('fichier', max_length=255, blank=True)
    file_size = models.PositiveBigIntegerField('taille (octets)', default=0)
    tables_count = models.PositiveIntegerField('tables', default=0)
    rows_count = models.PositiveIntegerField('lignes', default=0)
    message = models.CharField('message', max_length=255, blank=True)

    class Meta:
        verbose_name = 'sauvegarde'
        verbose_name_plural = 'sauvegardes'
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.get_status_display()} - {self.started_at:%d/%m/%Y %H:%M}'


class CollectedAnnouncement(models.Model):
    """Annonce reperee par la veille, conservee avec sa trace de collecte.

    Cette ligne est la preuve de ce qui a ete vu, d ou, quand et comment.
    Elle porte le contenu original : l equipe peut toujours comparer
    l extraction de l IA avec l annonce telle qu elle a ete trouvee.

    Aucun etat de cette ligne ne publie une offre. La publication reste
    une decision humaine prise dans l administration.

    La provenance est consignee deux fois : le lien vers la source, et un
    instantane fige (nom, adresse, date). L instantane survit a la
    suppression de la source : la trace d une annonce reste consultable
    meme si la source disparait du referentiel.
    """

    STATUS_DETECTED = 'detected'
    STATUS_DRAFT_CREATED = 'draft_created'
    STATUS_DUPLICATE = 'duplicate'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_DETECTED, 'Détectée'),
        (STATUS_DRAFT_CREATED, 'Brouillon créé'),
        (STATUS_DUPLICATE, 'Doublon signalé'),
        (STATUS_REJECTED, 'Rejetée'),
    ]

    EXTRACTION_PENDING = 'pending'
    EXTRACTION_DONE = 'done'
    EXTRACTION_FAILED = 'failed'
    EXTRACTION_CHOICES = [
        (EXTRACTION_PENDING, 'Extraction en attente'),
        (EXTRACTION_DONE, 'Extraction faite'),
        (EXTRACTION_FAILED, 'Extraction échouée'),
    ]

    DUPLICATE_NONE = 'none'
    DUPLICATE_SUSPECTED = 'suspected'
    DUPLICATE_CONFIRMED = 'confirmed'
    DUPLICATE_DISMISSED = 'dismissed'
    DUPLICATE_CHOICES = [
        (DUPLICATE_NONE, 'Aucun doublon'),
        (DUPLICATE_SUSPECTED, 'Doublon potentiel'),
        (DUPLICATE_CONFIRMED, 'Doublon confirmé'),
        (DUPLICATE_DISMISSED, 'Doublon écarté'),
    ]

    offer = models.ForeignKey(
        Offer,
        verbose_name='offre créée',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collected_announcements',
    )
    source = models.ForeignKey(
        Source,
        verbose_name='source surveillée',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collected_announcements',
    )
    source_name = models.CharField('nom de la source', max_length=200)
    source_url = models.URLField('adresse originale', blank=True)
    collection_method = models.CharField(
        'méthode de collecte',
        max_length=20,
        choices=Source.COLLECTION_METHOD_CHOICES,
        blank=True,
    )
    collected_at = models.DateTimeField('collectée le', default=timezone.now)
    raw_content = models.TextField(
        'contenu original',
        blank=True,
        help_text=(
            'Texte tel qu il a ete recupere. Il est conserve pour que '
            'l equipe puisse verifier l extraction de l IA.'
        ),
    )
    content_hash = models.CharField(
        'empreinte du contenu',
        max_length=64,
        blank=True,
        db_index=True,
        help_text='Empreinte du contenu original : evite de collecter deux fois la meme annonce.',
    )
    source_published_at = models.DateField(
        'date de publication d’origine',
        null=True,
        blank=True,
    )
    extraction_status = models.CharField(
        'état de l’extraction',
        max_length=20,
        choices=EXTRACTION_CHOICES,
        default=EXTRACTION_PENDING,
    )
    extracted_data = models.JSONField(
        'données extraites',
        default=dict,
        blank=True,
        help_text='Réponse brute de l IA, conservée pour audit.',
    )
    ai_provider = models.CharField('fournisseur utilisé', max_length=60, blank=True)
    ai_model = models.CharField('modèle utilisé', max_length=80, blank=True)
    ai_prompt_version = models.CharField('version du prompt', max_length=40, blank=True)
    duplicate_status = models.CharField(
        'doublon',
        max_length=20,
        choices=DUPLICATE_CHOICES,
        default=DUPLICATE_NONE,
    )
    duplicate_of = models.ForeignKey(
        Offer,
        verbose_name='offre existante proche',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='duplicate_collected_announcements',
    )
    duplicate_score = models.FloatField('score de similarité', null=True, blank=True)
    duplicate_reasons = models.TextField('motifs de rapprochement', blank=True)
    status = models.CharField(
        'état',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DETECTED,
    )
    error_message = models.TextField('erreur rencontrée', blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='examinée par',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_collected_announcements',
    )
    reviewed_at = models.DateTimeField('examinée le', null=True, blank=True)
    created_at = models.DateTimeField('enregistrée le', auto_now_add=True)

    class Meta:
        verbose_name = 'annonce collectée'
        verbose_name_plural = 'annonces collectées'
        ordering = ['-collected_at']

    @property
    def has_extraction(self):
        """Indique si l IA a fini son travail sur cette annonce."""
        return self.extraction_status == self.EXTRACTION_DONE

    @property
    def is_duplicate_flagged(self):
        """Indique si un doublon doit etre presente a l equipe."""
        return self.duplicate_status in {
            self.DUPLICATE_SUSPECTED,
            self.DUPLICATE_CONFIRMED,
        }

    def mark_reviewed(self, user):
        """Enregistre le passage de l annonce devant un humain."""
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.save(update_fields=['reviewed_by', 'reviewed_at'])

    def __str__(self):
        return f'{self.source_name} — {self.collected_at:%d/%m/%Y %H:%M}'


class SourceProposal(models.Model):
    """Source proposÃ©e par l'assistant de decouverte.

    L'assistant propose, l'equipe decide. Cette ligne conserve ce qui
    a ete constate : sans elle, la decision serait prise sur une
    impression, et personne ne pourrait dire plus tard sur quoi elle
    s'appuyait.

    Une proposition ne remplace pas une source : elle conduit a une
    source, ou elle est refusee.
    """

    VERDICT_SOURCE = 'source'
    VERDICT_A_VERIFIER = 'a_verifier'
    VERDICT_ECARTEE = 'ecartee'
    VERDICT_CHOICES = [
        (VERDICT_SOURCE, 'Reprise explicitement autorisÃ©e'),
        (VERDICT_A_VERIFIER, 'Reprise non Ã©tablie'),
        (VERDICT_ECARTEE, 'Source Ã©cartÃ©e'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REFUSED = 'refused'
    STATUS_OBSOLETE = 'obsolete'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'En attente de dÃ©cision'),
        (STATUS_ACCEPTED, 'AutorisÃ©e'),
        (STATUS_REFUSED, 'RefusÃ©e'),
        (STATUS_OBSOLETE, 'DÃ©jÃ  connue'),
    ]

    url = models.URLField('adresse de la page', max_length=500)
    name = models.CharField('nom proposÃ©', max_length=200, blank=True)
    page_title = models.CharField('titre de la page', max_length=250, blank=True)
    kind = models.CharField('type de site', max_length=80, blank=True)
    origin = models.CharField('origine de la proposition', max_length=20, blank=True)
    why = models.TextField('raison donnÃ©e', blank=True)
    verdict = models.CharField(
        'verdict',
        max_length=20,
        choices=VERDICT_CHOICES,
        default=VERDICT_A_VERIFIER,
    )
    score = models.FloatField('score', default=0.0)
    selector = models.CharField('selecteur trouvÃ©', max_length=300, blank=True)
    blocks_count = models.PositiveIntegerField('annonces dÃ©tectÃ©es', default=0)
    sample = models.TextField('Ã©chantillon', blank=True)
    reasons = models.TextField('constats', blank=True)
    conditions_quote = models.TextField('citation des conditions', blank=True)
    conditions_found = models.JSONField(
        'pages de conditions trouvÃ©es',
        default=list,
        blank=True,
    )
    status = models.CharField(
        'dÃ©cision',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    source = models.ForeignKey(
        Source,
        verbose_name='source crÃ©Ã©e',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proposals',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='dÃ©cidÃ©e par',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_source_proposals',
    )
    reviewed_at = models.DateTimeField('dÃ©cidÃ©e le', null=True, blank=True)
    created_at = models.DateTimeField('proposÃ©e le', auto_now_add=True)

    class Meta:
        verbose_name = 'source proposÃ©e'
        verbose_name_plural = 'sources proposÃ©es'
        ordering = ['-created_at']

    @property
    def is_pending(self):
        """Indique si la proposition attend encore une dÃ©cision."""
        return self.status == self.STATUS_PENDING

    @property
    def needs_motivation(self):
        """Indique si l'autorisation doit Ãªtre motivÃ©e par l'Ã©quipe.

        Une source dont la reprise n'est pas Ã©tablie ne peut pas Ãªtre
        autorisÃ©e sans une raison Ã©crite : c'est ce que l'Ã©quipe
        assume en écrivant pourquoi elle accorde cette autorisation.
        """
        return self.verdict == self.VERDICT_A_VERIFIER

    def default_authorization_note(self):
        """Note d'autorisation proposÃ©e, que l'Ã©quipe peut modifier.

        Elle reprend ce que l'assistant a constatÃ©. L'Ã©quipe reste
        libre de la reformuler : c'est sa signature, pas celle du
        modÃ¨le.
        """
        if self.verdict == self.VERDICT_SOURCE:
            base = (
                'Reprise autorisee par le site (constat du %s).'
                % timezone.localtime(self.created_at).strftime('%d/%m/%Y')
            )
            if self.conditions_quote:
                base += ' Citation : Â« %s Â».' % self.conditions_quote[:300]
        else:
            base = (
                'Autorisation accordee par l equipe de Faso Job le %s.'
                % timezone.localtime(self.created_at).strftime('%d/%m/%Y')
            )
            if self.conditions_quote:
                base += ' Conditions relevees : Â« %s Â».' % self.conditions_quote[:300]
        return base

    def __str__(self):
        return self.name or self.url


class VeilleRun(models.Model):
    """Historique des passages de collecte.

    Chaque passage de la veille laisse une ligne : ce qui a ete cherche,
    ce qui a ete trouve, ce qui a ete cree et ce qui a echoue. Une
    erreur de collecte n efface rien et n interrompt pas les autres
    sources : elle est consignee ici.
    """

    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_PARTIAL = 'partial'
    STATUS_FAILURE = 'failure'
    STATUS_CHOICES = [
        (STATUS_RUNNING, 'En cours'),
        (STATUS_SUCCESS, 'Réussie'),
        (STATUS_PARTIAL, 'Partiellement réussie'),
        (STATUS_FAILURE, 'Échouée'),
    ]

    TRIGGER_MANUAL = 'manual'
    TRIGGER_SCHEDULED = 'scheduled'
    TRIGGER_CHOICES = [
        (TRIGGER_MANUAL, 'Manuelle'),
        (TRIGGER_SCHEDULED, 'Automatique'),
    ]

    source = models.ForeignKey(
        Source,
        verbose_name='source',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='veille_runs',
    )
    triggered_by = models.CharField(
        'déclenchée par',
        max_length=20,
        choices=TRIGGER_CHOICES,
        default=TRIGGER_MANUAL,
    )
    status = models.CharField(
        'résultat',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_RUNNING,
    )
    started_at = models.DateTimeField('démarrée le')
    finished_at = models.DateTimeField('terminée le', null=True, blank=True)
    duration_seconds = models.PositiveIntegerField('durée (secondes)', default=0)
    found_count = models.PositiveIntegerField('annonces trouvées', default=0)
    created_count = models.PositiveIntegerField('brouillons créés', default=0)
    duplicate_count = models.PositiveIntegerField('doublons signalés', default=0)
    error_count = models.PositiveIntegerField('erreurs', default=0)
    message = models.CharField('message', max_length=255, blank=True)

    class Meta:
        verbose_name = 'passage de collecte'
        verbose_name_plural = 'passages de collecte'
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.get_status_display()} - {self.started_at:%d/%m/%Y %H:%M}'
