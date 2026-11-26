
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
    ProjectTask, TaskComment, ProjectType, ProjectStatus, TaskStatus,
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

# 2. User Login Serializer
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=True,
        error_messages={
            'required': 'Email is required.',
            'invalid': 'Enter a valid email address.',
            'blank': 'Email cannot be blank.',
            'null': 'Email cannot be null.',
        }
    )

    password = serializers.CharField(
        write_only=True,
        required=True,
        error_messages={
            'required': 'Password is required.',
            'blank': 'Password cannot be blank.',
            'null': 'Password cannot be null.',
        }
    )

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

        profile = user.profile

        return {
            'message': 'Login successful.',
            'user_id': user.id,
            'email': user.email,
            'role': profile.name if profile else None,
            'profile': {
                'id': profile.id,
                'name': profile.name
            } if profile else None,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }

# 3. Send OTP Serializer
class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=True,
        error_messages={
            'required': 'Email is required.',
            'invalid': 'Enter a valid email address.',
            'blank': 'Email cannot be blank.',
            'null': 'Email cannot be null.',
        }
    )

    def validate(self, data):
        email = data['email']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                'User with this email does not exist.'
            )

        if user.status != 'Active':
            raise serializers.ValidationError({
                'active_user_not_found': 'Active user not found.'
            })

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

        data['user'] = user
        return data

# 4. Verify OTP Serializer
class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=True,
        error_messages={
            'required': 'Email is required.',
            'invalid': 'Enter a valid email address.',
            'blank': 'Email cannot be blank.',
            'null': 'Email cannot be null.',
        }
    )

    otp = serializers.CharField(
        max_length=6,
        required=True,
        error_messages={
            'required': 'OTP is required.',
            'blank': 'OTP cannot be blank.',
            'null': 'OTP cannot be null.',
            'max_length': 'OTP must not exceed 6 characters.',
        }
    )

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
    email = serializers.EmailField(
        required=True,
        error_messages={
            'required': 'Email is required.',
            'invalid': 'Enter a valid email address.',
            'blank': 'Email cannot be blank.',
            'null': 'Email cannot be null.',
        }
    )

    otp = serializers.CharField(
        max_length=6,
        required=True,
        error_messages={
            'required': 'OTP is required.',
            'blank': 'OTP cannot be blank.',
            'null': 'OTP cannot be null.',
            'max_length': 'OTP must not exceed 6 characters.',
        }
    )

    new_password = serializers.CharField(
        write_only=True,
        required=True,
        error_messages={
            'required': 'New password is required.',
            'blank': 'New password cannot be blank.',
            'null': 'New password cannot be null.',
        }
    )

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

# 6. User List Query Parameter Validation
class UserListQuerySerializer(serializers.Serializer):

    status = serializers.CharField(
        required=False,
        default='Active',
        error_messages={
            'invalid': 'Invalid status.',
            'blank': 'Status cannot be blank.',
            'null': 'Status cannot be null.',
        }
    )

    date_from = serializers.CharField(
        required=False,
        allow_blank=True,
        error_messages={
            'invalid': 'Invalid date_from.',
            'null': 'date_from cannot be null.',
        }
    )

    date_to = serializers.CharField(
        required=False,
        allow_blank=True,
        error_messages={
            'invalid': 'Invalid date_to.',
            'null': 'date_to cannot be null.',
        }
    )

    profile = serializers.CharField(
        required=False,
        allow_blank=True,
        error_messages={
            'invalid': 'Profile must be a valid string.',
            'null': 'Profile cannot be null.',
        }
    )

    profile_id = serializers.IntegerField(
        required=False,
        min_value=1,
        error_messages={
            'invalid': 'Profile ID must be a valid integer.',
            'null': 'Profile ID cannot be null.',
            'min_value': 'Profile ID must be greater than 0.',
        }
    )

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

    def validate(self, data):

        profile = data.get('profile', '').strip()
        profile_id = data.get('profile_id')

        if profile and profile_id is not None:
            raise serializers.ValidationError(
                'Use either profile or profile_id, not both.'
            )

        if profile:
            if not Profile.objects.filter(
                name__iexact=profile
            ).exists():
                raise serializers.ValidationError(
                    'Profile does not exist.'
                )

        if profile_id is not None:
            if not Profile.objects.filter(id=profile_id).exists():
                raise serializers.ValidationError(
                    'Profile does not exist.'
                )

        return data

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
            'date_of_birth', 'gender', 'nationality', 'country',
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

    def to_representation(self, instance):

        data = super().to_representation(instance)

        if instance.modified_by_id is None:
            data.pop('modified_by', None)

        return data

    def get_profiles(self, obj):

        profile = obj.profile

        if not profile:
            return None

        return {
            'id': profile.id,
            'role': profile.name.lower(),
            'is_active': profile.status == 'Active',
            'is_default': profile.is_default
        }

#9. User Create Serializer
class UserCreateSerializer(serializers.ModelSerializer):

    profiles = serializers.PrimaryKeyRelatedField(
        queryset=Profile.objects.filter(status='Active'),
        source='profile',
        write_only=True,
        required=True,
        error_messages={
            'required': 'Please provide a profile ID.',
            'does_not_exist': 'Profile does not exist or is inactive.',
            'incorrect_type': 'Profile ID must be a valid integer.',
            'null': 'Profile ID cannot be null.'
        }
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
            'date_of_birth', 'gender', 'nationality', 'country',
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

    def to_representation(self, instance):

        data = super().to_representation(instance)


        if instance.modified_by_id is None:
            data.pop('modified_by', None)

        return data

    def validate_request_data(self, data):

        if not isinstance(data, dict):
            raise serializers.ValidationError(
                'Invalid request data. Expected a JSON object.'
            )

        return data

    def validate_email(self, value):

        if value != value.lower():
            raise serializers.ValidationError(
                'Email must contain only lowercase letters.'
            )

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

        validated_data['status'] = (
            validated_data.get('status') or 'Active'
        )

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
        allow_null=False,
        error_messages={
            'does_not_exist': 'Profile does not exist or is inactive.',
            'incorrect_type': 'Profile ID must be a valid integer.',
            'null': 'Profile ID cannot be null.'
        }
    )

    email = serializers.EmailField(
        required=False,
        error_messages={
            'invalid': 'Enter a valid email address.',
            'blank': 'Email cannot be blank.',
            'null': 'Email cannot be null.'
        }
    )

    created_by = UserAuditSerializer(read_only=True)
    modified_by = UserAuditSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'email', 'username',
            'profiles',
            'date_of_birth', 'gender', 'nationality', 'country',
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

    def validate_request_data(self, data):

        if not isinstance(data, dict):
            raise serializers.ValidationError(
                'Invalid request data. Expected a JSON object.'
            )

        allowed_fields = set(self.fields.keys())
        invalid_fields = set(data.keys()) - allowed_fields

        if invalid_fields:
            raise serializers.ValidationError({
                field: 'This field is not allowed.'
                for field in invalid_fields
            })

        return data

    def validate(self, attrs):

        request = self.context.get('request')

        if request and self.instance:
            profile = getattr(request.user, 'profile', None)
            role = profile.name if profile else ''

            is_admin = role in ['Admin', 'Super Admin']
            is_own_data = request.user.pk == self.instance.pk

            if is_own_data and not is_admin:

                restricted_fields = {
                    'email': 'Email',
                    'profiles': 'Profile',
                    'status': 'Status',
                    'date_of_birth': 'Date of birth',
                    'gender': 'Gender'
                }

                errors = {}

                for field, field_name in restricted_fields.items():
                    if field in self.initial_data:
                        errors[field] = (
                            f'You cannot change your own {field_name}. '
                            'Only Admin and Super Admin can change this field.'
                        )

                if errors:
                    raise serializers.ValidationError(errors)

        return attrs

    def validate_email(self, value):

        if value != value.lower():
            raise serializers.ValidationError(
                'Email must contain only lowercase letters.'
            )

        if User.objects.filter(email__iexact=value).exclude(
            pk=self.instance.pk
        ).exists():
            raise serializers.ValidationError(
                'A user with this email already exists.'
            )

        return value

    def update(self, instance, validated_data):

        profile = validated_data.pop('profile', serializers.empty)

        if profile is not serializers.empty:
            instance.profile = profile

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
        default='Active',
        error_messages={
            'invalid': 'Status must be a valid string.',
            'blank': 'Status cannot be blank.',
            'null': 'Status cannot be null.'
        }
    )

    date_from = serializers.CharField(
        required=False,
        allow_blank=True,
        error_messages={
            'invalid': 'date_from must be a valid string.',
            'null': 'date_from cannot be null.'
        }
    )

    date_to = serializers.CharField(
        required=False,
        allow_blank=True,
        error_messages={
            'invalid': 'date_to must be a valid string.',
            'null': 'date_to cannot be null.'
        }
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

    def to_internal_value(self, data):

        if not hasattr(data, 'keys'):
            raise serializers.ValidationError({
                'detail': 'Request data must be a JSON object.'
            })

        valid_fields = set(self.fields.keys())
        invalid_fields = set(data.keys()) - valid_fields

        if invalid_fields:
            errors = {
                field: ['This is not a valid field. Please provide a valid field name.']
                for field in invalid_fields
            }

            raise serializers.ValidationError(errors)

        return super().to_internal_value(data)

#13 New Client Serializer using User model
class UserClientSerializer(serializers.ModelSerializer):

    address = serializers.CharField(
        source='permanent_address',
        required=False,
        allow_blank=True,
        allow_null=True,
        error_messages={
            'invalid': 'Address must be a valid string.'
        }
    )

    contact_no = serializers.CharField(
        source='phone',
        required=False,
        allow_blank=True,
        allow_null=True,
        error_messages={
            'invalid': 'Contact number must be a valid string.'
        }
    )

    email_id = serializers.EmailField(
        source='email',
        required=True,
        error_messages={
            'required': 'Email is required.',
            'invalid': 'Enter a valid email address.',
            'blank': 'Email cannot be blank.',
            'null': 'Email cannot be null.'
        }
    )

    profiles = serializers.SerializerMethodField()

    created_by = UserAuditSerializer(read_only=True)
    modified_by = UserAuditSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'first_name',
            'last_name',
            'address',
            'country',
            'contact_no',
            'email_id',
            'status',
            'profiles',
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance is not None:
            self.fields['email_id'].required = False

    def get_profiles(self, obj):
        profile = getattr(obj, 'profile', None)

        if not profile:
            return None

        return {
            'id': profile.id,
            'role': profile.name.lower(),
            'is_active': profile.status == 'Active',
            'is_default': profile.is_default
        }

    def validate(self, attrs):

        request = self.context.get('request')

        if request and self.instance:
            profile = getattr(request.user, 'profile', None)
            role = profile.name if profile else ''

            is_admin = role in ['Admin', 'Super Admin']
            is_own_data = request.user.pk == self.instance.pk

            if is_own_data and not is_admin:

                restricted_fields = {
                    'email_id': 'Email',
                    'status': 'Status',
                    'profiles': 'Profile'
                }

                errors = {}

                for field, field_name in restricted_fields.items():
                    if field in self.initial_data:
                        errors[field] = (
                            f'You cannot change your own {field_name}. '
                            'Only Admin and Super Admin can change this field.'
                        )

                if errors:
                    raise serializers.ValidationError(errors)

        return attrs

    def validate_email_id(self, value):
        queryset = User.objects.filter(email__iexact=value)

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                'A user with this email already exists.'
            )

        return value

#14. Project Client Details Serializer
class ProjectClientSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        source='email_id',
        read_only=True
    )

    class Meta:
        model = Client
        fields = ['id', 'first_name', 'last_name', 'email']

# 15. Client Details Field
class ClientDetailsField(serializers.PrimaryKeyRelatedField):

    def to_representation(self, value):
        return ProjectClientSerializer(value).data

# 16. User Client Details Serializer
class UserClientDetailsSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email']


# 17. User Client Details Field
class UserClientDetailsField(serializers.PrimaryKeyRelatedField):

    def use_pk_only_optimization(self):
        return False

    def to_representation(self, value):
        return UserClientDetailsSerializer(value).data

#18. Project User Details Serializer
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


# 19. Project Attachment Serializer
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

# 20. Send Project Creation Email Notification to Client
def send_client_project_email(project):

    client = project.client or project.user_client

    if not client:
        return

    client_email = (
        getattr(client, 'email_id', None)
        or getattr(client, 'email', None)
    )

    if not client_email:
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
        f"Project Status: {project.project_status_master.name if project.project_status_master else 'Not provided'}\n"
        f"Description: {project.description or 'Not provided'}\n\n"
        f"Assigned Manager: {manager_name}\n"
        f"Manager Email: {manager_email}\n\n"
        f"Thank you."
    )

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [client_email],
        fail_silently=True
    )

# 21. Send Project Assignment Email Notification to Manager
def send_manager_project_email(project):

    manager = project.assigned_manager

    if not manager or not manager.email:
        return

    client = project.client or project.user_client

    if client:
        client_name = (
            f"{client.first_name or ''} {client.last_name or ''}"
        ).strip()

        client_email = (
            getattr(client, 'email_id', None)
            or getattr(client, 'email', None)
            or "Not available"
        )
    else:
        client_name = "Not assigned"
        client_email = "Not available"

    subject = "New Project Assigned to You"

    message = (
        f"Hello {manager.first_name or manager.username},\n\n"
        f"A new project has been assigned to you.\n\n"
        f"Project Title: {project.project_title}\n"
        f"Project Status: {project.project_status_master.name if project.project_status_master else 'Not provided'}\n"
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

#22. Project List Query Parameter Validation
class ProjectListQuerySerializer(serializers.Serializer):

    status = serializers.CharField(
        required=False,
        default='Active',
        error_messages={
            'invalid': 'Status must be a valid string.',
            'blank': 'Status cannot be blank.',
            'null': 'Status cannot be null.'
        }
    )

    client_id = serializers.CharField(
        required=False,
        allow_blank=True,
        error_messages={
            'invalid': 'client_id must be a valid string.',
            'null': 'client_id cannot be null.'
        }
    )

    manager_id = serializers.CharField(
        required=False,
        allow_blank=True,
        error_messages={
            'invalid': 'manager_id must be a valid string.',
            'null': 'manager_id cannot be null.'
        }
    )

    date_from = serializers.CharField(
        required=False,
        allow_blank=True,
        error_messages={
            'invalid': 'date_from must be a valid string.',
            'null': 'date_from cannot be null.'
        }
    )

    date_to = serializers.CharField(
        required=False,
        allow_blank=True,
        error_messages={
            'invalid': 'date_to must be a valid string.',
            'null': 'date_to cannot be null.'
        }
    )

    created_from = serializers.CharField(
        required=False,
        allow_blank=True,
        error_messages={
            'invalid': 'created_from must be a valid string.',
            'null': 'created_from cannot be null.'
        }
    )

    created_to = serializers.CharField(
        required=False,
        allow_blank=True,
        error_messages={
            'invalid': 'created_to must be a valid string.',
            'null': 'created_to cannot be null.'
        }
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

#23. Project Task List Query Parameter Validation
class ProjectTaskListQuerySerializer(serializers.Serializer):

    project_id = serializers.CharField(
        required=False,
        allow_blank=True,
        error_messages={
            'invalid': 'project_id must be a valid string.',
            'null': 'project_id cannot be null.'
        }
    )

    developer_id = serializers.CharField(
        required=False,
        allow_blank=True,
        error_messages={
            'invalid': 'developer_id must be a valid string.',
            'null': 'developer_id cannot be null.'
        }
    )

    def validate_project_id(self, value):
        if value and (not value.isdigit() or int(value) <= 0):
            raise serializers.ValidationError('Invalid project_id.')
        return value

    def validate_developer_id(self, value):
        if value and (not value.isdigit() or int(value) <= 0):
            raise serializers.ValidationError('Invalid developer_id.')
        return value

# 24. Project Serializer
class ProjectSerializer(serializers.ModelSerializer):

    client_id = ClientDetailsField(
        source='client',
        queryset=Client.objects.all(),
        required=False,
        allow_null=True,
        error_messages={
            'does_not_exist': 'Client does not exist.',
            'incorrect_type': 'Client ID must be a valid integer.',
            'null': 'Client ID cannot be null.'
        }
    )

    user_client_id = UserClientDetailsField(
        source='user_client',
        queryset=User.objects.filter(profile__name='Client'),
        required=False,
        allow_null=True,
        error_messages={
            'does_not_exist': 'User Client does not exist.',
            'incorrect_type': 'User Client ID must be a valid integer.',
            'null': 'User Client ID cannot be null.'
        }
    )

    assigned_manager = FlexibleManagerField(
        required=False,
        allow_null=True
    )

    team_leaders = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=User.objects.filter(
            profile__name='Team Leader',
            status='Active'
        ),
        required=False,
        error_messages={
            'does_not_exist': 'Team Leader does not exist or is inactive.',
            'incorrect_type': 'Team Leader ID must be a valid integer.'
        }
    )

    created_by = ProjectUserSerializer(read_only=True)

    updated_by = ProjectUserSerializer(
        source='modified_by',
        read_only=True
    )

    title = serializers.CharField(
        source='project_title',
        required=False,
        allow_null=False,
        error_messages={
            'required': 'Please provide a project title.',
            'invalid': 'Project title must be a valid string.',
            'blank': 'Project title cannot be blank.',
            'null': 'Project title cannot be null.'
        }
    )

    type = serializers.SlugRelatedField(
        slug_field='name',
        source='project_type_master',
        queryset=ProjectType.objects.filter(is_active=True),
        required=False,
        allow_null=True,
        error_messages={
            'does_not_exist': 'Invalid project type. Please select a valid project type.',
            'invalid': 'Project type must be a valid string.'
        }
    )

    status = serializers.CharField(
        required=False,
        allow_null=True,
        error_messages={
            'invalid': 'Project status must be a valid ID or name.',
            'blank': 'Project status cannot be blank.',
            'null': 'Project status cannot be null.'
        }
    )

    attachments = ProjectAttachmentSerializer(
        many=True,
        read_only=True
    )

    new_attachments = serializers.ListField(
        child=serializers.FileField(
            error_messages={
                'required': 'Attachment file is required.',
                'invalid': 'Please provide a valid attachment file.',
                'null': 'Attachment file cannot be null.'
            }
        ),
        write_only=True,
        required=False,
        error_messages={
            'not_a_list': 'Attachments must be provided as a list.',
            'null': 'Attachments cannot be null.'
        }
    )

    delete_attachment_ids = serializers.JSONField(
        required=False,
        write_only=True,
        error_messages={
            'invalid': 'Attachment IDs cannot be null.',
            'null': 'Attachment IDs cannot be null.'
        }
    )

    class Meta:
        model = Project
        fields = [
            'id', 'client_id', 'user_client_id', 'assigned_manager',
            'team_leaders',
            'created_by', 'updated_by',
            'title', 'type', 'date_of_completion',
            'status', 'created_at', 'updated_at',
            'is_deleted', 'attachments', 'new_attachments',
            'delete_attachment_ids', 'description',
        ]

        read_only_fields = [
            'id', 'created_by', 'updated_by',
            'created_at', 'updated_at',
            'is_deleted'
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)

        # Display status from project_status_master
        data['status'] = (
            instance.project_status_master.name
            if instance.project_status_master
            else None
        )

        if instance.client_id:
            data.pop('user_client_id', None)

        elif instance.user_client_id:
            data.pop('client_id', None)

        # Hide team_leaders when no Team Leader is assigned
        if not instance.team_leaders.exists():
            data.pop('team_leaders', None)

        # Hide update fields only in creation response
        if self.context.get('is_create_response'):
            data.pop('updated_by', None)
            data.pop('updated_at', None)

        return data

    def validate_status(self, value):

        if value is None:
            return None

        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                'Project status cannot be blank.'
            )

        if value.isdigit():
            status = ProjectStatus.objects.filter(
                id=int(value),
                is_active=True
            ).first()

            if not status:
                raise serializers.ValidationError(
                    'Invalid project status ID. Please select a valid status.'
                )

            return status

        status = ProjectStatus.objects.filter(
            name__iexact=value,
            is_active=True
        ).first()

        if not status:
            raise serializers.ValidationError(
                'Invalid project status. Please select a valid status.'
            )

        return status

    def validate(self, attrs):

        request = self.context.get('request')

        # Convert status into project_status_master
        if 'status' in attrs:
            attrs['project_status_master'] = attrs.pop('status')

        if 'project_type_master' in attrs:

            role = (
                request.user.profile.name
                if request and request.user.is_authenticated and request.user.profile
                else ''
            )

            if role not in ['Super Admin', 'Admin']:
                raise serializers.ValidationError({
                    'type': 'Only Admin and Super Admin can change the project type.'
                })

        if self.instance is None:

            errors = {}

            if 'project_title' not in attrs:
                errors['title'] = 'Please provide a project title.'

            manager = attrs.get(
                'assigned_manager',
                serializers.empty
            )

            if manager is serializers.empty or manager is None:
                errors['assigned_manager'] = 'Please assign a Manager to this project.'

            if errors:
                raise serializers.ValidationError(errors)

            if 'team_leaders' in self.initial_data:
                raise serializers.ValidationError({
                    'team_leaders': 'Team Leaders can only be assigned after project creation.'
                })

        client = attrs.get('client', serializers.empty)
        user_client = attrs.get('user_client', serializers.empty)

        if (
            client is not serializers.empty and client is not None
            and user_client is not serializers.empty and user_client is not None
        ):
            raise serializers.ValidationError({
                'client_id': 'Assign either old Client or User Client, not both.'
            })

        if client is not serializers.empty and client is not None:
            attrs['user_client'] = None

        elif user_client is not serializers.empty and user_client is not None:
            attrs['client'] = None

        return attrs

    def validate_title(self, value):

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

    def validate_new_attachments(self, files):

        allowed_extensions = [
            '.pdf', '.txt', '.xls', '.xlsx',
            '.doc', '.docx', '.jpg', '.jpeg',
            '.png', '.gif'
        ]

        max_size = 10 * 1024 * 1024  # 10 MB per file

        for file in files:

            if file.size > max_size:
                raise serializers.ValidationError(
                    f'{file.name}: File size cannot exceed 10 MB.'
                )

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

#25. Manager Details Serializer
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

#.26 Task User Related Field
class TaskUserRelatedField(serializers.PrimaryKeyRelatedField):

    def to_representation(self, value):
        return ManagerSerializer(value).data

#27. User Profile Details Serializer
class ProfileSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='name', read_only=True)

    class Meta:
        model = Profile
        fields = ['id', 'role', 'is_default']

#28. Profile Create, Update and Validation Serializer
class ProfileCRUDSerializer(serializers.ModelSerializer):

    role = serializers.CharField(
        source='name',
        required=True,
        allow_blank=False,
        max_length=100,
        error_messages={
            'required': 'Please provide a role.',
            'invalid': 'Role must be a valid string.',
            'blank': 'Role cannot be blank.',
            'null': 'Role cannot be null.',
            'max_length': 'Role cannot contain more than 100 characters.'
        }
    )

    class Meta:
        model = Profile
        fields = ['id', 'role', 'is_default']
        read_only_fields = ['id', 'is_default']

    def to_internal_value(self, data):

        if not isinstance(data, dict):
            raise serializers.ValidationError({
                'detail': 'Request data must be a JSON object.'
            })

        if 'role' in data and not isinstance(data['role'], str):
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

        if not value.replace(' ', '').isalpha():
            raise serializers.ValidationError(
                "Role must contain only alphabetic characters."
            )

        if value.lower() in [
            role.lower() for role in Profile.DEFAULT_PROFILES
        ]:
            raise serializers.ValidationError(
                "This role is reserved for default profiles."
            )

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

# 29.Profile Role Query Parameter Validation
class ProfileRoleQuerySerializer(serializers.Serializer):

    role = serializers.CharField(
        required=False,
        allow_blank=True,
        error_messages={
            'invalid': 'Role must be a valid string.',
            'null': 'Role cannot be null.'
        }
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

#30. Profile Detail Action Validation
class ProfileDetailActionSerializer(serializers.Serializer):

    pk = serializers.CharField(
        required=True,
        error_messages={
            'required': 'Please provide a profile ID.',
            'invalid': 'Profile ID must be a valid string.',
            'blank': 'Profile ID cannot be blank.',
            'null': 'Profile ID cannot be null.'
        }
    )

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

# 31.Profile Users Query Parameter Validation
class ProfileUsersQuerySerializer(serializers.Serializer):

    role = serializers.CharField(
        required=True,
        allow_blank=False,
        error_messages={
            'required': 'Please provide role parameter.',
            'blank': 'Please provide role parameter.',
            'invalid': 'Role must be a valid string.',
            'null': 'Role cannot be null.'
        }
    )

    def validate_role(self, value):

        try:
            return Profile.objects.get(name__iexact=value.strip())

        except Profile.DoesNotExist:
            raise serializers.ValidationError(
                'Profile does not exist.'
            )

# 32. Project Task Serializer
class ProjectTaskSerializer(serializers.ModelSerializer):

    project_id = serializers.PrimaryKeyRelatedField(
        source='project',
        queryset=Project.objects.all(),
        write_only=True,
        required=True,
        allow_null=False,
        error_messages={
            'required': 'Please provide a project ID.',
            'does_not_exist': 'Project does not exist.',
            'incorrect_type': 'Project ID must be a valid integer.',
            'null': 'Project ID cannot be null.'
        }
    )

    project = serializers.SerializerMethodField()

    developers = TaskUserRelatedField(
        many=True,
        queryset=User.objects.all(),
        required=False,
        error_messages={
            'does_not_exist': 'Developer does not exist.',
            'incorrect_type': 'Developer ID must be a valid integer.'
        }
    )

    team_leader = TaskUserRelatedField(
        many=True,
        queryset=User.objects.all(),
        required=False,
        error_messages={
            'does_not_exist': 'Team Leader does not exist.',
            'incorrect_type': 'Team Leader ID must be a valid integer.'
        }
    )

    task_title = serializers.CharField(
        error_messages={
            'required': 'Please provide a task title.',
            'invalid': 'Task title must be a valid string.',
            'blank': 'Task title cannot be blank.',
            'null': 'Task title cannot be null.'
        }
    )

    completion_date = serializers.DateField(
        required=False,
        allow_null=True,
        error_messages={
            'invalid': 'Invalid completion date. Use YYYY-MM-DD.',
        }
    )

    deadline_date = serializers.DateField(
        required=True,
        allow_null=False,
        error_messages={
            'required': 'Please provide deadline date.',
            'invalid': 'Invalid deadline date. Use YYYY-MM-DD.',
            'null': 'Deadline date cannot be null.'
        }
    )

    start_date = serializers.DateField(
        required=False,
        allow_null=True,
        error_messages={
            'invalid': 'Invalid start date. Use YYYY-MM-DD.',
        }
    )

    task_status = serializers.CharField(
        source='task_status_master',
        required=True,
        allow_null=False,
        error_messages={
            'required': 'Please provide task status.',
            'invalid': 'Task status must be a valid ID or name.',
            'blank': 'Task status cannot be blank.',
            'null': 'Task status cannot be null.'
        }
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

    def validate_task_status(self, value):

        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                'Task status cannot be blank.'
            )

        if value.isdigit():

            status = TaskStatus.objects.filter(
                id=int(value),
                is_active=True
            ).first()

            if not status:
                raise serializers.ValidationError(
                    'Please provide a valid task status ID.'
                )

            return status

        status = TaskStatus.objects.filter(
            name__iexact=value,
            is_active=True
        ).first()

        if not status:
            raise serializers.ValidationError(
                'Please provide a valid task status.'
            )

        return status

    def get_task_status_response(self, instance):

        if instance.task_status_master:
            return instance.task_status_master.name

        return None

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

    def validate(self, attrs):

        if self.instance is None:

            request = self.context.get('request')

            if (
                request
                and request.user.profile
                and request.user.profile.name == 'Team Leader'
            ):
                developers = attrs.get('developers', [])

                if not developers:
                    raise serializers.ValidationError({
                        'developers': 'Please assign at least one Developer to the task.'
                    })

        return attrs

    def to_representation(self, instance):

        data = super().to_representation(instance)

        data['task_status'] = self.get_task_status_response(instance)

        if instance.modified_by is None:
            data.pop('modified_by', None)

        if self.context.get('is_create_response'):
            data.pop('updated_at', None)

            request = self.context.get('request')

            if request:
                if 'developers' not in request.data:
                    data.pop('developers', None)

                if 'team_leader' not in request.data:
                    data.pop('team_leader', None)

        return data

# 33. Task Comment Serializer
class TaskCommentSerializer(serializers.ModelSerializer):

    task_id = serializers.PrimaryKeyRelatedField(
        source='task',
        queryset=ProjectTask.objects.all(),
        write_only=True,
        error_messages={
            'required': 'Please provide a task ID.',
            'does_not_exist': 'Task does not exist.',
            'incorrect_type': 'Task ID must be a valid integer.',
            'null': 'Task ID cannot be null.'
        }
    )

    task_title = serializers.CharField(
        source='task.task_title',
        read_only=True
    )

    user = ProjectUserSerializer(read_only=True)

    comment = serializers.CharField(
        error_messages={
            'required': 'Please provide a comment.',
            'invalid': 'Comment must be a valid string.',
            'blank': 'Comment cannot be blank.',
            'null': 'Comment cannot be null.'
        }
    )

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

    def validate(self, attrs):

        request = self.context.get('request')

        if request:
            profile = getattr(request.user, 'profile', None)
            role = profile.name if profile else ''

            if role == 'Client':
                raise serializers.ValidationError({
                    'comment': 'Clients do not have permission to add comments.'
                })

        return attrs

#34. Restore IDs Validation Serializer
class RestoreIDsSerializer(serializers.Serializer):

    ids = serializers.JSONField(required=False)

    def validate(self, attrs):

        ids = attrs.get('ids')

        if isinstance(ids, str):
            try:
                ids = json.loads(ids)
            except json.JSONDecodeError:
                ids = ids.split(',')

        if isinstance(ids, bool):
            raise serializers.ValidationError(
                'Valid IDs list is required.'
            )

        if isinstance(ids, int):
            ids = [ids]

        if not isinstance(ids, list) or not ids:
            raise serializers.ValidationError(
                'Valid IDs list is required.'
            )

        validated_ids = []

        for item in ids:
            if isinstance(item, bool):
                raise serializers.ValidationError(
                    'Valid IDs list is required.'
                )

            if isinstance(item, float) and not item.is_integer():
                raise serializers.ValidationError(
                    'Valid IDs list is required.'
                )

            try:
                item = int(item)
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    'Valid IDs list is required.'
                )

            if item <= 0:
                raise serializers.ValidationError(
                    'Valid IDs list is required.'
                )

            validated_ids.append(item)

        attrs['ids'] = validated_ids

        return attrs

#35.Task Comment List Query Parameter Validation
class TaskCommentListQuerySerializer(serializers.Serializer):

    task_id = serializers.CharField(
        required=False,
        allow_blank=True,
        error_messages={
            'invalid': 'task_id must be a valid string.',
            'null': 'task_id cannot be null.'
        }
    )

    def validate_task_id(self, value):
        if value and (not value.isdigit() or int(value) <= 0):
            raise serializers.ValidationError('Invalid task_id.')
        return value

# 36. Master Data CRUD Base Serializer
class MasterDataCRUDSerializer(serializers.ModelSerializer):

    name = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=100,
        error_messages={
            'required': 'Please provide a name.',
            'invalid': 'Name must be a valid string.',
            'blank': 'Name cannot be blank.',
            'null': 'Name cannot be null.',
            'max_length': 'Name cannot contain more than 100 characters.'
        }
    )

    is_active = serializers.BooleanField(required=False)

    class Meta:
        fields = [
            'id',
            'name',
            'is_active',
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

    def validate_name(self, value):

        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                'Name cannot be blank.'
            )

        queryset = self.Meta.model.objects.filter(
            name__iexact=value
        )

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                'This name already exists.'
            )

        return value

    def to_representation(self, instance):

        data = super().to_representation(instance)

        if instance.modified_by_id is None:
            data.pop('modified_by', None)
            data.pop('updated_at', None)

        return data

# 37. Project Type CRUD Serializer
class ProjectTypeCRUDSerializer(MasterDataCRUDSerializer):

    class Meta(MasterDataCRUDSerializer.Meta):
        model = ProjectType

# 38. Project Status CRUD Serializer
class ProjectStatusCRUDSerializer(MasterDataCRUDSerializer):

    class Meta(MasterDataCRUDSerializer.Meta):
        model = ProjectStatus

# 39. Task Status CRUD Serializer
class TaskStatusCRUDSerializer(MasterDataCRUDSerializer):

    class Meta(MasterDataCRUDSerializer.Meta):
        model = TaskStatus
