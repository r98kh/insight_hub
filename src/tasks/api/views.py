from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from django.core.cache import cache
from django.conf import settings
from ..models import TaskDefinition
from .serializers import TaskDefinitionSerializer


class AvailableTasksListView(generics.ListAPIView):
    serializer_class = TaskDefinitionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        cache_key = 'available_tasks'
        cached_tasks = cache.get(cache_key)
        
        if cached_tasks is None:
            cached_tasks = TaskDefinition.objects.filter(is_active=True).select_related().prefetch_related('taskparameter_set')
            cache.set(cache_key, cached_tasks, settings.CACHE_TTL['task_definitions'])
        
        return cached_tasks
    
    @swagger_auto_schema(
        operation_summary='List available tasks',
        operation_description='Returns a list of all available tasks that can be scheduled.'
    )
    def get(self, request, *args, **kwargs):
        tasks = self.get_queryset()
        serializer = self.get_serializer(tasks, many=True)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
