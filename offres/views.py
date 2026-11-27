from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Case, Count, F, IntegerField, Q, Value, When
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from .forms import OfferReportForm, OfferSubmissionForm
from .models import Offer, OfferReport


def _parse_salary_filter(value):
    if not value:
        return None, True
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError):
        return None, False
    if (
        not amount.is_finite()
        or amount < 0
        or amount >= Decimal('10000000000')
        or amount.as_tuple().exponent < -2
    ):
        return None, False
    return amount, True


def _deadline_status(offer, local_now):
    if not offer.deadline:
        return None, '', None

    days_until_deadline = (offer.deadline - local_now.date()).days
    if days_until_deadline == 0 and offer.is_expired(local_now):
        # La date limite est aujourd'hui mais l'heure de cloture est deja passee.
        days_until_deadline = -1

    days_since_deadline = (
        abs(days_until_deadline) if days_until_deadline < 0 else None
    )
    if days_until_deadline < 0:
        urgency = 'expired'
    elif days_until_deadline == 0:
        urgency = 'last-day'
    elif days_until_deadline <= 3:
        urgency = 'urgent'
    elif days_until_deadline <= 7:
        urgency = 'soon'
    else:
        urgency = 'normal'

    return days_until_deadline, urgency, days_since_deadline


def _catalogue_url(params, **overrides):
    """Construit une URL de catalogue en conservant les filtres courants."""
    updated = params.copy()
    for key, value in overrides.items():
        if value in (None, ''):
            updated.pop(key, None)
        else:
            updated[key] = value
    query = updated.urlencode()
    return f"{reverse('catalogue')}?{query}" if query else reverse('catalogue')


def _notify(function_name, target, only_if_quarantined=False):
    """Declenche une notification e-mail sans jamais interrompre le flux.

    Les notifications sont desactivees par defaut dans les parametres : le
    module lui-meme verifie avant d'envoyer quoi que ce soit.
    """
    from . import notifications

    if only_if_quarantined and not getattr(target, 'quarantine_reason', ''):
        return False

    function = getattr(notifications, function_name, None)
    if function is None:
        return False

    try:
        return function(target)
    except Exception:
        return False


def _screen_submission(submission):
    """Passe une proposition reçue au contrôle de modération.

    Une proposition mise en quarantaine reste en attente : elle n’est jamais
    publiée automatiquement. L’équipe est prévenue par le tableau de bord.
    """

    from . import moderation

    try:
        reasons = moderation.screen_submission(submission)
    except Exception:
        # Un controle indisponible ne doit jamais bloquer la reception.
        return
    if not reasons:
        return
    submission.quarantine_reason = moderation.quarantine_text(reasons)
    submission.quarantined_at = timezone.now()
    submission.save(update_fields=['quarantine_reason', 'quarantined_at'])


def _register_offer_view(request, offer):
    """Compte une consultation de fiche d'offre, sans donnee personnelle."""
    from . import tracking

    try:
        tracking.register_offer_view(request, offer)
    except Exception:
        # Le compteur ne doit jamais interrompre l’affichage de la fiche.
        return


def home_view(request):
    local_now = timezone.localtime()
    published_offers = Offer.objects.public(local_now)
    latest_offers = list(
        published_offers.select_related('category', 'source').order_by(
            '-created_at', '-pk'
        )[:4]
    )
    for offer in latest_offers:
        (
            offer.days_until_deadline,
            offer.deadline_urgency,
            offer.days_since_deadline,
        ) = _deadline_status(offer, local_now)

    opportunity_types = list(
        published_offers.exclude(employment_type='')
        .order_by()
        .values('employment_type')
        .annotate(offer_count=Count('pk'))
        .order_by('-offer_count', 'employment_type')[:4]
    )
    locations = list(
        published_offers.exclude(location='')
        .order_by('location')
        .values_list('location', flat=True)
        .distinct()
    )

    context = {
        'title': 'Faso Job — Opportunités professionnelles au Burkina Faso',
        'active_nav': 'home',
        'latest_offers': latest_offers,
        'offer_count': published_offers.count(),
        'opportunity_types': opportunity_types,
        'locations': locations,
    }
    return render(request, 'refonte/home.html', context)


def method_view(request):
    return render(
        request,
        'refonte/method.html',
        {
            'title': 'Comment ça marche — Faso Job',
            'meta_description': (
                'Comment Faso Job collecte, vérifie et publie les offres d’emploi au '
                'Burkina Faso : parcours de contrôle, badges, motifs de refus et '
                'questions fréquentes.'
            ),
            'active_nav': 'method',
        },
    )


def favorites_view(request):
    return render(
        request,
        'refonte/favorites.html',
        {
            'title': 'Mes favoris — Faso Job',
            'meta_description': (
                'Retrouvez les offres que vous avez enregistrées dans ce navigateur.'
            ),
            'active_nav': 'favorites',
        },
    )


def catalogue_view(request):
    local_now = timezone.localtime()
    published_offers = Offer.objects.public(local_now)
    offers = published_offers.select_related('category', 'source')

    keyword = request.GET.get('q', '').strip()
    if keyword:
        offers = offers.filter(
            Q(title__icontains=keyword)
            | Q(company_name__icontains=keyword)
            | Q(description__icontains=keyword)
            | Q(location__icontains=keyword)
        )

    opportunity_type = request.GET.get('type', '').strip()
    if opportunity_type:
        offers = offers.filter(employment_type__iexact=opportunity_type)

    location = request.GET.get('location', '').strip()
    if location:
        offers = offers.filter(location__icontains=location)

    if request.GET.get('source_verified') == '1':
        offers = offers.filter(is_source_confirmed=True)

    if request.GET.get('availability_confirmed') == '1':
        offers = offers.filter(availability_confirmed_at__isnull=False)

    deadline_from = request.GET.get('deadline_from', '').strip()
    deadline_to = request.GET.get('deadline_to', '').strip()
    deadline_error = ''
    parsed_deadline_from = parse_date(deadline_from) if deadline_from else None
    parsed_deadline_to = parse_date(deadline_to) if deadline_to else None
    if (
        (deadline_from and parsed_deadline_from is None)
        or (deadline_to and parsed_deadline_to is None)
    ):
        deadline_error = 'Saisissez une date de clôture valide.'
    elif (
        parsed_deadline_from
        and parsed_deadline_to
        and parsed_deadline_from > parsed_deadline_to
    ):
        deadline_error = 'La date de début doit précéder la date de fin.'
    elif parsed_deadline_from or parsed_deadline_to:
        if parsed_deadline_from:
            offers = offers.filter(deadline__gte=parsed_deadline_from)
        if parsed_deadline_to:
            offers = offers.filter(deadline__lte=parsed_deadline_to)
    if deadline_error:
        offers = Offer.objects.none()

    salary_min = request.GET.get('salary_min', '').strip()
    salary_max = request.GET.get('salary_max', '').strip()
    salary_error = ''
    minimum_salary, minimum_is_valid = _parse_salary_filter(salary_min)
    maximum_salary, maximum_is_valid = _parse_salary_filter(salary_max)
    if not minimum_is_valid or not maximum_is_valid:
        salary_error = 'Saisissez un montant numérique valide.'
        offers = Offer.objects.none()
    elif minimum_salary is not None and maximum_salary is not None and minimum_salary > maximum_salary:
        salary_error = 'Le montant maximal doit être supérieur ou égal au montant minimal.'
        offers = Offer.objects.none()
    else:
        if minimum_salary is not None:
            offers = offers.filter(
                Q(salary_max__gte=minimum_salary)
                | Q(salary_max__isnull=True, salary_min__gte=minimum_salary)
            )
        if maximum_salary is not None:
            offers = offers.filter(salary_min__lte=maximum_salary)

    sort = request.GET.get('sort', 'recent')
    if sort == 'salary':
        offers = offers.order_by(F('salary_min').asc(nulls_last=True), '-created_at')
    elif sort == 'deadline':
        offers = offers.order_by(F('deadline').asc(nulls_last=True), '-created_at')
    elif sort == 'verified':
        offers = offers.order_by('-is_employer_verified', '-is_source_confirmed', '-created_at')
    else:
        sort = 'recent'
        offers = offers.order_by('-created_at')

    paginator = Paginator(offers, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    for offer in page_obj.object_list:
        (
            offer.days_until_deadline,
            offer.deadline_urgency,
            offer.days_since_deadline,
        ) = _deadline_status(offer, local_now)

    params = request.GET.copy()
    params.pop('page', None)

    total_published = published_offers.count()
    opportunity_types = list(
        published_offers.exclude(employment_type='')
        .order_by('employment_type')
        .values_list('employment_type', flat=True)
        .distinct()
    )
    type_counts = list(
        published_offers.exclude(employment_type='')
        .order_by()
        .values('employment_type')
        .annotate(offer_total=Count('pk'))
        .order_by('-offer_total', 'employment_type')
    )
    type_tabs = [
        {
            'label': 'Toutes',
            'value': '',
            'count': total_published,
            'url': _catalogue_url(params, type=None),
            'active': not opportunity_type,
        }
    ]
    for entry in type_counts[:6]:
        type_tabs.append(
            {
                'label': entry['employment_type'],
                'value': entry['employment_type'],
                'count': entry['offer_total'],
                'url': _catalogue_url(params, type=entry['employment_type']),
                'active': opportunity_type.lower() == entry['employment_type'].lower(),
            }
        )

    active_filters = []
    if keyword:
        active_filters.append(
            {'label': f'« {keyword} »', 'remove_url': _catalogue_url(params, q=None)}
        )
    if location:
        active_filters.append(
            {'label': location, 'remove_url': _catalogue_url(params, location=None)}
        )
    if opportunity_type:
        active_filters.append(
            {'label': opportunity_type, 'remove_url': _catalogue_url(params, type=None)}
        )
    if request.GET.get('source_verified') == '1':
        active_filters.append(
            {
                'label': 'Source vérifiée',
                'remove_url': _catalogue_url(params, source_verified=None),
            }
        )
    if request.GET.get('availability_confirmed') == '1':
        active_filters.append(
            {
                'label': 'Disponibilité confirmée',
                'remove_url': _catalogue_url(params, availability_confirmed=None),
            }
        )
    if salary_min:
        active_filters.append(
            {
                'label': f'Rémunération ≥ {salary_min}',
                'remove_url': _catalogue_url(params, salary_min=None),
            }
        )
    if salary_max:
        active_filters.append(
            {
                'label': f'Rémunération ≤ {salary_max}',
                'remove_url': _catalogue_url(params, salary_max=None),
            }
        )
    if deadline_from:
        active_filters.append(
            {
                'label': f'Clôture dès le {deadline_from}',
                'remove_url': _catalogue_url(params, deadline_from=None),
            }
        )
    if deadline_to:
        active_filters.append(
            {
                'label': f'Clôture jusqu’au {deadline_to}',
                'remove_url': _catalogue_url(params, deadline_to=None),
            }
        )

    context = {
        'offers': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'result_count': paginator.count,
        'title': 'Offres d’emploi et opportunités',
        'active_nav': 'catalogue',
        'keyword': keyword,
        'opportunity_type': opportunity_type,
        'location': location,
        'opportunity_types': opportunity_types,
        'locations': list(
            published_offers.exclude(location='')
            .order_by('location')
            .values_list('location', flat=True)
            .distinct()
        ),
        'type_tabs': type_tabs,
        'active_filters': active_filters,
        'has_filters': bool(active_filters),
        'total_published': total_published,
        'salary_min': salary_min,
        'salary_max': salary_max,
        'salary_error': salary_error,
        'deadline_from': deadline_from,
        'deadline_to': deadline_to,
        'deadline_error': deadline_error,
        'sort': sort,
        'page_range': paginator.get_elided_page_range(page_obj.number),
        'querystring': request.GET.copy(),
    }
    context['querystring'].pop('page', None)
    context['querystring'] = context['querystring'].urlencode()
    return render(request, 'refonte/catalogue.html', context)


def offer_detail_view(request, slug):
    local_now = timezone.localtime()
    offer = get_object_or_404(
        Offer.objects.select_related('category', 'source'),
        slug=slug,
        status=Offer.STATUS_PUBLISHED,
        is_published=True,
    )
    if offer.is_expired(local_now):
        # Une offre expirée n'est plus une opportunité active : son contenu
        # n'est pas affiché, le visiteur est renvoyé vers les offres ouvertes.
        return render(
            request,
            'refonte/offer_closed.html',
            {
                'title': 'Offre close — Faso Job',
                'active_nav': 'catalogue',
            },
            status=404,
        )
    similar_criteria = Q()
    similarity_ordering = []
    if offer.category_id:
        similar_criteria |= Q(category_id=offer.category_id)
        similarity_ordering.append(
            Case(
                When(category_id=offer.category_id, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
    if offer.employment_type:
        similar_criteria |= Q(employment_type__iexact=offer.employment_type)
        similarity_ordering.append(
            Case(
                When(employment_type__iexact=offer.employment_type, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
    if offer.location:
        similar_criteria |= Q(location__icontains=offer.location)
        similarity_ordering.append(
            Case(
                When(location__icontains=offer.location, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
    similar_offers = []
    if similarity_ordering:
        similar_offers = list(
            Offer.objects.public(local_now)
            .filter(similar_criteria)
            .exclude(pk=offer.pk)
            .select_related('category')
            .order_by(*[ordering.desc() for ordering in similarity_ordering], '-created_at')[:3]
        )
    if not similar_offers:
        similar_offers = list(
            Offer.objects.public(local_now)
            .exclude(pk=offer.pk)
            .select_related('category')
            .order_by('-created_at', '-pk')[:3]
        )
    (
        days_until_deadline,
        deadline_urgency,
        days_since_deadline,
    ) = _deadline_status(offer, local_now)
    for similar_offer in similar_offers:
        (
            similar_offer.days_until_deadline,
            similar_offer.deadline_urgency,
            similar_offer.days_since_deadline,
        ) = _deadline_status(similar_offer, local_now)

    _register_offer_view(request, offer)

    applications_open = offer.is_available and deadline_urgency != 'expired'
    application_cta_url = offer.application_action_url if applications_open else ''
    if offer.application_action_is_whatsapp:
        application_cta_label = 'Postuler sur WhatsApp'
    elif offer.application_method == 'physical':
        application_cta_label = 'Voir les modalités de dépôt'
    elif application_cta_url.startswith('mailto:'):
        application_cta_label = 'Postuler par e-mail'
    elif application_cta_url.startswith('tel:'):
        application_cta_label = 'Postuler par téléphone'
    elif application_cta_url.startswith('#'):
        application_cta_label = 'Voir les modalités de candidature'
    else:
        application_cta_label = 'Postuler'
    application_cta_external = application_cta_url.startswith('http')

    meta_parts = [offer.title]
    if offer.company_name:
        meta_parts.append(f'chez {offer.company_name}')
    if offer.location:
        meta_parts.append(f'à {offer.location}')
    meta_description = ' '.join(meta_parts) + '.'
    if offer.employment_type:
        meta_description += f' {offer.employment_type}.'
    if applications_open:
        meta_description += ' Consultez les modalités de candidature sur Faso Job.'
    else:
        meta_description += ' Les candidatures sont fermées.'

    context = {
        'offer': offer,
        'similar_offers': similar_offers,
        'days_until_deadline': days_until_deadline,
        'days_since_deadline': days_since_deadline,
        'deadline_urgency': deadline_urgency,
        'applications_open': applications_open,
        'application_cta_url': application_cta_url,
        'application_cta_label': application_cta_label,
        'application_cta_is_whatsapp': offer.application_action_is_whatsapp,
        'application_cta_external': application_cta_external,
        'meta_description': meta_description,
        'active_nav': 'catalogue',
        'title': offer.title,
    }
    return render(request, 'refonte/offer_detail.html', context)


def offer_submission_view(request):
    if request.method == 'POST':
        form = OfferSubmissionForm(request.POST)
        if form.is_valid():
            submission = form.save()
            _screen_submission(submission)
            _notify(
                'notify_quarantined_submission',
                submission,
                only_if_quarantined=True,
            )
            _notify('notify_new_submission', submission)
            messages.success(
                request,
                'Votre proposition a bien été reçue. Elle est en attente de '
                'vérification et ne sera pas publiée automatiquement.',
            )
            return redirect('submit_offer')
    else:
        form = OfferSubmissionForm()

    return render(
        request,
        'refonte/submit_offer.html',
        {
            'form': form,
            'title': 'Proposer une annonce — Faso Job',
            'meta_description': (
                'Proposez une offre d’emploi, un stage ou une mission au Burkina Faso. '
                'Faso Job examine chaque annonce et sa source avant publication.'
            ),
            'active_nav': 'submit',
        },
    )


def report_fraud_view(request, slug=None):
    offer = None
    if slug:
        offer = get_object_or_404(
            Offer.objects.public(timezone.localtime()),
            slug=slug,
        )

    initial = {}
    if offer is not None:
        channel = OfferReport.CHANNEL_FASOJOB
        if offer.application_method == 'whatsapp':
            channel = OfferReport.CHANNEL_WHATSAPP
        elif offer.application_method == 'online':
            channel = OfferReport.CHANNEL_WEBSITE
        elif offer.application_method in ('physical', 'other'):
            channel = OfferReport.CHANNEL_IN_PERSON
        initial = {
            'suspect_title': offer.title,
            'suspect_organization': offer.company_name,
            'suspect_phone': offer.application_phone or offer.whatsapp_number,
            'suspect_channel': channel,
            'suspect_url': offer.application_url,
            'location_mentioned': offer.location,
        }

    if request.method == 'POST':
        form = OfferReportForm(request.POST, request.FILES, offer=offer)
        if form.is_valid():
            report = form.save(commit=False)
            report.offer = offer
            report.save()
            _notify('notify_new_report', report)
            target = (
                reverse('report_offer', args=[offer.slug])
                if offer is not None
                else reverse('report_fraud')
            )
            return redirect(f'{target}?recu=1')
    else:
        form = OfferReportForm(offer=offer, initial=initial)

    return render(
        request,
        'refonte/report_fraud.html',
        {
            'form': form,
            'offer': offer,
            'received': request.GET.get('recu') == '1',
            'title': 'Signaler une arnaque — Faso Job',
            'meta_description': (
                'Signalez une offre frauduleuse, une demande de frais ou une '
                'usurpation d’identité au Burkina Faso. Chaque signalement est '
                'examiné par l’équipe Faso Job.'
            ),
            'active_nav': 'report',
        },
    )


@staff_member_required
def report_evidence_view(request, pk):
    report = get_object_or_404(OfferReport, pk=pk)
    if not report.evidence:
        raise Http404('Aucune preuve jointe à ce signalement.')
    filename = Path(report.evidence.name).name
    return FileResponse(
        report.evidence.open('rb'),
        as_attachment=True,
        filename=filename,
    )
