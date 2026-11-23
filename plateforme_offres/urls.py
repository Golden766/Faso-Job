from django.contrib import admin
from django.urls import include, path

from offres.admin_views import (
    activity_report_export,
    activity_report_view,
    admin_dashboard_view,
    backup_restore_view,
    backup_settings_view,
    expired_offers_view,
)
from offres.veille.admin_views import veille_dashboard_view

urlpatterns = [
    path('', include('offres.urls')),
    path('admin/', admin_dashboard_view, name='admin-dashboard'),
    path(
        'admin/offres-expirees/',
        expired_offers_view,
        name='admin-expired-offers',
    ),
    path(
        'admin/rapport-activite/',
        activity_report_view,
        name='admin-activity-report',
    ),
    path(
        'admin/rapport-activite/export.csv',
        activity_report_export,
        name='admin-activity-report-csv',
    ),
    path('admin/sauvegardes/', backup_settings_view, name='admin-backups'),
    path(
        'admin/sauvegardes/restaurer/<str:file_name>/',
        backup_restore_view,
        name='admin-backup-restore',
    ),
    path('admin/veille/', veille_dashboard_view, name='admin-veille'),
    path('admin/', admin.site.urls),
]
