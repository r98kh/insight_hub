from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from ..models import TaskDefinition
from .serializers import TaskDefinitionSerializer


class AvailableTasksListView(generics.ListAPIView):
    queryset = TaskDefinition.objects.filter(is_active=True)
    serializer_class = TaskDefinitionSerializer
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_summary='List available tasks',
        operation_description='Returns a list of all available tasks that can be scheduled.'
    )
    def get(self, request, *args, **kwargs):
        tasks = self.get_queryset()
        serializer = self.get_serializer(tasks, many=True)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
