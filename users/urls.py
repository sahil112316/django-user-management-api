
from django.urls import path

from .views import (
    UserListCreateAPIView,
    UserDetailAPIView,
    UserProfileDetailAPIView,
    ClientListCreateAPIView,
    ClientDetailAPIView,
    ProjectListCreateAPIView,
    ProjectDetailAPIView,
    LoginAPIView,
    SendOTPAPIView,
    VerifyOTPAPIView,
    ForgotPasswordAPIView,
    ResetPasswordAPIView,
    ProfileListAPIView,
    ProfileDetailAPIView,
    ProfileUsersAPIView,
    UserRestoreAPIView,
    ClientRestoreAPIView,
    ProjectRestoreAPIView,
    ProjectTaskListCreateAPIView,
    ProjectTaskDetailAPIView,
    TaskCommentListCreateAPIView,
)

from .exceptions import invalid_api_url


urlpatterns = [

    # User CRUD APIs (User and Client)
    path(
        'users/',
        UserListCreateAPIView.as_view(),
        name='user-list-create'
    ),

    # User Restore APIs
    path(
        'users/restore/',
        UserRestoreAPIView.as_view(),
        name='user-restore'
    ),
    path(
        'users/<int:pk>/restore/',
        UserRestoreAPIView.as_view(),
        name='user-restore-detail'
    ),

    # User Detail APIs
    path(
        'users/<int:pk>/profile/',
        UserProfileDetailAPIView.as_view(),
        name='user-profile-detail'
    ),
    path(
        'users/<int:pk>/',
        UserDetailAPIView.as_view(),
        name='user-detail'
    ),

    # Authentication APIs
    path('auth/login/', LoginAPIView.as_view(), name='login'),
    path('auth/send-otp/', SendOTPAPIView.as_view(), name='send-otp'),
    path('auth/verify-otp/', VerifyOTPAPIView.as_view(), name='verify-otp'),
    path(
        'auth/forgot-password/',
        ForgotPasswordAPIView.as_view(),
        name='forgot-password'
    ),
    path(
        'auth/reset-password/',
        ResetPasswordAPIView.as_view(),
        name='reset-password'
    ),

    # Project Restore API
    path(
        'projects/restore/',
        ProjectRestoreAPIView.as_view(),
        name='project-restore'
    ),

    # Project CRUD APIs
    path(
        'projects/',
        ProjectListCreateAPIView.as_view(),
        name='project-list-create'
    ),
    path(
        'projects/<int:pk>/',
        ProjectDetailAPIView.as_view(),
        name='project-detail'
    ),

    # Project Task APIs
    path(
        'projects/tasks/',
        ProjectTaskListCreateAPIView.as_view(),
        name='project-task-list-create'
    ),
    path(
        'projects/tasks/<int:pk>/',
        ProjectTaskDetailAPIView.as_view(),
        name='project-task-detail'
    ),

    # Task Comment APIs
    path(
        'task-comments/',
        TaskCommentListCreateAPIView.as_view(),
        name='task-comment-list-create'
    ),

    # Profile CRUD APIs
    path(
        'profiles/',
        ProfileListAPIView.as_view(),
        name='profile-list'
    ),
    path(
        'profiles/<str:pk>/',
        ProfileDetailAPIView.as_view(),
        name='profile-detail'
    ),

    path(
        'clients/restore/',
        ClientRestoreAPIView.as_view(),
        name='client-restore'
    ),
    path(
        'clients/<int:pk>/restore/',
        ClientRestoreAPIView.as_view(),
        name='client-restore-detail'
    ),

    path(
        'clients/',
        ClientListCreateAPIView.as_view(),
        name='client-list-create'
    ),
    path(
        'clients/<int:pk>/',
        ClientDetailAPIView.as_view(),
        name='client-detail'
    ),

    path(
        '<path:invalid_path>',
        invalid_api_url,
        name='invalid-api-url'
    ),
]
