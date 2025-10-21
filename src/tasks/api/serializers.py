from rest_framework import serializers
from ..models import TaskDefinition, TaskParameter


class TaskParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskParameter
        fields = ['parameter_name', 'parameter_type']


class TaskDefinitionSerializer(serializers.ModelSerializer):
    parameters = TaskParameterSerializer(many=True, read_only=True, source='get_parameters')
    
    class Meta:
        model = TaskDefinition
        fields = ['id','name', 'parameters']
