from django.contrib.auth import get_user_model
from django.core.cache import cache
from core.exceptions import ResourceNotFoundException, PermissionDeniedException

User = get_user_model()


class UserService:
    @classmethod
    def create_user(cls, user_data):
        password = user_data.pop('password')
        user = User(**user_data)
        user.set_password(password)
        user.save()
        
        cls.invalidate_user_cache()
        
        return user
    
    @classmethod
    def get_user_by_id(cls, user_id):
        cache_key = f"user_{user_id}"
        user = cache.get(cache_key)
        
        if user is None:
            try:
                user = User.objects.get(id=user_id)
                cache.set(cache_key, user, 300)  # 5 minutes
            except User.DoesNotExist:
                raise ResourceNotFoundException("User not found")
        
        return user
    
    @classmethod
    def get_all_users(cls):
        return User.objects.all().select_related().order_by('-date_joined')
    
    @classmethod
    def update_user(cls, user, user_data):
        for field, value in user_data.items():
            if hasattr(user, field):
                setattr(user, field, value)
        
        user.save()
        cls.invalidate_user_cache(user.id)
        return user
    
    @classmethod
    def delete_user(cls, user):
        user.is_active = False
        user.save()
        cls.invalidate_user_cache(user.id)
        return user
    
    @classmethod
    def invalidate_user_cache(cls, user_id=None):
        if user_id:
            cache_key = f"user_{user_id}"
            cache.delete(cache_key)
        else:
            pass


class UserPermissionService:
    @classmethod
    def can_create_user(cls, requesting_user):
        return requesting_user.is_superuser
    
    @classmethod
    def can_view_user(cls, requesting_user, target_user):
        return requesting_user.is_superuser or requesting_user == target_user
    
    @classmethod
    def can_edit_user(cls, requesting_user, target_user):
        return requesting_user.is_superuser or requesting_user == target_user
    
    @classmethod
    def can_delete_user(cls, requesting_user, target_user):
        return requesting_user.is_superuser and requesting_user != target_user
