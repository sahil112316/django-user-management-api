
from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = 'users'

    def ready(self):
        from django.db.models.signals import post_migrate

        def create_default_profiles(sender, **kwargs):
            if sender.name != 'users':
                return

            from .models import Profile

            default_profiles = [
                ('Super Admin', 'Super Administrator profile'),
                ('Admin', 'Administrator profile'),
                ('Manager', 'Manager profile'),
                ('Team Leader', 'Team Leader profile'),
                ('Developer', 'Developer profile'),
                ('Human Resource', 'Human Resources profile'),
            ]

            for name, description in default_profiles:
                Profile.objects.get_or_create(
                    name=name,
                    defaults={
                        'profile_data': {'role': name},
                        'description': description,
                        'status': 'Active',
                        'is_default': True,
                    }
                )

        post_migrate.connect(
            create_default_profiles,
            sender=self,
            dispatch_uid='users_create_default_profiles',
            weak=False,
        )
