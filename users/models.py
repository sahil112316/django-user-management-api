from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser

#Default Profile
def get_default_profile():
    return {
        "role": "Standard",
        "is_active": True,
        "is_default": True
    }

#Basemodel
class BaseModel(models.Model):

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_created')
    modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_modified')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        abstract = True

#UserModel
class User(AbstractUser, BaseModel):
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    profiles = models.JSONField(default=get_default_profile, null=True, blank=True)
    is_client = models.BooleanField(default=False, db_index=True)
    profile = models.ForeignKey('Profile', on_delete=models.PROTECT, null=True, blank=True, related_name='users')
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')], null=True, blank=True)
    nationality = models.CharField(max_length=100, null=True, blank=True)
    country = models.CharField(max_length=50, null=True, blank=True)
    image = models.ImageField(upload_to='profile_images/', null=True, blank=True)
    blood_group = models.CharField(max_length=3, choices=[('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'), ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O-')], null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    permanent_address = models.TextField(null=True, blank=True)
    current_address = models.TextField(null=True, blank=True)
    emergency_contact_name = models.CharField(max_length=100, null=True, blank=True)
    emergency_contact_number = models.CharField(max_length=15, null=True, blank=True)
    emergency_contact_relationship = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=10, choices=[('Active', 'Active'), ('Inactive', 'Inactive')], default='Active', null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    otp = models.CharField(max_length=6, null=True, blank=True, default='')
    is_otp_used = models.BooleanField(default=False)
    otp_expires_at = models.DateTimeField(null=True, blank=True)
    otp_request_timestamps = models.JSONField(default=list, null=True, blank=True)

#Client Model
class Client(BaseModel):
    first_name = models.CharField(max_length=50, null=True, blank=True)
    last_name = models.CharField(max_length=50, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    country = models.CharField(max_length=50, null=True, blank=True)
    contact_no = models.CharField(max_length=15, null=True, blank=True)
    email_id = models.EmailField(unique=True, null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=[('Active', 'Active'), ('Inactive', 'Inactive')],
        default='Active',
        null=True,
        blank=True
    )
 
    def __str__(self):
        return f"{self.first_name} {self.last_name}"


# Project Model
class Project(BaseModel):

    project_title = models.CharField(max_length=150, null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    project_type = models.CharField(max_length=100, null=True, blank=True)
    start_date = models.DateField(auto_now_add=True)
    date_of_completion = models.DateField(null=True, blank=True)
    project_status = models.CharField(max_length=30, choices=[('Pending', 'Pending'), ('In Progress', 'In Progress'), ('Completed', 'Completed'), ('Cancelled', 'Cancelled')], default='Pending', null=True, blank=True)
    status = models.CharField(max_length=10, choices=[('Active', 'Active'), ('Inactive', 'Inactive')], default='Active', null=True, blank=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True, related_name='projects')
    assigned_manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_projects')
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_projects')

    def __str__(self):
        return self.project_title if self.project_title else "Project"

# ProjectAttachment Model
class ProjectAttachment(models.Model):

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='attachments')
    attachment = models.FileField(upload_to='project_attachments/')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_project_attachments')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for {self.project}"

# Project Task Model
class ProjectTask(BaseModel):

    TASK_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]

    task_title = models.CharField(max_length=255)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    developers = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='assigned_project_tasks')
    team_leader = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='led_project_tasks', blank=True)
    start_date = models.DateField(auto_now_add=True)
    completion_date = models.DateField(null=True, blank=True)
    deadline_date = models.DateField()
    task_status = models.CharField(max_length=20, choices=TASK_STATUS_CHOICES, default='Pending')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['project', 'task_title'], name='unique_task_title_per_project')
        ]

    def __str__(self):
        return self.task_title


# Task Comment Model
class TaskComment(BaseModel):

    task = models.ForeignKey(ProjectTask, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='task_comments')
    comment = models.TextField()

    def __str__(self):
        return f"Comment on {self.task.task_title}"

# . Profile QuerySet
class ProfileQuerySet(models.QuerySet):

    def delete(self):
        default_profiles = self.filter(is_default=True)

        if default_profiles.exists():
            raise models.ProtectedError("Default profiles cannot be deleted.", list(default_profiles))

        return super().delete()

    def update(self, **kwargs):
        if self.filter(is_default=True).exists():
            raise models.ProtectedError("Default profiles cannot be updated.", list(self.filter(is_default=True)))

        return super().update(**kwargs)

#  Profile Model
class Profile(BaseModel):

    DEFAULT_PROFILES = [
        'Super Admin',
        'Admin',
        'Manager',
        'Team Leader',
        'Developer',
        'Human Resource',
    ]

    name = models.CharField(max_length=100, unique=True)
    profile_data = models.JSONField(default=get_default_profile, blank=True)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=[('Active', 'Active'), ('Inactive', 'Inactive')], default='Active')
    is_default = models.BooleanField(default=False)
    objects = ProfileQuerySet.as_manager()

    def save(self, *args, **kwargs):

        if self.pk:
            old_profile = Profile.objects.filter(pk=self.pk).first()

            if old_profile and old_profile.is_default:
                raise models.ProtectedError("Default profiles cannot be updated.", [old_profile])

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):

        if self.is_default:
            raise models.ProtectedError("Default profiles cannot be deleted.", [self])

        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.profile_data.get('role', self.name)}"