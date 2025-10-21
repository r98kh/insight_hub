from rest_framework import generics, status
from rest_framework.response import Response
from ..models import TaskDefinition
from .serializers import TaskDefinitionSerializer


class AvailableTasksListView(generics.ListAPIView):

    queryset = TaskDefinition.objects.filter(is_active=True)
    serializer_class = TaskDefinitionSerializer
    
    def get(self, request, *args, **kwargs):
        tasks = self.get_queryset()
        serializer = self.get_serializer(tasks, many=True)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
