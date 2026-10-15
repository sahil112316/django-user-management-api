
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
import secrets

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from .models import User, EmailOTP
from .serializers import (
    LoginSerializer,
    SendOTPSerializer,
    UserSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    VerifyOTPSerializer,
    ResetPasswordSerializer,
)


# 1. Create User
class UserListCreateAPIView(generics.ListCreateAPIView):
    queryset = User.objects.filter(status='Active')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UserCreateSerializer
        return UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
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
            context=self.get_serializer_context()
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )


# 2. Retrieve, Update and Soft Delete User
class UserDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_queryset(self):
        if self.request.method in ['PATCH', 'PUT', 'DELETE']:
            return User.objects.all()

        return User.objects.filter(status='Active')

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UserUpdateSerializer
        return UserSerializer

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        user.status = 'Inactive'
        user.save()

        return Response(
            {'message': 'User deactivated successfully.'},
            status=status.HTTP_200_OK
        )


# 3. Login with JWT
class LoginAPIView(APIView):
    permission_classes = [AllowAny]

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

        otp = f"{secrets.randbelow(1000000):06d}"

        EmailOTP.objects.create(
            user=user,
            otp=otp,
            purpose='verification',
            expires_at=timezone.now() + timedelta(minutes=5)
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

        try:
            otp_record = EmailOTP.objects.filter(
                user=user,
                otp=otp,
                purpose='verification',
                expires_at__gt=timezone.now()
            ).latest('id')
        except EmailOTP.DoesNotExist:
            return Response(
                {'message': 'Invalid or expired OTP.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        otp_record.delete()

        return Response(
            {'message': 'OTP verified successfully.'},
            status=status.HTTP_200_OK
        )


# 6. Forgot Password 
class ForgotPasswordAPIView(APIView):
    permission_classes = [AllowAny]

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

        otp = f"{secrets.randbelow(1000000):06d}"

        EmailOTP.objects.create(
            user=user,
            otp=otp,
            purpose='password_reset',
            expires_at=timezone.now() + timedelta(minutes=5)
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

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']

        # Find active user
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

        # Verify password
        try:
            otp_record = EmailOTP.objects.filter(
                user=user,
                otp=otp,
                purpose='password_reset',
                expires_at__gt=timezone.now()
            ).latest('id')
        except EmailOTP.DoesNotExist:
            return Response(
                {'message': 'Invalid or expired password reset OTP.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update password 
        user.set_password(new_password)
        user.save()

        
        otp_record.delete()

        return Response(
            {'message': 'Password reset successfully.'},
            status=status.HTTP_200_OK
        )
