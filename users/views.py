from datetime import timedelta
import secrets

from django.core.mail import send_mail
from django.utils import timezone
from django.shortcuts import get_object_or_404

from django.db.models import Q
from django.utils.dateparse import parse_date

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import ValidationError

from .models import (
    User, Client, Project, Profile,
    ProjectTask, TaskComment, get_default_profile,
    ProjectType, ProjectStatus, TaskStatus
)


from .serializers import (
    UserListQuerySerializer,
    ClientListQuerySerializer,
    LoginSerializer,
    SendOTPSerializer,
    UserSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    VerifyOTPSerializer,
    ResetPasswordSerializer,
    ClientSerializer,
    ProjectSerializer,
    ProfileCRUDSerializer,
    ProjectTaskSerializer,
    TaskCommentSerializer,
    ProjectListQuerySerializer,
    ProfileRoleQuerySerializer,
    ProfileDetailActionSerializer,
    ProfileUsersQuerySerializer,
    RestoreIDsSerializer,
    ProjectTaskListQuerySerializer,
    TaskCommentListQuerySerializer,
    UserClientSerializer,
    ProjectTypeCRUDSerializer,
    ProjectStatusCRUDSerializer,
    TaskStatusCRUDSerializer,
)

# 1 Pagination Configuration

class ClientPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100

# 2. User List, Search, Filters, Pagination and Create API

class UserListCreateAPIView(APIView):
    renderer_classes = [JSONRenderer]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = UserCreateSerializer

    def has_user_management_permission(self, request):
        profile = getattr(request.user, 'profile', None)
        role = profile.name if profile else None
        return role in ['Super Admin', 'Admin']

    def get(self, request):

        is_admin = self.has_user_management_permission(request)

        query_serializer = UserListQuerySerializer(
            data=request.query_params
        )

        if not query_serializer.is_valid():
            error = next(iter(query_serializer.errors.values()))[0]
            return Response(
                {'error': str(error)},
                status=status.HTTP_400_BAD_REQUEST
            )

        validated_filters = query_serializer.validated_data

        user_status = validated_filters.get('status', 'Active')
        date_from = validated_filters.get('date_from', '')
        date_to = validated_filters.get('date_to', '')

        # Profile Filter Through Name or ID
        profile = validated_filters.get('profile', '').strip()
        profile_id = validated_filters.get('profile_id')

        if is_admin:

            if profile:
                is_client = profile.lower() == 'client'

                base_users = User.objects.filter(
                    profile__name__iexact=profile
                )

            elif profile_id is not None:
                is_client = Profile.objects.filter(
                    id=profile_id,
                    name__iexact='client'
                ).exists()

                base_users = User.objects.filter(
                    profile_id=profile_id
                )

            else:
                base_users = User.objects.exclude(
                    profile__name__iexact='client'
                )
                is_client = False

            user_profile = getattr(request.user, 'profile', None)

            if user_profile and user_profile.name == 'Admin':
                base_users = base_users.exclude(
                    Q(profile__name__iexact='Super Admin') |
                    Q(created_by__profile__name__iexact='Super Admin')
                )

        else:
            base_users = User.objects.filter(
                id=request.user.id
            )

            user_profile = getattr(request.user, 'profile', None)

            is_client = (
                user_profile and user_profile.name.lower() == 'client'
            )

            if profile:
                base_users = base_users.filter(
                    profile__name__iexact=profile
                )

            if profile_id is not None:
                base_users = base_users.filter(
                    profile_id=profile_id
                )

        total_count = base_users.count()

        active_count = base_users.filter(
            status__iexact='Active'
        ).count()

        inactive_count = base_users.filter(
            status__iexact='Inactive'
        ).count()

        users = base_users.filter(
            status__iexact=user_status
        ).order_by('id')

        # Search Filter
        search = request.query_params.get('search', '').strip()

        if search:
            users = users.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(profile__name__icontains=search) |
                Q(phone__icontains=search)
            )

        # Gender Filter
        gender = request.query_params.get('gender')

        if gender:
            users = users.filter(
                gender__iexact=gender.strip()
            )

        # Blood Group Filter
        blood_group = request.query_params.get('blood_group')

        if blood_group:
            users = users.filter(
                blood_group__iexact=blood_group.strip()
            )

        # Nationality Filter
        nationality = request.query_params.get('nationality')

        if nationality:
            users = users.filter(
                nationality__icontains=nationality.strip()
            )

        # Date of Birth Range Filter
        if date_from:
            users = users.filter(
                date_of_birth__gte=parse_date(date_from)
            )

        if date_to:
            users = users.filter(
                date_of_birth__lte=parse_date(date_to)
            )

        # Check Empty Filter Results
        filter_params = [
            'status',
            'date_from',
            'date_to',
            'profile',
            'profile_id',
            'search',
            'gender',
            'blood_group',
            'nationality'
        ]

        has_filters = any(
            request.query_params.get(param, '').strip()
            for param in filter_params
        )

        if has_filters and not users.exists():
            return Response(
                {
                    'message': 'No users found matching the applied filters.'
                },
                status=status.HTTP_200_OK
            )

        # Pagination
        paginator = ClientPagination()
        paginated_users = paginator.paginate_queryset(users, request)

        serializer_class = (
            UserClientSerializer if is_client else UserSerializer
        )

        serializer = serializer_class(
            paginated_users,
            many=True,
            context={'request': request}
        )

        response = paginator.get_paginated_response(serializer.data)

        if is_client:
            response.data.update({
                'total_clients': total_count,
                'active_clients': active_count,
                'inactive_clients': inactive_count
            })
        else:
            response.data.update({
                'total_users': total_count,
                'active_users': active_count,
                'inactive_users': inactive_count
            })

        return response

    def post(self, request):

        if not self.has_user_management_permission(request):
            return Response(
                {'error': 'Only Super Admin and Admin can create users.'},
                status=status.HTTP_403_FORBIDDEN
            )

        request_data_serializer = UserCreateSerializer()

        try:
            request_data_serializer.validate_request_data(request.data)
        except ValidationError as exc:
            return Response(
                {'error': str(exc.detail[0])},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = UserCreateSerializer(
            data=request.data,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)

        profile = serializer.validated_data.get('profile')

        user_profile = getattr(request.user, 'profile', None)

        if (
            user_profile and user_profile.name == 'Admin' and
            profile and profile.name.lower() == 'super admin'
        ):
            return Response(
                {'error': 'Admin cannot create a Super Admin user.'},
                status=status.HTTP_403_FORBIDDEN
            )

        is_client = (
            profile and profile.name.lower() == 'client'
        )

        user = serializer.save(
            created_by=request.user,
            modified_by=None
        )

        response_serializer = UserCreateSerializer(
            user,
            context={'request': request}
        )

        response_data = response_serializer.data.copy()

        response_data.pop('updated_at', None)

        return Response(
            response_data,
            status=status.HTTP_201_CREATED
        )

#3.User Retrieve, Update, Partial Update and Soft Delete API

class UserDetailAPIView(APIView):
    renderer_classes = [JSONRenderer]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = UserUpdateSerializer

    def has_user_management_permission(self, request):
        profile = getattr(request.user, 'profile', None)
        role = profile.name if profile else None
        return role in ['Super Admin', 'Admin']

    def get_accessible_users(self, request):
        profile = getattr(request.user, 'profile', None)
        role = profile.name if profile else None

        users = User.objects.all()

        if role == 'Admin':
            users = users.exclude(
                Q(profile__name__iexact='Super Admin') |
                Q(created_by__profile__name__iexact='Super Admin')
            )

        return users

    def is_client_user(self, user):
        profile = getattr(user, 'profile', None)

        if profile:
            return profile.name.strip().lower() == 'client'

        return getattr(user, 'is_client', False)

    def get(self, request, pk):

        if (
            not self.has_user_management_permission(request)
            and request.user.pk != pk
        ):
            return Response(
                {'error': 'You can only access your own data. Admin and Super Admin have permission to access all users data.'},
                status=status.HTTP_403_FORBIDDEN
            )

        user = get_object_or_404(
            self.get_accessible_users(request),
            pk=pk,
            status='Active'
        )

        serializer_class = (
            UserClientSerializer if self.is_client_user(user)
            else UserSerializer
        )

        serializer = serializer_class(
            user,
            context={'request': request}
        )

        return Response(serializer.data)

    # Update Active User / Client (PUT)
    def put(self, request, pk):

        # Validate Action
        if (
            'action' in request.data
            and request.data.get('action') != 'delete'
        ):
            return Response(
                {'error': 'Invalid action. Only "delete" is allowed.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if request.data.get('action') == 'delete':

            if not self.has_user_management_permission(request):
                return Response(
                    {'error': 'Only Super Admin and Admin can delete users.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            user = get_object_or_404(
                self.get_accessible_users(request),
                pk=pk,
                status='Active'
            )

            if self.is_client_user(user):
                user.status = 'Inactive'
                user.modified_by = request.user

                user.save(update_fields=[
                    'status',
                    'modified_by',
                    'updated_at'
                ])

                return Response(
                    {
                        'message': 'Client deleted successfully.',
                        'id': user.id,
                        'status': user.status
                    },
                    status=status.HTTP_200_OK
                )

            # User Soft Delete
            user.status = 'Inactive'
            user.is_deleted = True
            user.modified_by = request.user

            user.save(update_fields=[
                'status',
                'is_deleted',
                'modified_by',
                'updated_at'
            ])

            return Response(
                {
                    'message': 'User deleted successfully.',
                    'id': user.id,
                    'status': user.status,
                    'is_deleted': user.is_deleted
                },
                status=status.HTTP_200_OK
            )

        request_data_serializer = UserUpdateSerializer()

        try:
            request_data_serializer.validate_request_data(request.data)
        except ValidationError as exc:
            return Response(
                {'error': exc.detail},
                status=status.HTTP_400_BAD_REQUEST
            )

        if (
            not self.has_user_management_permission(request)
            and request.user.pk != pk
        ):
            return Response(
                {'error': 'You can only update your own data.'},
                status=status.HTTP_403_FORBIDDEN
            )

        user = get_object_or_404(
            self.get_accessible_users(request),
            pk=pk,
            status='Active'
        )

        if self.has_user_management_permission(request):
            serializer_class = UserUpdateSerializer
        else:
            serializer_class = (
                UserClientSerializer if self.is_client_user(user)
                else UserUpdateSerializer
            )

        serializer = serializer_class(
            user,
            data=request.data,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)
        serializer.save(modified_by=request.user)

        response_serializer_class = (
            UserClientSerializer if self.is_client_user(user)
            else UserSerializer
        )

        return Response(
            response_serializer_class(
                user,
                context={'request': request}
            ).data
        )

    # Update Active User / Client (PATCH)
    def patch(self, request, pk):

        if (
            not self.has_user_management_permission(request)
            and request.user.pk != pk
        ):
            return Response(
                {'error': 'You can only update your own data.'},
                status=status.HTTP_403_FORBIDDEN
            )

        user = get_object_or_404(
            self.get_accessible_users(request),
            pk=pk,
            status='Active'
        )

        if self.has_user_management_permission(request):
            serializer_class = UserUpdateSerializer
        else:
            serializer_class = (
                UserClientSerializer if self.is_client_user(user)
                else UserUpdateSerializer
            )

        serializer = serializer_class(
            user,
            data=request.data,
            partial=True,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)
        serializer.save(modified_by=request.user)

        response_serializer_class = (
            UserClientSerializer if self.is_client_user(user)
            else UserSerializer
        )

        return Response(
            response_serializer_class(
                user,
                context={'request': request}
            ).data
        )


# 4. User JSON Profile Configuration API

class UserProfileDetailAPIView(APIView):
    renderer_classes = [JSONRenderer]
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        return Response(
            {'profiles': user.profiles},
            status=status.HTTP_200_OK
        )

    def put(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        profiles_data = request.data.get('profiles', request.data)
        user.profiles = profiles_data
        user.save(update_fields=['profiles'])
        return Response(
            {'profiles': user.profiles},
            status=status.HTTP_200_OK
        )

    def patch(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        current_profiles = (
            user.profiles if isinstance(user.profiles, dict) else {}
        )
        incoming_profiles = request.data.get('profiles', request.data)

        if isinstance(incoming_profiles, dict):
            current_profiles.update(incoming_profiles)

        user.profiles = current_profiles
        user.save(update_fields=['profiles'])
        return Response(
            {'profiles': user.profiles},
            status=status.HTTP_200_OK
        )

    def delete(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user.profiles = get_default_profile()
        user.save(update_fields=['profiles'])
        return Response(
            {'message': 'User profile reset/hard deleted successfully.'},
            status=status.HTTP_200_OK
        )

# 5. User Login and JWT Authentication API

class LoginAPIView(APIView):
    renderer_classes = [JSONRenderer]
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            serializer.validated_data,
            status=status.HTTP_200_OK
        )

# 6.Send Verification OTP API

class SendOTPAPIView(APIView):
    renderer_classes = [JSONRenderer]
    permission_classes = [AllowAny]
    serializer_class = SendOTPSerializer

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)

        if not serializer.is_valid():
            if 'active_user_not_found' in serializer.errors:
                return Response(
                    {'message': 'Active user not found.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']

        otp = f'{secrets.randbelow(1000000):06d}'
        user.otp = otp
        user.is_otp_used = False
        user.otp_expires_at = timezone.now() + timedelta(minutes=5)
        user.save(
            update_fields=['otp', 'is_otp_used', 'otp_expires_at']
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

# 7. Verify OTP API

class VerifyOTPAPIView(APIView):
    renderer_classes = [JSONRenderer]
    permission_classes = [AllowAny]
    serializer_class = VerifyOTPSerializer

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)

        if not serializer.is_valid():
            errors = serializer.errors

            if 'active_user_not_found' in errors:
                return Response(
                    {'message': 'Active user not found.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            if 'invalid_otp' in errors:
                return Response(
                    {'message': 'Invalid or expired OTP.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']

        user.is_otp_used = True
        user.otp = ''
        user.otp_expires_at = None
        user.save(
            update_fields=['otp', 'is_otp_used', 'otp_expires_at']
        )

        return Response(
            {'message': 'OTP verified successfully.'},
            status=status.HTTP_200_OK
        )

# 8. Forgot Password and Send OTP API

class ForgotPasswordAPIView(APIView):
    renderer_classes = [JSONRenderer]
    permission_classes = [AllowAny]
    serializer_class = SendOTPSerializer

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)

        if not serializer.is_valid():
            if 'active_user_not_found' in serializer.errors:
                return Response(
                    {'message': 'Active user not found.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']

        otp = f'{secrets.randbelow(1000000):06d}'
        user.otp = otp
        user.is_otp_used = False
        user.otp_expires_at = timezone.now() + timedelta(minutes=5)
        user.save(
            update_fields=['otp', 'is_otp_used', 'otp_expires_at']
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

# 9. Reset Password API

class ResetPasswordAPIView(APIView):
    renderer_classes = [JSONRenderer]
    permission_classes = [AllowAny]
    serializer_class = ResetPasswordSerializer

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)

        if not serializer.is_valid():
            errors = serializer.errors

            if 'active_user_not_found' in errors:
                return Response(
                    {'message': 'Active user not found.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            if 'invalid_otp' in errors:
                return Response(
                    {'message': 'Invalid or expired password reset OTP.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        new_password = serializer.validated_data['new_password']

        user.set_password(new_password)
        user.is_otp_used = True
        user.otp = ''
        user.otp_expires_at = None
        user.save()

        return Response(
            {'message': 'Password reset successfully.'},
            status=status.HTTP_200_OK
        )

# 10. Client List, Search, Filters, Pagination and Create API

class ClientListCreateAPIView(APIView):
    renderer_classes = [JSONRenderer]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ClientSerializer

    # Get Clients
    def get(self, request):

        # Status and Date Query Validation
        query_serializer = ClientListQuerySerializer(
            data=request.query_params
        )

        if not query_serializer.is_valid():
            error = next(iter(query_serializer.errors.values()))[0]
            return Response(
                {'error': str(error)},
                status=status.HTTP_400_BAD_REQUEST
            )

        validated_filters = query_serializer.validated_data

        client_status = validated_filters.get('status', 'Active')
        date_from = validated_filters.get('date_from', '')
        date_to = validated_filters.get('date_to', '')

        clients = Client.objects.filter(
            status__iexact=client_status
        ).order_by('created_at')

        # Search Filter
        search = request.query_params.get('search', '').strip()

        if search:
            clients = clients.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email_id__icontains=search) |
                Q(contact_no__icontains=search) |
                Q(country__icontains=search) |
                Q(address__icontains=search)
            )

        # Country Filter
        country = request.query_params.get('country', '').strip()

        if country:
            clients = clients.filter(
                country__icontains=country
            )

        # Created Date Range Filter
        if date_from:
            clients = clients.filter(
                created_at__date__gte=parse_date(date_from)
            )

        if date_to:
            clients = clients.filter(
                created_at__date__lte=parse_date(date_to)
            )

        # Pagination
        paginator = ClientPagination()

        paginated_clients = paginator.paginate_queryset(
            clients,
            request
        )

        serializer = ClientSerializer(
            paginated_clients,
            many=True,
            context={'request': request}
        )

        return paginator.get_paginated_response(serializer.data)

    # Create Client
    def post(self, request):

        serializer = ClientSerializer(
            data=request.data,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)

        client = serializer.save(
            created_by=request.user,
            modified_by=request.user
        )

        return Response(
            ClientSerializer(
                client,
                context={'request': request}
            ).data,
            status=status.HTTP_201_CREATED
        )

# 11. Retrieve, Update and Soft Delete Client API

class ClientDetailAPIView(APIView):
    renderer_classes = [JSONRenderer]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ClientSerializer

    def get(self, request, pk):
        client = get_object_or_404(Client, pk=pk, status='Active')
        serializer = ClientSerializer(
            client,
            context={'request': request}
        )
        return Response(serializer.data)

    def put(self, request, pk):
        client = get_object_or_404(Client, pk=pk)

        if request.data.get('action') == 'delete':
            client.status = 'Inactive'
            client.save(update_fields=['status'])

            return Response(
                {
                    'message': 'Client deleted successfully.',
                    'id': client.id,
                    'status': client.status
                },
                status=status.HTTP_200_OK
            )

        serializer = ClientSerializer(
            client,
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated else None
        serializer.save(modified_by=user)
        return Response(serializer.data)

    def patch(self, request, pk):
        client = get_object_or_404(Client, pk=pk)
        serializer = ClientSerializer(
            client,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated else None
        serializer.save(modified_by=user)
        return Response(serializer.data)

#12. Project List, Search, Filters, Pagination and Create API


class ProjectListCreateAPIView(APIView):
    renderer_classes = [JSONRenderer]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    serializer_class = ProjectSerializer

    def get(self, request):

        # Query Parameter Validation
        query_serializer = ProjectListQuerySerializer(
            data=request.query_params
        )

        if not query_serializer.is_valid():
            errors = query_serializer.errors

            if (
                'client_id' in errors
                and 'Client does not exist.' in str(errors['client_id'])
            ):
                return Response(
                    {'error': 'Client does not exist.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            if (
                'manager_id' in errors
                and 'Manager does not exist.' in str(errors['manager_id'])
            ):
                return Response(
                    {'error': 'Manager does not exist.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            error = next(iter(errors.values()))[0]

            return Response(
                {'error': str(error)},
                status=status.HTTP_400_BAD_REQUEST
            )

        validated_filters = query_serializer.validated_data

        # 1. Status Filter
        project_record_status = validated_filters.get(
            'status', 'Active'
        )

        projects = Project.objects.filter(
            status__iexact=project_record_status
        ).order_by('id')

        # Role-Based Project Access
        user = request.user
        role = user.profile.name if user.profile else ''

        if role == 'Super Admin':
            pass

        elif role == 'Admin':
            projects = projects.exclude(
                created_by__profile__name__iexact='Super Admin'
            )

        elif role == 'Manager':
            projects = projects.filter(
                assigned_manager=user
            )

        elif role == 'Team Leader':
            projects = projects.filter(
                team_leaders=user
            ).distinct()

            if not projects.exists():
                return Response(
                    {
                        'message': 'No projects are assigned to you.',
                        'count': 0,
                        'results': []
                    },
                    status=status.HTTP_200_OK
                )

        else:
            return Response(
                {
                    'message': 'No projects are assigned to you. Projects are assigned only to Managers.',
                    'count': 0,
                    'results': []
                },
                status=status.HTTP_200_OK
            )

        # 2. Search Filter
        search = request.query_params.get('search', '').strip()

        if search:
            for word in search.split():
                projects = projects.filter(
                    Q(project_title__icontains=word) |
                    Q(project_type_master__name__icontains=word) |
                    Q(description__icontains=word) |
                    Q(client__first_name__icontains=word) |
                    Q(client__last_name__icontains=word) |
                    Q(client__email_id__icontains=word) |
                    Q(assigned_manager__first_name__icontains=word) |
                    Q(assigned_manager__last_name__icontains=word) |
                    Q(assigned_manager__username__icontains=word) |
                    Q(assigned_manager__email__icontains=word)
                )

        # 3. Project Title Filter
        project_title = request.query_params.get(
            'project_title', ''
        ).strip()

        if project_title:
            projects = projects.filter(
                project_title__icontains=project_title
            )

        # 4. Project Type Filter
        project_type = request.query_params.get(
            'project_type', ''
        ).strip()

        if project_type:
            projects = projects.filter(
                project_type_master__name__icontains=project_type
            )

        # 5. Description Filter
        description = request.query_params.get(
            'description', ''
        ).strip()

        if description:
            projects = projects.filter(
                description__icontains=description
            )

        # 6. Project Status Filter
        project_status = request.query_params.get(
            'project_status', ''
        ).strip()

        if project_status:
            projects = projects.filter(
                project_status_master__name__iexact=project_status
            )

        # 7. Client ID Filter
        client_id = validated_filters.get('client_id', '')

        if client_id:
            projects = projects.filter(
                client_id=int(client_id)
            )

        # 8. Client First Name, Last Name and Email Filters
        client_first_name = request.query_params.get(
            'client_first_name', ''
        ).strip()

        client_last_name = request.query_params.get(
            'client_last_name', ''
        ).strip()

        client_email = request.query_params.get(
            'client_email', ''
        ).strip()

        if client_first_name:
            projects = projects.filter(
                client__first_name__icontains=client_first_name
            )

        if client_last_name:
            projects = projects.filter(
                client__last_name__icontains=client_last_name
            )

        if client_email:
            projects = projects.filter(
                client__email_id__icontains=client_email
            )

        # 9. Manager ID Filter
        manager_id = validated_filters.get('manager_id', '')

        if manager_id:
            projects = projects.filter(
                assigned_manager_id=int(manager_id)
            )

        # 10. Manager Details and Role Filters
        manager_first_name = request.query_params.get(
            'manager_first_name', ''
        ).strip()

        manager_last_name = request.query_params.get(
            'manager_last_name', ''
        ).strip()

        manager_username = request.query_params.get(
            'manager_username', ''
        ).strip()

        manager_email = request.query_params.get(
            'manager_email', ''
        ).strip()

        manager_role = request.query_params.get(
            'manager_role', ''
        ).strip()

        if manager_role:
            projects = projects.filter(
                assigned_manager__profile__name__icontains=manager_role
            )

        if manager_first_name:
            projects = projects.filter(
                assigned_manager__first_name__icontains=manager_first_name
            )

        if manager_last_name:
            projects = projects.filter(
                assigned_manager__last_name__icontains=manager_last_name
            )

        if manager_username:
            projects = projects.filter(
                assigned_manager__username__icontains=manager_username
            )

        if manager_email:
            projects = projects.filter(
                assigned_manager__email__icontains=manager_email
            )

        # 11. Completion Date From
        date_from = validated_filters.get('date_from', '')

        if date_from:
            projects = projects.filter(
                date_of_completion__gte=parse_date(date_from)
            )

        # 12. Completion Date To
        date_to = validated_filters.get('date_to', '')

        if date_to:
            projects = projects.filter(
                date_of_completion__lte=parse_date(date_to)
            )

        # 13. Creation Date From
        created_from = validated_filters.get('created_from', '')

        if created_from:
            projects = projects.filter(
                created_at__date__gte=parse_date(created_from)
            )

        # 14. Creation Date To
        created_to = validated_filters.get('created_to', '')

        if created_to:
            projects = projects.filter(
                created_at__date__lte=parse_date(created_to)
            )

        paginator = ClientPagination()

        paginated_projects = paginator.paginate_queryset(
            projects,
            request
        )

        serializer = ProjectSerializer(
            paginated_projects,
            many=True,
            context={'request': request}
        )

        return paginator.get_paginated_response(serializer.data)

    def post(self, request):

        user = request.user
        role = user.profile.name if user.profile else ''

        if role not in ['Super Admin', 'Admin']:
            return Response(
                {
                    'error': 'Only Admin and Super Admin have permission to create a project.'
                },
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ProjectSerializer(
            data=request.data,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)

        project = serializer.save(
            created_by=user,
            modified_by=None,
            status='Active'
        )

        response_serializer = ProjectSerializer(
            project,
            context={
                'request': request,
                'is_create_response': True
            }
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )


# 13.Project Retrieve, Update, Partial Update and Soft Delete API



class ProjectDetailAPIView(APIView):
    renderer_classes = [JSONRenderer]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    serializer_class = ProjectSerializer

    def get_user_projects(self, request):

        projects = Project.objects.all()

        user = request.user
        role = user.profile.name if user.profile else ''

        if role == 'Super Admin':
            pass

        elif role == 'Admin':
            projects = projects.exclude(
                created_by__profile__name__iexact='Super Admin'
            )

        elif role == 'Manager':
            projects = projects.filter(
                assigned_manager=user
            )

        elif role == 'Developer':
            projects = projects.filter(
                tasks__developers=user
            ).distinct()

        elif role == 'Team Leader':
            projects = projects.filter(
                team_leaders=user
            ).distinct()

        elif role == 'Client' or user.is_client:
            projects = projects.filter(
                user_client=user
            )

        else:
            projects = projects.none()

        return projects

    def get(self, request, pk):
        project = get_object_or_404(
            self.get_user_projects(request),
            pk=pk
        )

        serializer = ProjectSerializer(
            project,
            context={'request': request}
        )

        return Response(serializer.data)

    def put(self, request, pk):

        user = request.user
        role = user.profile.name if user.profile else ''

        if role == 'Manager':

            if request.data.get('action') == 'delete':
                return Response(
                    {
                        'error': 'Only Admin and Super Admin can delete a project.'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            if 'type' in request.data:
                return Response(
                    {
                        'type': 'Only Admin and Super Admin can change the project type.'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            if not request.data or not set(request.data.keys()).issubset({'team_leaders', 'status'}):
                return Response(
                    {
                        'error': 'Managers can only update project status and assign Team Leaders to their own projects.'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            project = get_object_or_404(
                Project.objects.filter(assigned_manager=user),
                pk=pk
            )

            serializer = ProjectSerializer(
                project,
                data=request.data,
                partial=True,
                context={'request': request}
            )

            serializer.is_valid(raise_exception=True)
            serializer.save(modified_by=user)

            return Response(serializer.data)

        if role not in ['Super Admin', 'Admin']:
            return Response(
                {
                    'error': 'Only Admin and Super Admin can update or delete a project. You do not have permission to perform this action.'
                },
                status=status.HTTP_403_FORBIDDEN
            )

        if request.data.get('action') == 'delete':
            project = get_object_or_404(
                self.get_user_projects(request),
                pk=pk,
                status='Active',
                is_deleted=False
            )

            project.status = 'Inactive'
            project.is_deleted = True

            project.save(update_fields=[
                'status',
                'is_deleted'
            ])

            return Response(
                {
                    "message": "Project deleted successfully.",
                    "id": project.id,
                    "status": project.status,
                    "is_deleted": project.is_deleted
                },
                status=status.HTTP_200_OK
            )

        project = get_object_or_404(
            self.get_user_projects(request),
            pk=pk
        )

        serializer = ProjectSerializer(
            project,
            data=request.data,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)

        user = request.user if request.user.is_authenticated else None

        serializer.save(modified_by=user)

        return Response(serializer.data)

    def patch(self, request, pk):

        user = request.user
        role = user.profile.name if user.profile else ''

        if role == 'Manager':

            if 'type' in request.data:
                return Response(
                    {
                        'type': 'Only Admin and Super Admin can change the project type.'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            if not request.data or not set(request.data.keys()).issubset({'team_leaders', 'status'}):
                return Response(
                    {
                        'error': 'Managers can only update project status and assign Team Leaders to their own projects.'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            project = get_object_or_404(
                Project.objects.filter(assigned_manager=user),
                pk=pk
            )

            serializer = ProjectSerializer(
                project,
                data=request.data,
                partial=True,
                context={'request': request}
            )

            serializer.is_valid(raise_exception=True)
            serializer.save(modified_by=user)

            return Response(serializer.data)

        if role not in ['Super Admin', 'Admin']:
            return Response(
                {
                    'error': 'Only Admin and Super Admin can update a project. You do not have permission to perform this action.'
                },
                status=status.HTTP_403_FORBIDDEN
            )

        project = get_object_or_404(
            self.get_user_projects(request),
            pk=pk
        )

        serializer = ProjectSerializer(
            project,
            data=request.data,
            partial=True,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)

        user = request.user if request.user.is_authenticated else None

        serializer.save(modified_by=user)

        return Response(serializer.data)





# 14. Profile List and Create API

class ProfileListAPIView(APIView):
    renderer_classes = [JSONRenderer]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def has_profile_management_permission(self, request):
        profile = getattr(request.user, 'profile', None)
        role = profile.name if profile else ''
        return role in ['Admin', 'Super Admin']

    def get(self, request):

        if not self.has_profile_management_permission(request):
            return Response(
                {
                    'error': 'Only Admin and Super Admin have permission to access profiles.'
                },
                status=status.HTTP_403_FORBIDDEN
            )

        query_serializer = ProfileRoleQuerySerializer(
            data=request.query_params
        )

        if not query_serializer.is_valid():
            return Response(
                {"detail": "Not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        profile = query_serializer.validated_data.get('profile')

        if profile:
            users = profile.users.filter(
                status='Active'
            ).order_by('id')

            serializer = UserSerializer(
                users,
                many=True,
                context={'request': request}
            )

            return Response(
                {
                    "profile_id": profile.id,
                    "profile_name": profile.name,
                    "total_users": users.count(),
                    "users": serializer.data
                },
                status=status.HTTP_200_OK
            )

        profiles = Profile.objects.all().order_by('id')

        serializer = ProfileCRUDSerializer(
            profiles,
            many=True
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def post(self, request):

        if not self.has_profile_management_permission(request):
            return Response(
                {
                    'error': 'Only Admin and Super Admin have permission to create a profile.'
                },
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ProfileCRUDSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )

#15. Profile Retrieve, Update, Partial Update and Permanent Delete API

class ProfileDetailAPIView(APIView):

    renderer_classes = [JSONRenderer]
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_profile(self, pk, action):

        serializer = ProfileDetailActionSerializer(
            data={'pk': pk},
            context={'action': action}
        )

        if not serializer.is_valid():

            errors = serializer.errors

            if 'default_profile' in errors:
                message = str(errors['default_profile'][0])

                return None, Response(
                    {"message": message},
                    status=status.HTTP_403_FORBIDDEN
                )

            return None, Response(
                {"error": "Invalid profile ID or profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        return serializer.validated_data['profile'], None

    def get(self, request, pk):

        profile, error_response = self.get_profile(pk, 'get')

        if error_response:
            return error_response

        serializer = ProfileCRUDSerializer(profile)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def put(self, request, pk):

        profile, error_response = self.get_profile(pk, 'put')

        if error_response:
            return error_response

        serializer = ProfileCRUDSerializer(
            profile,
            data=request.data
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def patch(self, request, pk):

        profile, error_response = self.get_profile(pk, 'patch')

        if error_response:
            return error_response

        serializer = ProfileCRUDSerializer(
            profile,
            data=request.data,
            partial=True
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def delete(self, request, pk):

        profile, error_response = self.get_profile(pk, 'delete')

        if error_response:
            return error_response

        try:
            profile.delete()

        except ProtectedError:
            return Response(
                {"message": "Default profiles cannot be deleted."},
                status=status.HTTP_403_FORBIDDEN
            )

        return Response(
            {"message": "Profile deleted successfully."},
            status=status.HTTP_200_OK
        )

# 16 Get Users by Profile API

class ProfileUsersAPIView(APIView):

    renderer_classes = [JSONRenderer]
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):

        query_serializer = ProfileUsersQuerySerializer(
            data=request.query_params
        )

        if not query_serializer.is_valid():

            errors = query_serializer.errors

            if 'role' in errors and str(errors['role'][0]) == 'Please provide role parameter.':
                return Response(
                    {"error": "Please provide role parameter."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response(
                {"detail": "Not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        profile = query_serializer.validated_data['role']

        users = profile.users.filter(
            status='Active'
        ).order_by('id')

        serializer = UserSerializer(
            users,
            many=True,
            context={'request': request}
        )

        return Response(
            {
                "profile_id": profile.id,
                "profile_name": profile.name,
                "total_users": users.count(),
                "users": serializer.data
            },
            status=status.HTTP_200_OK
        )

# 17. Restore Inactive Users API

class UserRestoreAPIView(APIView):

    renderer_classes = [JSONRenderer]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):

        if pk is not None:

            user = User.objects.filter(pk=pk).first()

            if user is None:
                return Response(
                    {"error": "User not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

            if user.status == 'Active' and not user.is_deleted:
                return Response(
                    {"message": "User is already active."},
                    status=status.HTTP_200_OK
                )

            user.status = 'Active'
            user.is_deleted = False

            user.save(update_fields=[
                'status',
                'is_deleted',
                'updated_at'
            ])

            return Response(
                {
                    "message": "User restored successfully.",
                    "id": user.id,
                    "status": user.status
                },
                status=status.HTTP_200_OK
            )

        query_serializer = RestoreIDsSerializer(data=request.data)

        if not query_serializer.is_valid():
            return Response(
                {"error": "Valid User IDs list is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_ids = query_serializer.validated_data['ids']

        users = User.objects.filter(
            id__in=user_ids
        ).filter(
            Q(status='Inactive') | Q(is_deleted=True)
        )

        if not users.exists():
            return Response(
                {"error": "No inactive users found for the provided IDs."},
                status=status.HTTP_404_NOT_FOUND
            )

        restored_count = users.update(
            status='Active',
            is_deleted=False
        )

        return Response(
            {
                "message": "Users restored successfully.",
                "restored_count": restored_count
            },
            status=status.HTTP_200_OK
        )

# 18. Restore Inactive Clients API

class ClientRestoreAPIView(APIView):

    renderer_classes = [JSONRenderer]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):

        if pk is not None:

            client = Client.objects.filter(pk=pk).first()

            if client is None:
                return Response(
                    {"error": "Client not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

            if client.status == 'Active':
                return Response(
                    {"message": "Client is already active."},
                    status=status.HTTP_200_OK
                )

            client.status = 'Active'
            client.save(update_fields=['status'])

            return Response(
                {
                    "message": "Client restored successfully.",
                    "id": client.id,
                    "status": client.status
                },
                status=status.HTTP_200_OK
            )

        query_serializer = RestoreIDsSerializer(data=request.data)

        if not query_serializer.is_valid():
            return Response(
                {"error": "Valid Client IDs list is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        client_ids = query_serializer.validated_data['ids']

        clients = Client.objects.filter(
            id__in=client_ids,
            status='Inactive'
        )

        if not clients.exists():
            return Response(
                {"error": "No inactive clients found for the provided IDs."},
                status=status.HTTP_404_NOT_FOUND
            )

        restored_count = clients.update(status='Active')

        return Response(
            {
                "message": "Clients restored successfully.",
                "restored_count": restored_count
            },
            status=status.HTTP_200_OK
        )

# 19. Restore Inactive Projects API

class ProjectRestoreAPIView(APIView):

    renderer_classes = [JSONRenderer]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):

        query_serializer = RestoreIDsSerializer(data=request.data)

        if not query_serializer.is_valid():
            return Response(
                {"error": "Valid Project IDs list is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        project_ids = query_serializer.validated_data['ids']

        projects = Project.objects.filter(
            id__in=project_ids,
            is_deleted=True
        )

        if not projects.exists():
            return Response(
                {"error": "No deleted projects found for the provided IDs."},
                status=status.HTTP_404_NOT_FOUND
            )

        restored_count = projects.update(
            status='Active',
            is_deleted=False,
            deleted_at=None,
            deleted_by=None
        )

        return Response(
            {
                "message": "Projects restored successfully.",
                "restored_count": restored_count
            },
            status=status.HTTP_200_OK
        )

# 20 Project Task List, Search, Filter and Create API


class ProjectTaskListCreateAPIView(APIView):

    renderer_classes = [JSONRenderer]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ProjectTaskSerializer

    def get(self, request):

        tasks = ProjectTask.objects.select_related(
            'project', 'created_by', 'modified_by'
        ).prefetch_related(
            'developers',
            'team_leader'
        ).order_by('id')

        user = request.user
        role = user.profile.name if user.profile else ''

        if role == 'Super Admin':
            pass

        elif role == 'Admin':
            tasks = tasks.exclude(
                created_by__profile__name__iexact='Super Admin'
            )

        elif role == 'Manager':
            tasks = tasks.filter(
                project__assigned_manager=user
            )

        elif role == 'Developer':
            tasks = tasks.filter(
                developers=user
            )

        elif role == 'Team Leader':
            tasks = tasks.filter(
                team_leader=user
            )

        else:
            return Response(
                {
                    'error': 'You do not have permission to view tasks.'
                },
                status=status.HTTP_403_FORBIDDEN
            )

        search = request.query_params.get('search', '').strip()

        if search:
            tasks = tasks.filter(
                Q(task_title__icontains=search)
            )

        query_serializer = ProjectTaskListQuerySerializer(
            data=request.query_params
        )

        if not query_serializer.is_valid():
            errors = query_serializer.errors

            if 'project_id' in errors:
                return Response(
                    {'error': 'Invalid project_id.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if 'developer_id' in errors:
                return Response(
                    {'error': 'Invalid developer_id.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            error = next(iter(errors.values()))[0]

            return Response(
                {'error': str(error)},
                status=status.HTTP_400_BAD_REQUEST
            )

        project_id = query_serializer.validated_data.get(
            'project_id', ''
        )

        if project_id:
            tasks = tasks.filter(project_id=int(project_id))

        task_status = request.query_params.get(
            'task_status', ''
        ).strip()

        if task_status:
            tasks = tasks.filter(
                task_status_master__name__iexact=task_status
            )

        developer_id = query_serializer.validated_data.get(
            'developer_id', ''
        )

        if developer_id:
            tasks = tasks.filter(
                developers__id=int(developer_id)
            )

        paginator = ClientPagination()
        paginated_tasks = paginator.paginate_queryset(tasks, request)

        serializer = ProjectTaskSerializer(
            paginated_tasks,
            many=True,
            context={'request': request}
        )

        return paginator.get_paginated_response(serializer.data)

    def post(self, request):

        user = request.user
        role = user.profile.name if user.profile else ''

        allowed_roles = [
            'Super Admin',
            'Admin',
            'Manager',
            'Team Leader'
        ]

        if role not in allowed_roles:
            return Response(
                {
                    'error': 'You do not have permission to create tasks. Only Super Admin, Admin, Manager and Team Leader can create tasks.'
                },
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ProjectTaskSerializer(
            data=request.data,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)

        if (
            role == 'Team Leader'
            and 'team_leader' in serializer.validated_data
        ):
            return Response(
                {
                    'error': 'Team Leaders can assign Developers only.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        project = serializer.validated_data.get('project')

        if role == 'Manager':
            if project.assigned_manager_id != user.id:
                return Response(
                    {
                        'error': 'You can create tasks only in your assigned projects.'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

        elif role == 'Team Leader':
            if not project.team_leaders.filter(id=user.id).exists():
                return Response(
                    {
                        'error': 'You can create tasks only in projects assigned to you.'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

        task = serializer.save(
            created_by=request.user,
            modified_by=None
        )

        response_serializer = ProjectTaskSerializer(
            task,
            context={
                'request': request,
                'is_create_response': True
            }
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )


# 21. Project Task Detail API


class ProjectTaskDetailAPIView(APIView):

    renderer_classes = [JSONRenderer]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ProjectTaskSerializer

    def get_user_tasks(self, request):

        tasks = ProjectTask.objects.select_related(
            'project', 'created_by', 'modified_by'
        ).prefetch_related(
            'developers', 'team_leader'
        )

        user = request.user
        role = user.profile.name if user.profile else ''

        if role == 'Super Admin':
            pass

        elif role == 'Admin':
            tasks = tasks.exclude(
                created_by__profile__name__iexact='Super Admin'
            )

        elif role == 'Manager':
            tasks = tasks.filter(
                project__assigned_manager=user
            )

        elif role == 'Developer':
            tasks = tasks.filter(
                developers=user
            )

        elif role == 'Team Leader':
            tasks = tasks.filter(
                team_leader=user
            )

        else:
            tasks = tasks.none()

        return tasks.distinct()

    def get_editable_task(self, request, pk):

        user = request.user
        role = user.profile.name if user.profile else ''

        task = get_object_or_404(
            ProjectTask.objects.select_related(
                'project', 'created_by'
            ),
            pk=pk
        )

        if role == 'Super Admin':
            return task

        if role == 'Admin':
            if (
                task.created_by
                and task.created_by.profile
                and task.created_by.profile.name.lower() == 'super admin'
            ):
                return None

            return task

        if role == 'Manager':
            if (
                task.project.assigned_manager_id == user.id
                and (
                    task.created_by_id == user.id
                    or (
                        task.created_by
                        and task.created_by.profile
                        and task.created_by.profile.name == 'Team Leader'
                    )
                )
            ):
                return task

            return None

        if role == 'Team Leader':
            if (
                task.created_by_id == user.id
                and task.project.team_leaders.filter(
                    id=user.id
                ).exists()
            ):
                return task

            return None

        return None

    def get(self, request, pk):

        user = request.user
        role = user.profile.name if user.profile else ''

        if role not in [
            'Super Admin',
            'Admin',
            'Manager',
            'Team Leader',
            'Developer'
        ]:
            return Response(
                {
                    'error': 'You do not have permission to view tasks.'
                },
                status=status.HTTP_403_FORBIDDEN
            )

        task = get_object_or_404(
            self.get_user_tasks(request),
            pk=pk
        )

        serializer = ProjectTaskSerializer(
            task,
            context={'request': request}
        )

        return Response(serializer.data)

    def put(self, request, pk):

        user = request.user
        role = user.profile.name if user.profile else ''

        task = self.get_editable_task(request, pk)

        if not task:
            return Response(
                {
                    'error': 'You do not have permission to update this task.'
                },
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ProjectTaskSerializer(
            task,
            data=request.data,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)

        project = serializer.validated_data.get(
            'project', task.project
        )

        if role == 'Manager':
            if project.assigned_manager_id != user.id:
                return Response(
                    {
                        'error': 'You can update tasks only in your assigned projects.'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

        elif role == 'Team Leader':
            if not project.team_leaders.filter(
                id=user.id
            ).exists():
                return Response(
                    {
                        'error': 'You can update tasks only in projects assigned to you.'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

        task = serializer.save(modified_by=request.user)

        return Response(
            ProjectTaskSerializer(
                task,
                context={'request': request}
            ).data
        )

    def patch(self, request, pk):

        user = request.user
        role = user.profile.name if user.profile else ''

        task = self.get_editable_task(request, pk)

        if not task:
            return Response(
                {
                    'error': 'You do not have permission to update this task.'
                },
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ProjectTaskSerializer(
            task,
            data=request.data,
            partial=True,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)

        project = serializer.validated_data.get(
            'project', task.project
        )

        if role == 'Manager':
            if project.assigned_manager_id != user.id:
                return Response(
                    {
                        'error': 'You can update tasks only in your assigned projects.'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

        elif role == 'Team Leader':
            if not project.team_leaders.filter(
                id=user.id
            ).exists():
                return Response(
                    {
                        'error': 'You can update tasks only in projects assigned to you.'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

        task = serializer.save(modified_by=request.user)

        return Response(
            ProjectTaskSerializer(
                task,
                context={'request': request}
            ).data
        )

    def delete(self, request, pk):

        task = self.get_editable_task(request, pk)

        if not task:
            return Response(
                {
                    'error': 'You do not have permission to delete this task.'
                },
                status=status.HTTP_403_FORBIDDEN
            )

        task.delete()

        return Response(
            {'message': 'Project task deleted successfully.'},
            status=status.HTTP_200_OK
        )


# 22. Task Comment List and Create API

class TaskCommentListCreateAPIView(APIView):

    renderer_classes = [JSONRenderer]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = TaskCommentSerializer

    def get(self, request):

        user = request.user
        role = user.profile.name if user.profile else ''

        if role == 'Client':
            return Response(
                {
                    "success": False,
                    "message": "Clients do not have permission to view comments.",
                    "errors": {}
                },
                status=status.HTTP_403_FORBIDDEN
            )

        comments = TaskComment.objects.select_related(
            'task', 'user', 'task__project'
        ).order_by('id')

        accessible_tasks = ProjectTask.objects.all()


        query_serializer = TaskCommentListQuerySerializer(
            data=request.query_params
        )

        if not query_serializer.is_valid():
            return Response(
                {'error': 'Invalid task_id.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        task_id = query_serializer.validated_data.get('task_id', '')

        if task_id:

            task = ProjectTask.objects.filter(
                pk=int(task_id)
            ).first()

            if not task:
                return Response(
                    {
                        "success": False,
                        "message": "Task not found.",
                        "errors": {}
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            if not accessible_tasks.filter(
                pk=int(task_id)
            ).exists():
                return Response(
                    {
                        "success": False,
                        "message": "You do not have permission to access comments for this task.",
                        "errors": {}
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            comments = comments.filter(task_id=int(task_id))

        else:

            comments = comments.filter(
                task__in=accessible_tasks
            )

        paginator = ClientPagination()
        paginated_comments = paginator.paginate_queryset(
            comments.distinct(), request
        )

        serializer = TaskCommentSerializer(
            paginated_comments,
            many=True,
            context={'request': request}
        )

        return paginator.get_paginated_response(serializer.data)

    def post(self, request):

        user = request.user
        role = user.profile.name if user.profile else ''

        if role == 'Client':
            return Response(
                {
                    "success": False,
                    "message": "Clients do not have permission to add comments.",
                    "errors": {}
                },
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = TaskCommentSerializer(
            data=request.data,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)

        comment = serializer.save(user=request.user)

        response_data = TaskCommentSerializer(
            comment,
            context={'request': request}
        ).data

        response_data.pop('updated_at', None)

        return Response(
            response_data,
            status=status.HTTP_201_CREATED
        )

# 23. Master Data List and Create API

class MasterDataListCreateAPIView(APIView):

    renderer_classes = [JSONRenderer]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    model = None
    serializer_class = None

    def get(self, request):

        records = self.model.objects.all().order_by('id')

        serializer = self.serializer_class(
            records,
            many=True
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def post(self, request):

        serializer = self.serializer_class(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        record = serializer.save(
            created_by=request.user,
            modified_by=None
        )

        return Response(
            self.serializer_class(record).data,
            status=status.HTTP_201_CREATED
        )

# 24. Master Data Retrieve, Update, Partial Update and Delete API

class MasterDataDetailAPIView(APIView):

    renderer_classes = [JSONRenderer]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    model = None
    serializer_class = None

    def get_object(self, pk):

        return get_object_or_404(
            self.model,
            pk=pk
        )

    def get(self, request, pk):

        record = self.get_object(pk)

        serializer = self.serializer_class(record)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def put(self, request, pk):

        record = self.get_object(pk)

        serializer = self.serializer_class(
            record,
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        serializer.save(modified_by=request.user)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def patch(self, request, pk):

        record = self.get_object(pk)

        serializer = self.serializer_class(
            record,
            data=request.data,
            partial=True
        )

        serializer.is_valid(raise_exception=True)

        serializer.save(modified_by=request.user)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def delete(self, request, pk):

        record = self.get_object(pk)

        try:
            record.delete()

        except ProtectedError:
            return Response(
                {
                    'error': 'This record cannot be deleted because it is associated with existing records.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {
                'message': 'Record deleted successfully.'
            },
            status=status.HTTP_200_OK
        )

# 25. Project Type CRUD APIs

class ProjectTypeListCreateAPIView(MasterDataListCreateAPIView):
    model = ProjectType
    serializer_class = ProjectTypeCRUDSerializer

class ProjectTypeDetailAPIView(MasterDataDetailAPIView):
    model = ProjectType
    serializer_class = ProjectTypeCRUDSerializer

# 26. Project Status CRUD APIs

class ProjectStatusListCreateAPIView(MasterDataListCreateAPIView):
    model = ProjectStatus
    serializer_class = ProjectStatusCRUDSerializer

class ProjectStatusDetailAPIView(MasterDataDetailAPIView):
    model = ProjectStatus
    serializer_class = ProjectStatusCRUDSerializer

# 27. Task Status CRUD APIs

class TaskStatusListCreateAPIView(MasterDataListCreateAPIView):
    model = TaskStatus
    serializer_class = TaskStatusCRUDSerializer

class TaskStatusDetailAPIView(MasterDataDetailAPIView):
    model = TaskStatus
    serializer_class = TaskStatusCRUDSerializer
