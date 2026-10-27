from rest_framework import serializers
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, Client, Project



class FlexibleManagerField(serializers.RelatedField):
    queryset = User.objects.all()

    def to_representation(self, value):
        return value.username if value.username else value.id

    def to_internal_value(self, data):
        if isinstance(data, int):
            try:
                return User.objects.get(pk=data)
            except User.DoesNotExist:
                raise serializers.ValidationError("User with this ID does not exist.")
        elif isinstance(data, str):
            prefix = data.split('@')[0] if '@' in data else data
            try:
                return User.objects.get(
                    Q(username=data) | 
                    Q(email=data) | 
                    Q(username__iexact=prefix) | 
                    Q(email__istartswith=prefix)
                )
            except User.DoesNotExist:
                raise serializers.ValidationError("User with this username or identifier does not exist.")
        raise serializers.ValidationError("Invalid input for assigned_manager.")


# 1. Login Serializer 
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, data):
        email = data['email']
        password = data['password']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or password.")

        if user.status != 'Active':
            raise serializers.ValidationError("User account is inactive.")

        if not user.check_password(password):
            raise serializers.ValidationError("Invalid email or password.")

        refresh = RefreshToken.for_user(user)

        return {
            'message': 'Login successful.',
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }


# 2. Send OTP Serializer 
class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate(self, data):
        email = data['email']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")

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
            except Exception:
                pass

        if len(valid_timestamps) >= 3:
            raise serializers.ValidationError(
                "You have exceeded the maximum number of OTP requests. Please try again after 12 hours."
            )

        valid_timestamps.append(now.isoformat())
        user.otp_request_timestamps = valid_timestamps
        user.save(update_fields=['otp_request_timestamps'])

        return data


# 3. Verify OTP Serializer
class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(max_length=6, required=True)


# 4. Reset Password Serializer
class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(max_length=6, required=True)
    new_password = serializers.CharField(write_only=True, required=True)


# 5. User Read Serializer
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'email', 'username',
            'profiles', 'date_of_birth', 'gender', 'nationality',
            'image', 'blood_group', 'phone', 'permanent_address',
            'current_address', 'emergency_contact_name',
            'emergency_contact_number', 'emergency_contact_relationship',
            'status'
        ]


# 6. User Create Serializer 
class UserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'email', 'username',
            'profiles', 'date_of_birth', 'gender', 'nationality',
            'image', 'blood_group', 'phone', 'permanent_address',
            'current_address', 'emergency_contact_name',
            'emergency_contact_number', 'emergency_contact_relationship',
            'status'
        ]
        extra_kwargs = {
            'first_name': {'required': False, 'allow_blank': True, 'allow_null': True},
            'last_name': {'required': False, 'allow_blank': True, 'allow_null': True},
            'username': {'required': False, 'allow_blank': True, 'allow_null': True},
        }

    def create(self, validated_data):
        email = validated_data.get('email')
        
        if not validated_data.get('status'):
            validated_data['status'] = 'Active'

        email_prefix = email.split('@')[0] if email else "user"
        default_password = f"{email_prefix}@123"

        user = User(**validated_data)
        user.set_password(default_password)
        user.save()
       
        try:
            send_mail(
                subject='Welcome to Our Platform',
                message=(
                    'Hello,\n\n'
                    f'Welcome! Your account has been created successfully.\n'
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


# 7. User Update Serializer
class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'username',
            'profiles', 'date_of_birth', 'gender', 'nationality',
            'image', 'blood_group', 'phone', 'permanent_address',
            'current_address', 'emergency_contact_name',
            'emergency_contact_number', 'emergency_contact_relationship',
            'status'
        ]


# 8. Client Serializer
class ClientSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.first_name', read_only=True)
    modified_by_name = serializers.CharField(source='modified_by.first_name', read_only=True)

    class Meta:
        model = Client
        fields = '__all__'
        read_only_fields = ['created_by', 'modified_by', 'created_at', 'updated_at']


# 9. Project Serializer 
class ProjectSerializer(serializers.ModelSerializer):
    assigned_manager = FlexibleManagerField(required=False, allow_null=True)
    assigned_manager_name = serializers.CharField(source='assigned_manager.first_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.first_name', read_only=True)
    modified_by_name = serializers.CharField(source='modified_by.first_name', read_only=True)

    class Meta:
        model = Project
        fields = '__all__'
        read_only_fields = ['created_by', 'modified_by', 'created_at', 'updated_at']