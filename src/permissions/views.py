from rest_framework import permissions


class IsOwnerOrSuperuser(permissions.BasePermission):
    
    def has_permission(self, request, view):
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        return obj.user == request.user


class IsSuperuserOrReadOnly(permissions.BasePermission):    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_superuser


class IsSuperuserOnly(permissions.BasePermission):
    
    def has_permission(self, request, view):
        return request.user.is_superuser


class IsAuthenticatedOnly(permissions.BasePermission):
    
    def has_permission(self, request, view):
        return request.user.is_authenticated


class IsOwnerOrReadOnly(permissions.BasePermission):
    
    def has_permission(self, request, view):
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user == request.user


class HasSpecificPermission(permissions.BasePermission):
    
    def __init__(self, permission_codename):
        self.permission_codename = permission_codename
    
    def has_permission(self, request, view):
        return request.user.has_perm(self.permission_codename)


class IsOwnerOrHasPermission(permissions.BasePermission):
    
    def __init__(self, permission_codename):
        self.permission_codename = permission_codename      
    
    def has_permission(self, request, view):
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        
        if hasattr(obj, 'user') and obj.user == request.user:
            return True
        
        return request.user.has_perm(self.permission_codename)


class JobLimitPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        if request.user.is_superuser:
            return True
        
        if hasattr(view, 'action') and view.action in ['pause', 'resume', 'execute_now']:
            return True
        
        # Import here to avoid circular import
        from scheduler.models import ScheduledJob
        
        active_jobs_count = ScheduledJob.objects.filter(
            user=request.user,
            is_active=True
        ).count()
        
        return active_jobs_count < 5


class PermissionMixin:
    
    @staticmethod
    def check_user_limit(user, model_class, limit_field='is_active', limit_value=True, max_limit=5):
        if user.is_superuser:
            return True, 0, None
        
        current_count = model_class.objects.filter(
            user=user,
            **{limit_field: limit_value}
        ).count()
        
        return current_count < max_limit, current_count, max_limit
    
    @staticmethod
    def get_user_objects(user, model_class, filter_field='user'):
        if user.is_superuser:
            return model_class.objects.all()
        
        return model_class.objects.filter(**{filter_field: user})
    
    @staticmethod
    def check_job_limit(user, max_limit=5): 
        if user.is_superuser:
            return True, 0, None
        
        # Import here to avoid circular import
        from scheduler.models import ScheduledJob
        
        active_jobs_count = ScheduledJob.objects.filter(
            user=user,
            is_active=True
        ).count()
        
        return active_jobs_count < max_limit, active_jobs_count, max_limit
