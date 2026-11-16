
from datetime import timedelta
from django.core.mail import send_mail
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
from django.utils.dateparse import parse_date
import json

from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    User, Client, Project, Profile, ProjectAttachment,
    ProjectTask, TaskComment
)

#1. Project Manager Assignment Field

class FlexibleManagerField(serializers.RelatedField):
    queryset = User.objects.all()

    def to_representation(self, value):
        if value:
            return ManagerSerializer(value).data
        return None

    def to_internal_value(self, data):
        if isinstance(data, bool):
            raise serializers.ValidationError(
                'Invalid input for assigned_manager.'
            )

        if isinstance(data, int):
            try:
                user = User.objects.select_related('profile').get(pk=data)
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    'User with this ID does not exist.'
                )

        elif isinstance(data, str):
            matched_users = list(
                User.objects.select_related('profile').filter(
                    Q(username__iexact=data) |
                    Q(email__iexact=data)
                )[:2]
            )

            if not matched_users:
                raise serializers.ValidationError(
                    'User with this username or email does not exist.'
                )

            if len(matched_users) > 1:
                raise serializers.ValidationError(
                    'Multiple users found. Please provide a unique username or email.'
                )

            user = matched_users[0]

        else:
            raise serializers.ValidationError(
                'Invalid input for assigned_manager.'
            )

        if user.status != 'Active':
            raise serializers.ValidationError(
                'Inactive users cannot be assigned as project manager.'
            )

        profile = getattr(user, 'profile', None)

        if not profile or profile.name.strip().lower() != 'manager':
            raise serializers.ValidationError(
                'Only users with Manager role can be assigned as project manager.'
            )

        return user


# 2.  User Login Serializer

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, data):
        email = data['email']
        password = data['password']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                'Invalid email or password.'
            )

        if user.status != 'Active':
            raise serializers.ValidationError(
                'User account is inactive.'
            )

        if not user.check_password(password):
            raise serializers.ValidationError(
                'Invalid email or password.'
            )

        refresh = RefreshToken.for_user(user)
        return {
            'message': 'Login successful.',
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }


# 3. Send OTP Serializer

class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate(self, data):
        email = data['email']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                'User with this email does not exist.'
            )

        now = timezone.now()
        twelve_hours_ago = now - timedelta(hours=12)

        if user.otp_request_timestamps is None:
            user.otp_request_timestamps = []

        valid_timestamps = []
        for t_str in user.otp_request_timestamps:
            try:
                t_dt = timezone.datetime.fromisoformat(t_str)
                if timezone.is_naive(t_dt):
                    t_dt = timezone.make_aware(t_dt)
                if t_dt > twelve_hours_ago:
                    valid_timestamps.append(t_str)
            except (ValueError, TypeError):
                pass

        if len(valid_timestamps) >= 3:
            raise serializers.ValidationError(
                'You have exceeded the maximum number of OTP requests. '
                'Please try again after 12 hours.'
            )

        valid_timestamps.append(now.isoformat())
        user.otp_request_timestamps = valid_timestamps
        user.save(update_fields=['otp_request_timestamps'])

        if user.status != 'Active':
            raise serializers.ValidationError({
                'active_user_not_found': 'Active user not found.'
            })

        data['user'] = user
        return data


# 4. Verify OTP Serializer

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(max_length=6, required=True)

    def validate(self, attrs):
        email = attrs['email']
        otp = attrs['otp']

        try:
            user = User.objects.get(
                email=email,
                status='Active'
            )
        except User.DoesNotExist:
            raise serializers.ValidationError({
                'active_user_not_found': 'Active user not found.'
            })

        if (
            user.otp != otp
            or getattr(user, 'is_otp_used', False) is True
            or user.otp_expires_at is None
            or user.otp_expires_at <= timezone.now()
        ):
            raise serializers.ValidationError({
                'invalid_otp': 'Invalid or expired OTP.'
            })

        attrs['user'] = user
        return attrs

# 5. Reset Password Serializer

class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(max_length=6, required=True)
    new_password = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        email = attrs['email']
        otp = attrs['otp']

        try:
            user = User.objects.get(
                email=email,
                status='Active'
            )
        except User.DoesNotExist:
            raise serializers.ValidationError({
                'active_user_not_found': 'Active user not found.'
            })

        if (
            user.otp != otp
            or getattr(user, 'is_otp_used', False) is True
            or user.otp_expires_at is None
            or user.otp_expires_at <= timezone.now()
        ):
            raise serializers.ValidationError({
                'invalid_otp': 'Invalid or expired password reset OTP.'
            })

        attrs['user'] = user
        return attrs



#6. User List Query Parameter Validation

class UserListQuerySerializer(serializers.Serializer):

    status = serializers.CharField(
        required=False,
        default='Active'
    )

    date_from = serializers.CharField(required=False, allow_blank=True)
    date_to = serializers.CharField(required=False, allow_blank=True)

    def validate_status(self, value):
        value = value.strip()

        if value.lower() not in ['active', 'inactive']:
            raise serializers.ValidationError(
                'Status must be active or inactive.'
            )

        return value

    def validate_date_from(self, value):
        if value:
            from django.utils.dateparse import parse_date

            if parse_date(value) is None:
                raise serializers.ValidationError(
                    'Invalid date_from. Use YYYY-MM-DD.'
                )

        return value

    def validate_date_to(self, value):
        if value:
            from django.utils.dateparse import parse_date

            if parse_date(value) is None:
                raise serializers.ValidationError(
                    'Invalid date_to. Use YYYY-MM-DD.'
                )

        return value

#7. User Audit Serializer

class UserAuditSerializer(serializers.ModelSerializer):

    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'first_name',
            'last_name',
            'profile'
        ]

    def get_profile(self, obj):
        if not obj.profile:
            return None

        return {
            'id': obj.profile.id,
            'role': obj.profile.name,
            'is_default': obj.profile.is_default
        }


#8. User Details Serializer

class UserSerializer(serializers.ModelSerializer):

    profiles = serializers.SerializerMethodField()
    created_by = UserAuditSerializer(read_only=True)
    modified_by = UserAuditSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 'email',
            'profiles',
            'date_of_birth', 'gender', 'nationality',
            'image', 'blood_group', 'phone', 'permanent_address',
            'current_address', 'emergency_contact_name',
            'emergency_contact_number', 'emergency_contact_relationship',
            'status',
            'created_by', 'modified_by',
            'created_at', 'updated_at'
        ]

        read_only_fields = [
            'created_by', 'modified_by', 'created_at', 'updated_at'
        ]

    def get_profiles(self, obj):

        profile = obj.profile

        if not profile:
            return None

        return {
            'id': profile.id,
            'role': profile.name,
            'is_active': profile.status == 'Active',
            'is_default': profile.is_default
        }

#9. User Create Serializer

class UserCreateSerializer(serializers.ModelSerializer):

    profiles = serializers.PrimaryKeyRelatedField(
        queryset=Profile.objects.filter(status='Active'),
        source='profile',
        write_only=True,
        required=True
    )

    profiles_details = serializers.SerializerMethodField(read_only=True)
    email = serializers.EmailField(required=True)

    created_by = UserAuditSerializer(read_only=True)
    modified_by = UserAuditSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'email', 'username',
            'profiles', 'profiles_details',
            'date_of_birth', 'gender', 'nationality',
            'image', 'blood_group', 'phone', 'permanent_address',
            'current_address', 'emergency_contact_name',
            'emergency_contact_number',
            'emergency_contact_relationship', 'status',
            'created_by', 'modified_by',
            'created_at', 'updated_at'
        ]

        read_only_fields = [
            'created_by', 'modified_by', 'created_at', 'updated_at'
        ]


    def validate_email(self, value):
     if User.objects.filter(email__iexact=value).exists():
        raise serializers.ValidationError(
            "A user with this email already exists."
        )

     return value

    def get_profiles_details(self, obj):
        profile = obj.profile

        if not profile:
            return None

        return {
            'id': profile.id,
            'role': profile.name,
            'is_active': profile.status == 'Active',
            'is_default': profile.is_default
        }

    def create(self, validated_data):
        profile = validated_data.pop('profile')
        email = validated_data.get('email')

        validated_data['profile'] = profile
        validated_data['profiles'] = profile.profile_data
        validated_data['status'] = validated_data.get('status') or 'Active'

        email_prefix = email.split('@')[0] if email else 'user'
        default_password = f'{email_prefix}@123'

        user = User(**validated_data)
        user.set_password(default_password)
        user.save()

        try:
            send_mail(
                subject='Welcome to Our Platform',
                message=(
                    'Hello,\n\n'
                    'Welcome! Your account has been created successfully.\n'
                    f'Your default password is: {default_password}\n\n'
                    'Thank you for joining us.'
                ),
                from_email=None,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception:
            pass

        return user

#10. User Update Serializer

class UserUpdateSerializer(serializers.ModelSerializer):

    profiles = serializers.PrimaryKeyRelatedField(
        source='profile',
        queryset=Profile.objects.filter(status='Active'),
        required=False,
        allow_null=True
    )

    created_by = UserAuditSerializer(read_only=True)
    modified_by = UserAuditSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'email', 'username',
            'profiles',
            'date_of_birth', 'gender', 'nationality',
            'image', 'blood_group', 'phone', 'permanent_address',
            'current_address', 'emergency_contact_name',
            'emergency_contact_number', 'emergency_contact_relationship',
            'status',
            'created_by', 'modified_by',
            'created_at', 'updated_at'
        ]

        read_only_fields = [
            'created_by', 'modified_by', 'created_at', 'updated_at'
        ]

    def update(self, instance, validated_data):

        profile = validated_data.get('profile', serializers.empty)

        if profile is not serializers.empty:
            if profile is not None:
                validated_data['profiles'] = profile.profile_data
            else:
                validated_data['profiles'] = {
                    'role': 'Standard'
                }

        return super().update(instance, validated_data)


#11. Client List Query Parameter Validation


class ClientListQuerySerializer(serializers.Serializer):

    status = serializers.CharField(
        required=False,
        default='Active'
    )

    date_from = serializers.CharField(
        required=False,
        allow_blank=True
    )

    date_to = serializers.CharField(
        required=False,
        allow_blank=True
    )

    def validate_status(self, value):
        value = value.strip()

        if value.lower() not in ['active', 'inactive']:
            raise serializers.ValidationError(
                'Status must be active or inactive.'
            )

        return value

    def validate_date_from(self, value):
        if value and parse_date(value) is None:
            raise serializers.ValidationError(
                'Invalid date_from. Use YYYY-MM-DD.'
            )

        return value

    def validate_date_to(self, value):
        if value and parse_date(value) is None:
            raise serializers.ValidationError(
                'Invalid date_to. Use YYYY-MM-DD.'
            )

        return value




#12. Client Serializer

class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = '__all__'



#13. Project Client Details Serializer

class ProjectClientSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        source='email_id',
        read_only=True
    )

    class Meta:
        model = Client
        fields = ['id', 'first_name', 'last_name', 'email']

#14.Client Details Field

class ClientDetailsField(serializers.PrimaryKeyRelatedField):

    def to_representation(self, value):
        return ProjectClientSerializer(value).data


#15. Project User Details Serializer

class ProjectUserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='profile.name', read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'first_name',
            'last_name',
            'email',
            'role'
        ]


# 16. Project Attachment Serializer

class ProjectAttachmentSerializer(serializers.ModelSerializer):
    file = serializers.SerializerMethodField()

    uploaded_by = ProjectUserSerializer(
        read_only=True,
        allow_null=True
    )

    class Meta:
        model = ProjectAttachment
        fields = [
            'id', 'file', 'uploaded_by', 'uploaded_at'
        ]

    def get_file(self, obj):
        if obj.attachment:
            request = self.context.get('request')

            if request:
                return request.build_absolute_uri(obj.attachment.url)

            return obj.attachment.url

        return None

# 17. Send Project Creation Email Notification to Client

def send_client_project_email(project):

    client = project.client

    if not client or not client.email_id:
        return

    manager = project.assigned_manager

    if manager:
        manager_name = f"{manager.first_name} {manager.last_name}".strip()
        manager_email = manager.email or "Not available"
    else:
        manager_name = "Not assigned"
        manager_email = "Not available"

    subject = "New Project Created"

    message = (
        f"Hello {client.first_name or 'Client'},\n\n"
        f"A new project has been created for you.\n\n"
        f"Project Title: {project.project_title}\n"
        f"Project Status: {project.project_status}\n"
        f"Description: {project.description or 'Not provided'}\n\n"
        f"Assigned Manager: {manager_name}\n"
        f"Manager Email: {manager_email}\n\n"
        f"Thank you."
    )

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [client.email_id],
        fail_silently=True
    )


# 18. Send Project Assignment Email Notification to Manager

def send_manager_project_email(project):

    manager = project.assigned_manager

    if not manager or not manager.email:
        return

    client = project.client

    if client:
        client_name = (
            f"{client.first_name or ''} {client.last_name or ''}"
        ).strip()
        client_email = client.email_id or "Not available"
    else:
        client_name = "Not assigned"
        client_email = "Not available"

    subject = "New Project Assigned to You"

    message = (
        f"Hello {manager.first_name or manager.username},\n\n"
        f"A new project has been assigned to you.\n\n"
        f"Project Title: {project.project_title}\n"
        f"Project Status: {project.project_status}\n"
        f"Description: {project.description or 'Not provided'}\n\n"
        f"Client Name: {client_name}\n"
        f"Client Email: {client_email}\n\n"
        f"Thank you."
    )

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [manager.email],
        fail_silently=True
    )




#19. Project List Query Parameter Validation

class ProjectListQuerySerializer(serializers.Serializer):

    status = serializers.CharField(
        required=False,
        default='Active'
    )

    client_id = serializers.CharField(
        required=False,
        allow_blank=True
    )

    manager_id = serializers.CharField(
        required=False,
        allow_blank=True
    )

    date_from = serializers.CharField(
        required=False,
        allow_blank=True
    )

    date_to = serializers.CharField(
        required=False,
        allow_blank=True
    )

    created_from = serializers.CharField(
        required=False,
        allow_blank=True
    )

    created_to = serializers.CharField(
        required=False,
        allow_blank=True
    )

    def validate_status(self, value):
        value = value.strip()

        if value.lower() not in ['active', 'inactive']:
            raise serializers.ValidationError(
                'Status must be active or inactive.'
            )

        return value

    def validate_client_id(self, value):
        if value:
            if not value.isdigit() or int(value) <= 0:
                raise serializers.ValidationError(
                    'Invalid client_id.'
                )

            if not Client.objects.filter(id=int(value)).exists():
                raise serializers.ValidationError(
                    'Client does not exist.'
                )

        return value

    def validate_manager_id(self, value):
        if value:
            if not value.isdigit() or int(value) <= 0:
                raise serializers.ValidationError(
                    'Invalid manager_id.'
                )

            if not User.objects.filter(id=int(value)).exists():
                raise serializers.ValidationError(
                    'Manager does not exist.'
                )

        return value

    def validate_date_from(self, value):
        if value and parse_date(value) is None:
            raise serializers.ValidationError(
                'Invalid date_from. Use YYYY-MM-DD.'
            )

        return value

    def validate_date_to(self, value):
        if value and parse_date(value) is None:
            raise serializers.ValidationError(
                'Invalid date_to. Use YYYY-MM-DD.'
            )

        return value

    def validate_created_from(self, value):
        if value and parse_date(value) is None:
            raise serializers.ValidationError(
                'Invalid created_from. Use YYYY-MM-DD.'
            )

        return value

    def validate_created_to(self, value):
        if value and parse_date(value) is None:
            raise serializers.ValidationError(
                'Invalid created_to. Use YYYY-MM-DD.'
            )

        return value

#20. Project Task List Query Parameter Validation

class ProjectTaskListQuerySerializer(serializers.Serializer):

    project_id = serializers.CharField(required=False, allow_blank=True)
    developer_id = serializers.CharField(required=False, allow_blank=True)

    def validate_project_id(self, value):
        if value and (not value.isdigit() or int(value) <= 0):
            raise serializers.ValidationError('Invalid project_id.')
        return value

    def validate_developer_id(self, value):
        if value and (not value.isdigit() or int(value) <= 0):
            raise serializers.ValidationError('Invalid developer_id.')
        return value

# 21. Project Serializer

class ProjectSerializer(serializers.ModelSerializer):

    client_id = ClientDetailsField(
        source='client',
        queryset=Client.objects.all(),
        required=False,
        allow_null=True
    )

    assigned_manager = FlexibleManagerField(
        required=False,
        allow_null=True
    )

    created_by = ProjectUserSerializer(read_only=True)

    updated_by = ProjectUserSerializer(
        source='modified_by',
        read_only=True
    )

    deleted_by = ProjectUserSerializer(
        read_only=True,
        allow_null=True
    )

    title = serializers.CharField(
        source='project_title',
        required=False,
        allow_null=True
    )

    type = serializers.CharField(
        source='project_type',
        required=False,
        allow_null=True
    )

    status = serializers.ChoiceField(
        choices=Project._meta.get_field('project_status').choices,
        source='project_status',
        required=False,
        allow_null=True
    )

    attachments = ProjectAttachmentSerializer(
        many=True,
        read_only=True
    )

    new_attachments = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False
    )

    delete_attachment_ids = serializers.JSONField(
        required=False,
        write_only=True
    )

    class Meta:
        model = Project
        fields = [
            'id', 'client_id', 'assigned_manager',
            'created_by', 'updated_by',
            'title', 'type', 'date_of_completion',
            'status', 'created_at', 'updated_at',
            'is_deleted', 'deleted_at', 'deleted_by',
            'attachments', 'new_attachments',
            'delete_attachment_ids', 'description',
        ]

        read_only_fields = [
            'id', 'created_by', 'updated_by',
            'created_at', 'updated_at',
            'is_deleted', 'deleted_at', 'deleted_by'
        ]

    # Project Title Duplicate Validation

    def validate_title(self, value):

        if value is None:
            return value

        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Project title cannot be empty."
            )

        queryset = Project.objects.filter(
            project_title__iexact=value,
            is_deleted=False
        )

        if self.instance:
            queryset = queryset.exclude(
                pk=self.instance.pk
            )

        if queryset.exists():
            raise serializers.ValidationError(
                "Project with this title already exists."
            )

        return value

    def validate_assigned_manager(self, value):

        if value is None:
            return value

        profile = getattr(value, 'profile', None)

        if not profile or profile.name.strip().lower() != 'manager':
            raise serializers.ValidationError(
                "Only users with Manager role can be assigned as project manager."
            )

        return value

    def validate_new_attachments(self, files):

        allowed_extensions = [
            '.pdf', '.txt', '.xls', '.xlsx',
            '.doc', '.docx', '.jpg', '.jpeg',
            '.png', '.gif'
        ]

        for file in files:
            extension = '.' + file.name.split('.')[-1].lower()

            if extension not in allowed_extensions:
                raise serializers.ValidationError(
                    f'{file.name}: This file type is not allowed.'
                )

        return files

    def validate_delete_attachment_ids(self, ids):

        if self.instance is None:
            raise serializers.ValidationError(
                'Attachments cannot be deleted while creating a project.'
            )

        if not isinstance(ids, list):
            raise serializers.ValidationError(
                'Attachment IDs must be a list.'
            )

        if not all(type(i) is int and i > 0 for i in ids):
            raise serializers.ValidationError(
                'All attachment IDs must be positive integers.'
            )

        existing_ids = set(
            self.instance.attachments.filter(
                id__in=ids
            ).values_list('id', flat=True)
        )

        invalid_ids = set(ids) - existing_ids

        if invalid_ids:
            raise serializers.ValidationError(
                f'Invalid attachment IDs: {list(invalid_ids)}'
            )

        return ids

    def create(self, validated_data):

        files = validated_data.pop('new_attachments', [])
        validated_data.pop('delete_attachment_ids', [])

        project = Project.objects.create(**validated_data)

        request = self.context.get('request')
        uploaded_by = None

        if request and request.user.is_authenticated:
            uploaded_by = request.user

        for file in files:
            ProjectAttachment.objects.create(
                project=project,
                attachment=file,
                uploaded_by=uploaded_by
            )

        send_client_project_email(project)
        send_manager_project_email(project)

        return project

    def update(self, instance, validated_data):

        files = validated_data.pop('new_attachments', [])

        delete_ids = validated_data.pop(
            'delete_attachment_ids', []
        )

        instance = super().update(instance, validated_data)

        request = self.context.get('request')
        uploaded_by = (
            request.user
            if request and request.user.is_authenticated
            else None
        )

        # Add new attachments

        for file in files:
            ProjectAttachment.objects.create(
                project=instance,
                attachment=file,
                uploaded_by=uploaded_by
            )

        # Permanently delete attachments from database and disk

        for attachment in instance.attachments.filter(
            id__in=delete_ids
        ):
            if attachment.attachment:
                attachment.attachment.delete(save=False)

            attachment.delete()

        return instance

#22. Manager Details Serializer

class ManagerSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'first_name',
            'last_name',
            'email',
            'role'
        ]

    def get_role(self, obj):
        if obj.profile:
            return {
                'id': obj.profile.id,
                'role': obj.profile.name,
                'is_default': obj.profile.is_default
            }

        return None


#.23 Task User Related Field

class TaskUserRelatedField(serializers.PrimaryKeyRelatedField):

    def to_representation(self, value):
        return ManagerSerializer(value).data

#24. User Profile Details Serializer

class ProfileSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='name', read_only=True)

    class Meta:
        model = Profile
        fields = ['id', 'role', 'is_default']




#25. Profile Create, Update and Validation Serializer

class ProfileCRUDSerializer(serializers.ModelSerializer):

    role = serializers.CharField(
        source='name',
        required=True,
        allow_blank=False,
        max_length=100
    )

    class Meta:
        model = Profile
        fields = ['id', 'role', 'is_default']
        read_only_fields = ['id', 'is_default']

    # Only string input is allowed
    def to_internal_value(self, data):

        if isinstance(data, dict) and 'role' in data:
            if not isinstance(data['role'], str):
                raise serializers.ValidationError({
                    'role': 'Role must be a string.'
                })

        return super().to_internal_value(data)

    def validate_role(self, value):

        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Role cannot be empty."
            )

        # Only alphabetic characters and spaces are allowed
        if not value.replace(' ', '').isalpha():
            raise serializers.ValidationError(
                "Role must contain only alphabetic characters."
            )

        # Default profile names are reserved
        if value.lower() in [
            role.lower() for role in Profile.DEFAULT_PROFILES
        ]:
            raise serializers.ValidationError(
                "This role is reserved for default profiles."
            )

        # Check duplicate profile names
        queryset = Profile.objects.filter(name__iexact=value)

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                "This role already exists."
            )

        return value

    # Create Custom Profile
    def create(self, validated_data):

        role = validated_data['name']

        return Profile.objects.create(
            name=role,
            profile_data={"role": role},
            is_default=False
        )

    # Update Custom Profile
    def update(self, instance, validated_data):

        role = validated_data.get('name', instance.name)

        instance.name = role
        instance.profile_data = {
            **(instance.profile_data or {}),
            "role": role
        }

        instance.save()

        return instance


# 26.Profile Role Query Parameter Validation

class ProfileRoleQuerySerializer(serializers.Serializer):

    role = serializers.CharField(
        required=False,
        allow_blank=True
    )

    def validate(self, data):
        role = data.get('role', '')

        if role:
            try:
                data['profile'] = Profile.objects.get(
                    name__iexact=role
                )
            except Profile.DoesNotExist:
                raise serializers.ValidationError(
                    'Profile does not exist.'
                )

        return data

#27. Profile Detail Action Validation

class ProfileDetailActionSerializer(serializers.Serializer):

    pk = serializers.CharField()

    def validate(self, attrs):

        pk = attrs['pk']

        if not pk.isdigit() or int(pk) <= 0:
            raise serializers.ValidationError({
                'profile_not_found':
                    'Invalid profile ID or profile not found.'
            })

        try:
            profile = Profile.objects.get(pk=int(pk))
        except Profile.DoesNotExist:
            raise serializers.ValidationError({
                'profile_not_found':
                    'Invalid profile ID or profile not found.'
            })

        action = self.context.get('action')

        if profile.is_default and action in ['put', 'patch']:
            raise serializers.ValidationError({
                'default_profile':
                    'Default profiles cannot be updated.'
            })

        if profile.is_default and action == 'delete':
            raise serializers.ValidationError({
                'default_profile':
                    'Default profiles cannot be deleted.'
            })

        attrs['profile'] = profile

        return attrs

# 28.Profile Users Query Parameter Validation

class ProfileUsersQuerySerializer(serializers.Serializer):

    role = serializers.CharField(
        required=True,
        allow_blank=False,
        error_messages={
            'required': 'Please provide role parameter.',
            'blank': 'Please provide role parameter.'
        }
    )

    def validate_role(self, value):

        try:
            return Profile.objects.get(name__iexact=value.strip())

        except Profile.DoesNotExist:
            raise serializers.ValidationError(
                'Profile does not exist.'
            )



# 29. Project Task Serializer

class ProjectTaskSerializer(serializers.ModelSerializer):

    project_id = serializers.PrimaryKeyRelatedField(
        source='project',
        queryset=Project.objects.all(),
        write_only=True
    )

    project = serializers.SerializerMethodField()

    developers = TaskUserRelatedField(
        many=True,
        queryset=User.objects.all(),
        required=False
    )

    team_leader = TaskUserRelatedField(
        many=True,
        queryset=User.objects.all(),
        required=False
    )

    created_by = ProjectUserSerializer(read_only=True)

    modified_by = ProjectUserSerializer(read_only=True)

    class Meta:
        model = ProjectTask

        fields = [
            'id',
            'task_title',
            'project',
            'project_id',
            'developers',
            'team_leader',
            'completion_date',
            'deadline_date',
            'task_status',
            'start_date',
            'created_by',
            'modified_by',
            'created_at',
            'updated_at'
        ]

        read_only_fields = [
            'id',
            'created_by',
            'modified_by',
            'created_at',
            'updated_at'
        ]

    # Project Details

    def get_project(self, obj):

        if not obj.project:
            return None

        return {
            'id': obj.project.id,
            'project_title': obj.project.project_title,
            'description': obj.project.description,
            'start_date': obj.project.start_date,
            'date_of_completion': obj.project.date_of_completion
        }

    # Developer Validation

    def validate_developers(self, developers):

        for developer in developers:

            if (
                not developer.profile
                or developer.profile.name.strip().lower() != 'developer'
            ):
                raise serializers.ValidationError(
                    f"User {developer.id} must have Developer role."
                )

            if developer.status != 'Active':
                raise serializers.ValidationError(
                    f"User {developer.id} is inactive."
                )

        return developers

    # Team Leader Validation

    def validate_team_leader(self, team_leaders):

        for leader in team_leaders:

            if (
                not leader.profile
                or leader.profile.name.strip().lower() != 'team leader'
            ):
                raise serializers.ValidationError(
                    f"User {leader.id} must have Team Leader role."
                )

            if leader.status != 'Active':
                raise serializers.ValidationError(
                    f"User {leader.id} is inactive."
                )

        return team_leaders


# 30. Task Comment Serializer

class TaskCommentSerializer(serializers.ModelSerializer):

    task_id = serializers.PrimaryKeyRelatedField(
        source='task',
        queryset=ProjectTask.objects.all(),
        write_only=True
    )

    task_title = serializers.CharField(
        source='task.task_title',
        read_only=True
    )

    user = ProjectUserSerializer(read_only=True)

    class Meta:
        model = TaskComment
        fields = [
            'id',
            'task_id',
            'task_title',
            'user',
            'comment',
            'created_at',
            'updated_at'
        ]

        read_only_fields = [
            'id',
            'user',
            'created_at',
            'updated_at'
        ]

#31. Restore IDs Validation Serializer
class RestoreIDsSerializer(serializers.Serializer):

    ids = serializers.JSONField(required=False)

    def validate(self, attrs):

        ids = attrs.get('ids')

        if isinstance(ids, str):
            try:
                ids = json.loads(ids)
            except json.JSONDecodeError:
                ids = ids.split(',')

        if isinstance(ids, int):
            ids = [ids]

        if not isinstance(ids, list) or not ids:
            raise serializers.ValidationError(
                'Valid IDs list is required.'
            )

        try:
            ids = [int(item) for item in ids]
        except (ValueError, TypeError):
            raise serializers.ValidationError(
                'Valid IDs list is required.'
            )

        if any(item <= 0 for item in ids):
            raise serializers.ValidationError(
                'Valid IDs list is required.'
            )

        attrs['ids'] = ids

        return attrs

#32.Task Comment List Query Parameter Validation

class TaskCommentListQuerySerializer(serializers.Serializer):

    task_id = serializers.CharField(required=False, allow_blank=True)

    def validate_task_id(self, value):
        if value and (not value.isdigit() or int(value) <= 0):
            raise serializers.ValidationError('Invalid task_id.')
        return value