from datetime import timedelta
import secrets

from django.core.mail import send_mail
from django.utils import timezone
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from .models import User
from .serializers import (
    LoginSerializer,
    SendOTPSerializer,
    UserSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    VerifyOTPSerializer,
    ResetPasswordSerializer,
)


# 1. List and Create Users
class UserListCreateAPIView(APIView):
    # Ye line HTML Form wala tab enable kar degi Browsable API me
    serializer_class = UserCreateSerializer

    def get(self, request):
        users = User.objects.filter(status='Active')
        serializer = UserSerializer(
            users,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)

    def post(self, request):
        serializer = UserCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        send_mail(
            subject='Welcome to Our Platform',
            message=(
                f'Hello {user.first_name},\n\n'
                'Welcome! Your account has been created successfully.\n\n'
                'Thank you for joining us.'
            ),
            from_email=None,
            recipient_list=[user.email],
            fail_silently=False,
        )

        response_serializer = UserSerializer(
            user,
            context={'request': request}
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )


# 2. Retrieve, Update and Soft Delete User  
class UserDetailAPIView(APIView):
    # PUT/PATCH ke liye Form enable karne ke liye
    serializer_class = UserUpdateSerializer

    def get(self, request, pk):
        user = get_object_or_404(
            User,
            pk=pk,
            status='Active'
        )
        serializer = UserSerializer(
            user,
            context={'request': request}
        )
        return Response(serializer.data)

    def put(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        serializer = UserUpdateSerializer(
            user,
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            UserSerializer(
                user,
                context={'request': request}
            ).data
        )

    def patch(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        serializer = UserUpdateSerializer(
            user,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            UserSerializer(
                user,
                context={'request': request}
            ).data
        )

    def delete(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user.status = 'Inactive'
        user.save(update_fields=['status'])

        return Response(
            {'message': 'User deactivated successfully.'},
            status=status.HTTP_200_OK
        )


# 3. Login with JWT
class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response(
            serializer.validated_data,
            status=status.HTTP_200_OK
        )


# 4. Send Verification OTP
class SendOTPAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = SendOTPSerializer

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']

        try:
            user = User.objects.get(
                email=email,
                status='Active'
            )
        except User.DoesNotExist:
            return Response(
                {'message': 'Active user not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        otp = f'{secrets.randbelow(1000000):06d}'

        user.otp = otp
        user.otp_purpose = 'verification'
        user.otp_expires_at = timezone.now() + timedelta(minutes=5)
        user.save(
            update_fields=[
                'otp',
                'otp_purpose',
                'otp_expires_at'
            ]
        )

        send_mail(
            subject='Your Verification OTP',
            message=f'Your OTP is {otp}. It expires in 5 minutes.',
            from_email=None,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return Response(
            {'message': 'OTP sent successfully.'},
            status=status.HTTP_200_OK
        )


# 5. Verify OTP
class VerifyOTPAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = VerifyOTPSerializer

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']

        try:
            user = User.objects.get(
                email=email,
                status='Active'
            )
        except User.DoesNotExist:
            return Response(
                {'message': 'Active user not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if (
            user.otp != otp
            or user.otp_purpose != 'verification'
            or user.otp_expires_at is None
            or user.otp_expires_at <= timezone.now()
        ):
            return Response(
                {'message': 'Invalid or expired OTP.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.otp = ''
        user.otp_purpose = ''
        user.otp_expires_at = None
        user.save(
            update_fields=[
                'otp',
                'otp_purpose',
                'otp_expires_at'
            ]
        )

        return Response(
            {'message': 'OTP verified successfully.'},
            status=status.HTTP_200_OK
        )


# 6. Forgot Password
class ForgotPasswordAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = SendOTPSerializer

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']

        try:
            user = User.objects.get(
                email=email,
                status='Active'
            )
        except User.DoesNotExist:
            return Response(
                {'message': 'Active user not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        otp = f'{secrets.randbelow(1000000):06d}'

        user.otp = otp
        user.otp_purpose = 'password_reset'
        user.otp_expires_at = timezone.now() + timedelta(minutes=5)
        user.save(
            update_fields=[
                'otp',
                'otp_purpose',
                'otp_expires_at'
            ]
        )

        send_mail(
            subject='Password Reset OTP',
            message=(
                f'Hello {user.first_name},\n\n'
                f'Your password reset OTP is {otp}.\n'
                'This OTP expires in 5 minutes.\n\n'
                'If you did not request a password reset, '
                'please ignore this email.'
            ),
            from_email=None,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return Response(
            {'message': 'Password reset OTP sent successfully.'},
            status=status.HTTP_200_OK
        )


# 7. Reset Password
class ResetPasswordAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = ResetPasswordSerializer

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']

        try:
            user = User.objects.get(
                email=email,
                status='Active'
            )
        except User.DoesNotExist:
            return Response(
                {'message': 'Active user not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if (
            user.otp != otp
            or user.otp_purpose != 'password_reset'
            or user.otp_expires_at is None
            or user.otp_expires_at <= timezone.now()
        ):
            return Response(
                {'message': 'Invalid or expired password reset OTP.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.otp = ''
        user.otp_purpose = ''
        user.otp_expires_at = None
        user.save()

        return Response(
            {'message': 'Password reset successfully.'},
            status=status.HTTP_200_OK
        )