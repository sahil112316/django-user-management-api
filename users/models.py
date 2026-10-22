from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):

    profiles = models.CharField(
        max_length=20,
        choices=[
            ('Administrator', 'Administrator'),
            ('Standard', 'Standard'),
            ('Developer', 'Developer'),
            ('Client', 'Client'),
            ('Human Resource', 'Human Resource'),
        ]
    )

    date_of_birth = models.DateField(null=True, blank=True)

    gender = models.CharField(
        max_length=10,
        choices=[
            ('Male', 'Male'),
            ('Female', 'Female'),
            ('Other', 'Other'),
        ],
        null=True,
        blank=True
    )

    nationality = models.CharField(max_length=100, blank=True)

    image = models.ImageField(
        upload_to='profile_images/',
        null=True,
        blank=True
    )

    blood_group = models.CharField(
        max_length=3,
        choices=[
            ('A+', 'A+'),
            ('A-', 'A-'),
            ('B+', 'B+'),
            ('B-', 'B-'),
            ('AB+', 'AB+'),
            ('AB-', 'AB-'),
            ('O+', 'O+'),
            ('O-', 'O-'),
        ],
        null=True,
        blank=True
    )

    phone = models.CharField(max_length=15, blank=True)

    permanent_address = models.TextField(blank=True)

    current_address = models.TextField(blank=True)

    emergency_contact_name = models.CharField(
        max_length=100,
        blank=True
    )

    emergency_contact_number = models.CharField(
        max_length=15,
        blank=True
    )

    emergency_contact_relationship = models.CharField(
        max_length=50,
        blank=True
    )

    status = models.CharField(
        max_length=10,
        choices=[
            ('Active', 'Active'),
            ('Inactive', 'Inactive'),
        ],
        default='Active'
    )

    email = models.EmailField(unique=True)

    # OTP fields
    otp = models.CharField(
        max_length=6,
        blank=True,
        default=''
    )

    is_otp_used = models.BooleanField(
        default=False
    )

    otp_expires_at = models.DateTimeField(
        null=True,
        blank=True
    )


class Client(models.Model):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    address = models.TextField()
    country = models.CharField(max_length=50)
    contact_no = models.CharField(max_length=15)
    email_id = models.EmailField(unique=True)

    status = models.CharField(
        max_length=10,
        choices=[
            ('Active', 'Active'),
            ('Inactive', 'Inactive'),
        ],
        default='Active'
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_clients'
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_clients'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"