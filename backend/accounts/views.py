from django.contrib.auth import get_user_model, login as django_login, logout as django_logout
from django.db import models
from django.shortcuts import render, redirect
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import RegisterSerializer, UserSerializer, AdminUserSerializer, AdminCreateUserSerializer

User = get_user_model()


class IsAdminRole(permissions.BasePermission):
    """Role-based admin check (the app uses a role field, not is_staff)."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin_user()


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        # Also create a Django session so server-rendered pages see request.user
        django_login(request, user)
        return Response({
            'user': UserSerializer(user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        # JWT auth alone doesn't cover Django template views (/staff/, /admin-panel/),
        # which rely on session auth — so log the session in as well.
        if response.status_code == 200:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.user
            django_login(request, user)
            response.data['user'] = UserSerializer(user).data
        return response


class LogoutView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            pass
        django_logout(request)
        return Response({'detail': 'Logged out.'}, status=status.HTTP_200_OK)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class AdminUserListCreateView(generics.ListCreateAPIView):
    """Admin-only user management: list every account, optionally filtered by
    role/search, and create new accounts with any role (staff/admin included)."""
    permission_classes = [IsAdminRole]
    pagination_class = None

    def get_queryset(self):
        qs = User.objects.all().order_by('-date_joined')
        role = self.request.query_params.get('role', '')
        q = self.request.query_params.get('q', '')
        if role in ('customer', 'staff', 'admin'):
            qs = qs.filter(role=role)
        if q:
            qs = qs.filter(
                models.Q(username__icontains=q) | models.Q(email__icontains=q) |
                models.Q(first_name__icontains=q) | models.Q(last_name__icontains=q)
            )
        return qs

    def get_serializer_class(self):
        return AdminCreateUserSerializer if self.request.method == 'POST' else AdminUserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(AdminUserSerializer(user).data, status=status.HTTP_201_CREATED)


class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Edit a user's role/active status, or remove the account entirely.
    An admin can't lock themselves out — self-demotion/deactivation/deletion
    on their own account is blocked."""
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminRole]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.id == request.user.id:
            new_role = request.data.get('role')
            new_active = request.data.get('is_active')
            if (new_role is not None and new_role != instance.role) or new_active is False:
                return Response(
                    {'detail': "You can't change your own role or deactivate your own account."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.id == request.user.id:
            return Response(
                {'detail': "You can't delete your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


def login_page(request):
    if request.user.is_authenticated:
        return redirect('home')
    return render(request, 'store/home.html', {'open_login': True})
