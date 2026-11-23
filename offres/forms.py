from django import forms

from .models import OfferReport, OfferSubmission


class OfferSubmissionForm(forms.ModelForm):
    SECTION_DEFINITIONS = (
        (
            'L’opportunité',
            'Le poste, l’employeur et les conditions générales.',
            (
                'title',
                'company_name',
                'employer_kind',
                'location',
                'employment_type',
                'deadline',
                'deadline_time',
                'experience_required',
                'schedule',
            ),
        ),
        (
            'Description et rémunération',
            'Ce que les candidats doivent savoir avant de postuler.',
            (
                'details',
                'salary_min',
                'salary_max',
                'salary_currency',
                'salary_note',
            ),
        ),
        (
            'Source et candidature',
            'D’où vient l’annonce et comment postuler.',
            (
                'source_name',
                'source_url',
                'application_method',
                'application_url',
                'application_email',
                'application_phone',
                'whatsapp_number',
                'application_instructions',
                'required_documents',
            ),
        ),
        (
            'Votre contact',
            'Ces coordonnées restent internes à l’équipe de vérification.',
            ('declarant_role', 'contact_email', 'contact_phone'),
        ),
        (
            'Charte éthique',
            'Une dernière vérification avant l’envoi.',
            ('ethics_commitment',),
        ),
    )

    ethics_commitment = forms.BooleanField(
        label=(
            'J’atteste que cette opportunité est réelle et qu’elle n’exige aucun '
            'frais de dossier, caution ou paiement Mobile Money.'
        ),
        required=True,
        error_messages={
            'required': (
                'Vous devez accepter la charte éthique pour envoyer la proposition.'
            ),
        },
    )

    class Meta:
        model = OfferSubmission
        fields = (
            'title',
            'company_name',
            'employer_kind',
            'location',
            'employment_type',
            'salary_min',
            'salary_max',
            'salary_currency',
            'salary_note',
            'deadline',
            'deadline_time',
            'experience_required',
            'schedule',
            'details',
            'source_name',
            'source_url',
            'application_method',
            'application_url',
            'application_email',
            'application_phone',
            'whatsapp_number',
            'application_instructions',
            'required_documents',
            'contact_email',
            'contact_phone',
            'declarant_role',
            'ethics_commitment',
        )
        widgets = {
            'salary_min': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'salary_max': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'deadline': forms.DateInput(attrs={'type': 'date'}),
            'deadline_time': forms.TimeInput(attrs={'type': 'time'}),
            'details': forms.Textarea(attrs={'rows': 6}),
            'application_instructions': forms.Textarea(attrs={'rows': 3}),
            'required_documents': forms.Textarea(attrs={'rows': 3}),
        }

    @property
    def sections(self):
        return tuple(
            (title, tuple(self[name] for name in field_names))
            for title, _description, field_names in self.SECTION_DEFINITIONS
        )

    @property
    def numbered_sections(self):
        return tuple(
            {
                'number': index,
                'title': title,
                'description': description,
                'fields': tuple(self[name] for name in field_names),
            }
            for index, (title, description, field_names) in enumerate(
                self.SECTION_DEFINITIONS,
                start=1,
            )
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].label = 'Intitulé du poste'
        self.fields['title'].help_text = (
            'Reprenez l’intitulé exact publié par le recruteur.'
        )
        self.fields['company_name'].label = 'Nom de l’entreprise / recruteur'
        self.fields['company_name'].help_text = (
            'Le nom qui sera affiché sur l’offre.'
        )
        self.fields['employer_kind'].label = 'Type d’employeur'
        self.fields['location'].label = 'Ville ou zone'
        self.fields['location'].help_text = (
            'Ville, commune ou zone concernée par l’offre.'
        )
        self.fields['employment_type'].label = 'Type d’opportunité'
        self.fields['employment_type'].help_text = (
            'Exemple : CDI, CDD, stage, mission.'
        )
        self.fields['salary_min'].label = 'Rémunération minimale (facultative)'
        self.fields['salary_max'].label = 'Rémunération maximale (facultative)'
        self.fields['salary_currency'].label = 'Devise (facultative)'
        self.fields['salary_note'].label = 'Précision sur le salaire (facultative)'
        self.fields['salary_note'].help_text = (
            'Laissez vide si le montant n’est pas communiqué.'
        )
        self.fields['deadline'].label = 'Date limite (facultative)'
        self.fields['deadline'].help_text = (
            'L’offre sera signalée comme expirée après cette date.'
        )
        self.fields['deadline_time'].label = 'Heure limite (facultative)'
        self.fields['experience_required'].label = 'Expérience demandée (facultative)'
        self.fields['schedule'].label = 'Horaires (facultatifs)'
        self.fields['details'].label = 'Description du poste'
        self.fields['details'].help_text = (
            'Décrivez les missions, le profil recherché et les conditions de travail.'
        )
        self.fields['source_name'].label = 'Source de l’annonce (facultative)'
        self.fields['source_name'].help_text = (
            'Exemple : page Facebook de l’entreprise, WhatsApp, presse locale.'
        )
        self.fields['source_url'].label = 'Lien vers la source (facultatif)'
        self.fields['application_method'].label = 'Mode principal de candidature'
        self.fields['application_method'].help_text = (
            'Renseignez ensuite le canal correspondant.'
        )
        self.fields['application_url'].label = 'Lien de candidature (facultatif)'
        self.fields['application_email'].label = 'E-mail de candidature (facultatif)'
        self.fields['application_phone'].label = 'Téléphone de candidature (facultatif)'
        self.fields['whatsapp_number'].label = 'Numéro WhatsApp (facultatif)'
        self.fields['application_instructions'].label = 'Autres modalités (facultatif)'
        self.fields['required_documents'].label = 'Dossier à fournir (facultatif)'
        self.fields['contact_email'].label = 'Votre e-mail de contact'
        self.fields['contact_phone'].label = 'Votre téléphone de contact'
        self.fields['declarant_role'].label = 'Vous proposez cette offre en tant que'
        self.fields['ethics_commitment'].label = (
            'J’atteste que cette opportunité est réelle et qu’elle n’exige aucun '
            'frais de dossier, caution ou paiement Mobile Money.'
        )

        optional_fields = (
            'salary_min',
            'salary_max',
            'salary_currency',
            'salary_note',
            'deadline',
            'deadline_time',
            'experience_required',
            'schedule',
            'source_url',
            'source_name',
            'application_url',
            'application_email',
            'application_phone',
            'whatsapp_number',
            'application_instructions',
            'required_documents',
            'contact_email',
            'contact_phone',
        )
        for field_name in optional_fields:
            self.fields[field_name].required = False

        required_fields = ('location', 'employment_type', 'application_method')
        for field_name in required_fields:
            self.fields[field_name].required = True

        self.fields['location'].error_messages['required'] = (
            'Indiquez la ville ou la zone de l’offre.'
        )
        self.fields['employment_type'].error_messages['required'] = (
            'Précisez le type d’opportunité.'
        )
        self.fields['application_method'].error_messages['required'] = (
            'Choisissez le mode principal de candidature.'
        )

        self.fields['contact_email'].help_text = (
            'E-mail ou téléphone : au moins un des deux est nécessaire pour vous joindre.'
        )
        self.fields['contact_phone'].help_text = (
            'Usage interne uniquement. Ces coordonnées ne seront pas publiées.'
        )

        self.fields['salary_currency'].widget = forms.Select(
            choices=(('', 'Devise à préciser'), ('FCFA', 'FCFA'), ('EUR', 'EUR'), ('USD', 'USD')),
        )
        self.fields['employer_kind'].widget = forms.RadioSelect(
            choices=self.fields['employer_kind'].choices,
        )
        self.fields['declarant_role'].widget = forms.RadioSelect(
            choices=self.fields['declarant_role'].choices,
        )
        self.fields['title'].widget.attrs['placeholder'] = 'Ex. assistant comptable'
        self.fields['company_name'].widget.attrs['placeholder'] = 'Nom public'
        self.fields['location'].widget.attrs['placeholder'] = 'Ex. Bobo-Dioulasso'
        self.fields['employment_type'].widget.attrs['placeholder'] = 'Emploi, stage, mission…'
        self.fields['salary_note'].widget.attrs['placeholder'] = 'Montant ou à discuter'
        self.fields['source_url'].widget.attrs['placeholder'] = 'https://…'
        self.fields['source_name'].widget.attrs['placeholder'] = 'Ex. Facebook, WhatsApp, site de l’entreprise…'
        self.fields['application_url'].widget.attrs['placeholder'] = 'https://…'
        self.fields['application_email'].widget.attrs['placeholder'] = 'recrutement@exemple.bf'
        self.fields['application_phone'].widget.attrs['placeholder'] = '+226 70 00 00 00'
        self.fields['whatsapp_number'].widget.attrs['placeholder'] = '+226 70 00 00 00'
        self.fields['contact_email'].widget.attrs['placeholder'] = 'vous@exemple.bf'
        self.fields['contact_phone'].widget.attrs['placeholder'] = '+226 70 00 00 00'
        self.fields['required_documents'].widget.attrs['placeholder'] = 'Ex. CV, lettre de motivation, copie du diplôme…'
        self.fields['details'].required = True

        self.fields['company_name'].widget.attrs['autocomplete'] = 'organization'
        self.fields['location'].widget.attrs['autocomplete'] = 'address-level2'
        self.fields['contact_email'].widget.attrs['autocomplete'] = 'email'
        self.fields['contact_phone'].widget.attrs['autocomplete'] = 'tel'
        self.fields['application_email'].widget.attrs['autocomplete'] = 'email'
        self.fields['application_phone'].widget.attrs['autocomplete'] = 'tel'
        self.fields['whatsapp_number'].widget.attrs['autocomplete'] = 'tel'
        self.fields['source_url'].widget.attrs['autocomplete'] = 'url'
        self.fields['application_url'].widget.attrs['autocomplete'] = 'url'

        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                continue
            if isinstance(widget, forms.RadioSelect):
                continue
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'fj-select')
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault('class', 'fj-textarea')
            else:
                widget.attrs.setdefault('class', 'fj-input')

    def clean(self):
        cleaned_data = super().clean()
        salary_min = cleaned_data.get('salary_min')
        salary_max = cleaned_data.get('salary_max')
        if salary_min is not None and salary_max is not None and salary_min > salary_max:
            self.add_error(
                'salary_max',
                'La rémunération maximale doit être supérieure ou égale au minimum.',
            )

        if not cleaned_data.get('contact_email') and not cleaned_data.get('contact_phone'):
            self.add_error(
                'contact_phone',
                'Indiquez un e-mail ou un téléphone pour que nous puissions vérifier l’annonce.',
            )

        method = cleaned_data.get('application_method')
        channel_requirements = {
            'whatsapp': ('whatsapp_number', 'Indiquez le numéro WhatsApp à utiliser.'),
            'email': ('application_email', 'Indiquez l’adresse e-mail de candidature.'),
            'phone': ('application_phone', 'Indiquez le téléphone de candidature.'),
            'online': ('application_url', 'Indiquez le lien de candidature.'),
            'physical': (
                'application_instructions',
                'Précisez l’adresse ou les modalités du dépôt physique.',
            ),
            'other': (
                'application_instructions',
                'Précisez les modalités de candidature.',
            ),
        }
        requirement = channel_requirements.get(method)
        if requirement:
            field_name, message = requirement
            if not cleaned_data.get(field_name):
                self.add_error(field_name, message)

        return cleaned_data



class OfferReportForm(forms.ModelForm):
    SECTION_DEFINITIONS = (
        (
            'Le motif principal',
            'Sélectionnez le comportement qui correspond le mieux à la situation.',
            ('reason',),
        ),
        (
            'L’annonce ou la personne mise en cause',
            'Donnez les éléments que vous connaissez. Au moins un identifiant est nécessaire.',
            (
                'suspect_title',
                'suspect_organization',
                'suspect_phone',
                'suspect_channel',
                'suspect_url',
                'amount_requested',
                'location_mentioned',
                'details',
            ),
        ),
        (
            'Preuve et suivi',
            'Une capture d’écran aide notre équipe. Vos coordonnées restent privées.',
            ('evidence', 'reporter_name', 'reporter_email', 'reporter_phone'),
        ),
    )

    reason = forms.ChoiceField(
        label='Motif principal du signalement',
        choices=OfferReport.REASON_CHOICES,
        widget=forms.RadioSelect,
        error_messages={'required': 'Choisissez le motif principal de votre signalement.'},
    )
    details = forms.CharField(
        label='Décrivez précisément les faits',
        min_length=30,
        widget=forms.Textarea(attrs={'rows': 7}),
        help_text=(
            'Expliquez ce qui s’est passé : le message reçu, le montant demandé, '
            'le prétexte invoqué et les coordonnées utilisées.'
        ),
        error_messages={
            'required': 'Décrivez les faits pour permettre leur vérification.',
            'min_length': 'Ajoutez quelques précisions (30 caractères minimum).',
        },
    )
    suspect_channel = forms.ChoiceField(
        label='Canal de provenance',
        choices=(('', 'Sélectionner le canal'),) + tuple(OfferReport.CHANNEL_CHOICES),
        error_messages={'required': 'Indiquez où l’annonce ou le contact a été trouvé.'},
    )
    evidence = forms.FileField(
        label='Capture d’écran, reçu ou message',
        required=False,
        widget=forms.ClearableFileInput(
            attrs={'accept': '.png,.jpg,.jpeg,.webp,.pdf'}
        ),
        help_text='Formats acceptés : PNG, JPG, WEBP ou PDF. 5 Mo maximum.',
    )

    class Meta:
        model = OfferReport
        fields = (
            'reason',
            'suspect_title',
            'suspect_organization',
            'suspect_phone',
            'suspect_channel',
            'suspect_url',
            'amount_requested',
            'location_mentioned',
            'details',
            'evidence',
            'reporter_name',
            'reporter_email',
            'reporter_phone',
        )
        widgets = {
            'amount_requested': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }

    def __init__(self, *args, offer=None, **kwargs):
        self.offer = offer
        super().__init__(*args, **kwargs)
        if offer is not None:
            self.instance.offer = offer

        self.fields['suspect_title'].label = 'Intitulé du poste suspect'
        self.fields['suspect_title'].help_text = 'Reprenez l’intitulé affiché dans l’annonce.'
        self.fields['suspect_organization'].label = 'Entreprise ou organisation mise en cause'
        self.fields['suspect_organization'].help_text = 'Nom affiché, même s’il semble inventé.'
        self.fields['suspect_phone'].label = 'Téléphone ou identifiant Mobile Money'
        self.fields['suspect_phone'].help_text = (
            'Numéro utilisé pour le contact ou le paiement demandé.'
        )
        self.fields['suspect_url'].label = 'Lien ou canal de provenance (facultatif)'
        self.fields['suspect_url'].help_text = (
            'Lien d’une publication, nom d’un groupe WhatsApp ou d’une page Facebook.'
        )
        self.fields['amount_requested'].label = 'Montant réclamé en FCFA (facultatif)'
        self.fields['location_mentioned'].label = 'Ville ou lieu évoqué (facultatif)'
        self.fields['reporter_name'].label = 'Votre nom (facultatif)'
        self.fields['reporter_email'].label = 'Votre e-mail de suivi (facultatif)'
        self.fields['reporter_phone'].label = 'Votre téléphone ou WhatsApp (facultatif)'
        self.fields['reporter_email'].help_text = (
            'Ces coordonnées ne sont jamais publiées. Laissez vide pour rester anonyme.'
        )
        self.fields['reporter_phone'].help_text = (
            'Utilisé uniquement si notre équipe a besoin d’un complément.'
        )

        self.fields['suspect_title'].widget.attrs['placeholder'] = 'Ex. assistant logistique'
        self.fields['suspect_organization'].widget.attrs['placeholder'] = 'Ex. nom affiché par le recruteur'
        self.fields['suspect_phone'].widget.attrs['placeholder'] = '+226 70 00 00 00'
        self.fields['suspect_url'].widget.attrs['placeholder'] = 'https://… ou nom du groupe'
        self.fields['location_mentioned'].widget.attrs['placeholder'] = 'Ex. Ouagadougou'
        self.fields['reporter_name'].widget.attrs['placeholder'] = 'Nom ou pseudonyme'
        self.fields['reporter_email'].widget.attrs['placeholder'] = 'vous@exemple.bf'
        self.fields['reporter_phone'].widget.attrs['placeholder'] = '+226 70 00 00 00'

        self.fields['reporter_email'].widget.attrs['autocomplete'] = 'email'
        self.fields['reporter_phone'].widget.attrs['autocomplete'] = 'tel'
        self.fields['reporter_name'].widget.attrs['autocomplete'] = 'name'

        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect)):
                continue
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'fj-select')
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault('class', 'fj-textarea')
            elif isinstance(widget, forms.FileInput):
                widget.attrs.setdefault('class', 'fj-file-input')
            else:
                widget.attrs.setdefault('class', 'fj-input')

    @property
    def numbered_sections(self):
        return tuple(
            {
                'number': index,
                'title': title,
                'description': description,
                'fields': tuple(self[name] for name in field_names),
            }
            for index, (title, description, field_names) in enumerate(
                self.SECTION_DEFINITIONS,
                start=1,
            )
        )
