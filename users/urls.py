from django.urls import path
from .views import (
    UserListCreateAPIView,
    UserDetailAPIView,
    ClientListCreateAPIView,
    ClientDetailAPIView,
    LoginAPIView,
    SendOTPAPIView,
    VerifyOTPAPIView,
    ForgotPasswordAPIView,
    ResetPasswordAPIView,
)

urlpatterns = [
    # User CRUD APIs
    path('users/', UserListCreateAPIView.as_view(), name='user-list-create'),
    path('users/<int:pk>/', UserDetailAPIView.as_view(), name='user-detail'),

    # Login API
    path('auth/login/', LoginAPIView.as_view(), name='login'),

    # Send OTP API
    path('auth/send-otp/', SendOTPAPIView.as_view(), name='send-otp'),

    # Verify OTP API
    path('auth/verify-otp/', VerifyOTPAPIView.as_view(), name='verify-otp'),

    # Forgot Password API
    path('auth/forgot-password/', ForgotPasswordAPIView.as_view(), name='forgot-password'),

    # Reset Password API
    path('auth/reset-password/', ResetPasswordAPIView.as_view(), name='reset-password'),

    # Client CRUD APIs 
    path('clients/', ClientListCreateAPIView.as_view(), name='client-list-create'),
    path('clients/<int:pk>/', ClientDetailAPIView.as_view(), name='client-detail'),
]