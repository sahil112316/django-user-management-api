from rest_framework import serializers
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User


# 1. User Serializer
class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            'id',
            'first_name',
            'last_name',
            'email',
            'username',
            'profiles',
            'date_of_birth',
            'gender',
            'nationality',
            'image',
            'blood_group',
            'phone',
            'permanent_address',
            'current_address',
            'emergency_contact_name',
            'emergency_contact_number',
            'emergency_contact_relationship',
            'status',
        ]


# 2. User Create Serializer
class UserCreateSerializer(serializers.ModelSerializer):

    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'email',
            'username',
            'password',
            'profiles',
            'date_of_birth',
            'gender',
            'nationality',
            'image',
            'blood_group',
            'phone',
            'permanent_address',
            'current_address',
            'emergency_contact_name',
            'emergency_contact_number',
            'emergency_contact_relationship',
            'status',
        ]

    def create(self, validated_data):
        password = validated_data.pop('password')

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        return user


# 3. User Update Serializer
class UserUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'email',
            'username',
            'profiles',
            'date_of_birth',
            'gender',
            'nationality',
            'image',
            'blood_group',
            'phone',
            'permanent_address',
            'current_address',
            'emergency_contact_name',
            'emergency_contact_number',
            'emergency_contact_relationship',
            'status',
        ]


# 4. Login Serializer
class LoginSerializer(serializers.Serializer):

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data['email']
        password = data['password']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                "Invalid email or password."
            )

        if user.status != 'Active':
            raise serializers.ValidationError(
                "User account is inactive."
            )

        authenticated_user = authenticate(
            username=user.username,
            password=password
        )

        if authenticated_user is None:
            raise serializers.ValidationError(
                "Invalid email or password."
            )

        refresh = RefreshToken.for_user(authenticated_user)

        return {
            'message': 'Login successful.',
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }


# 5. Send OTP Serializer
class SendOTPSerializer(serializers.Serializer):

    email = serializers.EmailField()



class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)
    new_password = serializers.CharField(
        write_only=True,
        min_length=8
    )