
from django.core.management.base import BaseCommand
from django.utils import timezone

from users.models import User


class Command(BaseCommand):
    help = "Delete expired OTPs from database"

    def handle(self, *args, **kwargs):
        expired_users = User.objects.filter(
            otp_expires_at__isnull=False,
            otp_expires_at__lte=timezone.now()
        )

        count = expired_users.update(
            otp='',
            otp_expires_at=None,
            is_otp_used=True
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'{count} expired OTP(s) cleared.'
            )
        )
