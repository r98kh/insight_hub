from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied


class IsOwnerOrSuperuser(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user.is_superuser or obj.user == request.user


class JobLimitPermission(BasePermission):
    def has_permission(self, request, view):
        if request.method in ['POST']:
            from scheduler.services import JobLimitService
            return JobLimitService.can_create_job(request.user)
        return True


class TaskExecutionPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        if not obj.can_execute():
            raise PermissionDenied("Job cannot be executed at this time")
        return request.user.is_superuser or obj.user == request.user


class ReadOnlyOrOwnerPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        return request.user.is_superuser or obj.user == request.user
