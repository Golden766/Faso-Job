from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission


class Command(BaseCommand):
    help = 'Crée les groupes éditoriaux et peut affecter un utilisateur existant.'

    def add_arguments(self, parser):
        parser.add_argument('--username')
        parser.add_argument('--role', choices=['editor', 'moderator'])

    def handle(self, *args, **options):
        editor_group, _ = Group.objects.get_or_create(name='Éditeur')
        moderator_group, _ = Group.objects.get_or_create(name='Modérateur')

        editor_permissions = {
            'offres': [
                'view_source', 'add_source', 'change_source',
                'view_category', 'add_category', 'change_category',
                'view_offer', 'add_offer', 'change_offer',
                'view_offersubmission', 'view_offerreport',
                'view_blacklistedcontact', 'view_platformsettings',
            ],
        }
        moderator_permissions = {
            'offres': [
                'view_source', 'change_source',
                'view_category',
                'view_offer', 'change_offer',
                'view_offersubmission', 'change_offersubmission',
                'view_offerreport', 'change_offerreport',
                'view_blacklistedcontact', 'add_blacklistedcontact',
                'change_blacklistedcontact',
                'view_platformsettings', 'change_platformsettings',
            ],
        }

        editor_group.permissions.set(self._get_permissions(editor_permissions))
        moderator_group.permissions.set(self._get_permissions(moderator_permissions))

        username = options.get('username')
        role = options.get('role')
        if username or role:
            if not username or not role:
                raise CommandError('Les options --username et --role doivent être utilisées ensemble.')

            user_model = get_user_model()
            try:
                user = user_model.objects.get(username=username)
            except user_model.DoesNotExist:
                raise CommandError(f"Utilisateur « {username} » introuvable.")

            group = editor_group if role == 'editor' else moderator_group
            user.groups.add(group)
            if not user.is_staff:
                user.is_staff = True
                user.save(update_fields=['is_staff'])
            self.stdout.write(self.style.SUCCESS(f"Le rôle « {group.name} » a été attribué à {username}."))

        self.stdout.write(self.style.SUCCESS('Groupes éditoriaux créés avec des permissions distinctes.'))

    @staticmethod
    def _get_permissions(permission_map):
        permissions = Permission.objects.none()
        for app_label, codenames in permission_map.items():
            permissions |= Permission.objects.filter(
                content_type__app_label=app_label,
                codename__in=codenames,
            )
        return permissions
