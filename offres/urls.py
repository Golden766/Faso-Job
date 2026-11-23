from django.urls import path
from django.views.generic import RedirectView

from .dev_views import styleguide_view
from .twofactor_views import (
    two_factor_regenerate_recovery_codes,
    two_factor_settings_view,
    two_factor_verify_view,
)
from .views import (
    catalogue_view,
    favorites_view,
    home_view,
    method_view,
    offer_detail_view,
    offer_submission_view,
    report_evidence_view,
    report_fraud_view,
)

urlpatterns = [
    path('', home_view, name='home'),
    path('catalogue/', catalogue_view, name='catalogue'),
    path('favoris/', favorites_view, name='favorites'),
    path('comment-ca-marche/', method_view, name='method'),
    path('proposer-une-annonce/', offer_submission_view, name='submit_offer'),
    path(
        'proposer-une-offre/',
        RedirectView.as_view(pattern_name='submit_offer', permanent=True),
    ),
    path('signaler-une-arnaque/', report_fraud_view, name='report_fraud'),
    path('offre/<slug:slug>/', offer_detail_view, name='offer_detail'),
    path('offre/<slug:slug>/signaler/', report_fraud_view, name='report_offer'),
    path(
        'admin/signalements/<int:pk>/preuve/',
        report_evidence_view,
        name='report_evidence',
    ),
    path('styleguide/', styleguide_view, name='styleguide'),
    path('admin/securite/', two_factor_settings_view, name='two_factor_settings'),
    path(
        'admin/securite/verification/',
        two_factor_verify_view,
        name='two_factor_verify',
    ),
    path(
        'admin/securite/codes-de-secours/',
        two_factor_regenerate_recovery_codes,
        name='two_factor_recovery_codes',
    ),
]
