from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.contrib.auth import get_user_model

from .serializers import UserCreateSerializer, UserListSerializer

User = get_user_model()


class IsSuperUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class RegisterUserView(APIView):
    permission_classes = [IsSuperUser]

    @swagger_auto_schema(
        request_body=UserCreateSerializer,
        operation_summary='Create a new user (superuser only)',
        operation_description='Creates a user with first_name, last_name, username, password, email.'
    )
    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.save()
        return Response({'id': user.id, 'username': user.username, 'email': user.email}, status=status.HTTP_201_CREATED)


class UserListView(APIView):
    permission_classes = [IsSuperUser]

    @swagger_auto_schema(
        operation_summary='List all users (superuser only)',
        operation_description='Returns a list of all users in the system with their basic information.'
    )
    def get(self, request):
        users = User.objects.all().order_by('-date_joined')
        serializer = UserListSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
