from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser


def get_default_profile():
    return {
        "role": "Standard",
        "theme": "light",
        "preferences": {}
    }


class User(AbstractUser):
    username = models.CharField(
        max_length=150,
        unique=True,
        null=True,
        blank=True
    )

    profiles = models.JSONField(
        default=get_default_profile,
        null=True,
        blank=True
    )

    date_of_birth = models.DateField(
        null=True,
        blank=True
    )

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

    nationality = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

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

    phone = models.CharField(
        max_length=15,
        null=True,
        blank=True
    )

    permanent_address = models.TextField(
        null=True,
        blank=True
    )

    current_address = models.TextField(
        null=True,
        blank=True
    )

    emergency_contact_name = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    emergency_contact_number = models.CharField(
        max_length=15,
        null=True,
        blank=True
    )

    emergency_contact_relationship = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=10,
        choices=[
            ('Active', 'Active'),
            ('Inactive', 'Inactive'),
        ],
        default='Active',
        null=True,
        blank=True
    )

    email = models.EmailField(
        unique=True,
        null=True,
        blank=True
    )

    # OTP fields
    otp = models.CharField(
        max_length=6,
        null=True,
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

    
    otp_request_timestamps = models.JSONField(
        default=list,
        null=True,
        blank=True
    )


class Client(models.Model):
    first_name = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )
    
    last_name = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )
    
    address = models.TextField(
        null=True,
        blank=True
    )
    
    country = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )
    
    contact_no = models.CharField(
        max_length=15,
        null=True,
        blank=True
    )
    
    email_id = models.EmailField(
        unique=True,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=10,
        choices=[
            ('Active', 'Active'),
            ('Inactive', 'Inactive'),
        ],
        default='Active',
        null=True,
        blank=True
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
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        null=True,
        blank=True
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Project(models.Model):
    project_title = models.CharField(
        max_length=150,
        null=True,
        blank=True
    )

    project_type = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    date_of_completion = models.DateField(
        null=True,
        blank=True
    )

    project_status = models.CharField(
        max_length=30,
        choices=[
            ('Pending', 'Pending'),
            ('In Progress', 'In Progress'),
            ('Completed', 'Completed'),
            ('Cancelled', 'Cancelled'),
        ],
        default='Pending',
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=10,
        choices=[
            ('Active', 'Active'),
            ('Inactive', 'Inactive'),
        ],
        default='Active',
        null=True,
        blank=True
    )

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='projects'
    )

    assigned_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_projects'
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_projects'
    )

    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_projects'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        null=True,
        blank=True
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        null=True,
        blank=True
    )

    def __str__(self):
        return self.project_title if self.project_title else "Project"