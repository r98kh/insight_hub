from rest_framework import serializers
from scheduler.models import ScheduledJob, JobExecutionLog
from ..validators import validate_cron_expression, get_cron_description, validate_parameter_type


class ScheduledJobSerializer(serializers.ModelSerializer):
    task_definition_name = serializers.CharField(source='task_definition.name', read_only=True)
    task_definition_description = serializers.CharField(source='task_definition.description', read_only=True)
    cron_description = serializers.SerializerMethodField()
    next_run_formatted = serializers.SerializerMethodField()
    last_run_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = ScheduledJob
        fields = [
            'id', 'task_definition', 'task_definition_name', 'task_definition_description',
            'cron_expression', 'cron_description', 'parameters', 'is_active', 'status',
            'execution_count', 'consecutive_failures', 'max_executions', 'max_failures',
            'created_at', 'updated_at', 'last_run', 'last_run_formatted', 
            'next_run', 'next_run_formatted'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'execution_count', 
            'consecutive_failures', 'last_run', 'next_run'
        ]
    
    def get_cron_description(self, obj):
        return get_cron_description(obj.cron_expression)
    
    def get_next_run_formatted(self, obj):
        if obj.next_run:
            return obj.next_run.strftime('%Y-%m-%d %H:%M:%S')
        return None
    
    def get_last_run_formatted(self, obj):
        if obj.last_run:
            return obj.last_run.strftime('%Y-%m-%d %H:%M:%S')
        return None
    
    def validate_cron_expression(self, value):
        validate_cron_expression(value)
        return value
    
    def validate_parameters(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Parameters must be a JSON object")
        return value
    
    def validate(self, attrs):
        task_definition = attrs.get('task_definition')
        parameters = attrs.get('parameters', {})
        
        if task_definition:
            task_params = task_definition.get_parameters()
            errors = []
            
            for param in task_params:
                param_name = param.parameter_name
                
                if param.is_required and param_name not in parameters:
                    errors.append(f"Required parameter '{param_name}' is missing")
                
                if param_name in parameters:
                    value = parameters[param_name]
                    if not validate_parameter_type(value, param.parameter_type):
                        errors.append(f"Parameter '{param_name}' has invalid type. Expected: {param.parameter_type}")
            
            if errors:
                raise serializers.ValidationError({'parameters': errors})
        
        return attrs


class ScheduledJobCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduledJob
        fields = ['task_definition', 'cron_expression', 'parameters']
    
    def validate_cron_expression(self, value):
        validate_cron_expression(value)
        return value
    
    def validate_parameters(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Parameters must be a JSON object")
        return value
    
    def validate(self, attrs):
        task_definition = attrs.get('task_definition')
        parameters = attrs.get('parameters', {})
        
        if task_definition:
            task_params = task_definition.get_parameters()
            errors = []
            
            for param in task_params:
                param_name = param.parameter_name
                
                if param.is_required and param_name not in parameters:
                    errors.append(f"Required parameter '{param_name}' is missing")
                
                if param_name in parameters:
                    value = parameters[param_name]
                    if not validate_parameter_type(value, param.parameter_type):
                        errors.append(f"Parameter '{param_name}' has invalid type. Expected: {param.parameter_type}")
            
            if errors:
                raise serializers.ValidationError({'parameters': errors})
        
        return attrs


class JobExecutionLogSerializer(serializers.ModelSerializer):
    scheduled_job_name = serializers.CharField(source='scheduled_job.task_definition.name', read_only=True)
    duration_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = JobExecutionLog
        fields = [
            'id', 'scheduled_job', 'scheduled_job_name', 'execution_time', 
            'status', 'started_at', 'completed_at', 'duration', 'duration_formatted',
            'result', 'error_message', 'celery_task_id'
        ]
        read_only_fields = [
            'id', 'execution_time', 'started_at', 'completed_at', 
            'duration', 'celery_task_id'
        ]
    
    def get_duration_formatted(self, obj):
        if obj.duration:
            total_seconds = obj.duration.total_seconds()
            if total_seconds < 60:
                return f"{total_seconds:.2f}s"
            elif total_seconds < 3600:
                return f"{total_seconds/60:.2f}m"
            else:
                return f"{total_seconds/3600:.2f}h"
        return None


class ScheduleListRequestSerializer(serializers.Serializer):
    filters = serializers.DictField(required=False, default=dict)
    ordering = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=[]
    )
    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=10)
    search = serializers.CharField(required=False, allow_blank=True)
    
    def validate_ordering(self, value):
        allowed_fields = [
            'id', 'user', 'task_definition', 'cron_expression', 'is_active', 'status',
            'created_at', 'updated_at', 'last_run', 'next_run', 'max_executions',
            'execution_count', 'max_failures', 'consecutive_failures',
            'task_definition__name', 'task_definition__description',
            'user__username', 'user__email'
        ]
        
        for field in value:
            clean_field = field.lstrip('-')
            if clean_field not in allowed_fields:
                raise serializers.ValidationError(f"Invalid ordering field: {clean_field}")
        
        return value


class AdvancedSearchSerializer(serializers.Serializer):
    filters = serializers.DictField(required=False, default=dict)
    ordering = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=[]
    )
    search = serializers.CharField(required=False, allow_blank=True)
    search_fields = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=[]
    )
    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=10)
    
    def validate_ordering(self, value):
        allowed_fields = [
            'id', 'user', 'task_definition', 'cron_expression', 'is_active', 'status',
            'created_at', 'updated_at', 'last_run', 'next_run', 'max_executions',
            'execution_count', 'max_failures', 'consecutive_failures',
            'task_definition__name', 'task_definition__description',
            'user__username', 'user__email'
        ]
        
        for field in value:
            clean_field = field.lstrip('-')
            if clean_field not in allowed_fields:
                raise serializers.ValidationError(f"Invalid ordering field: {clean_field}")
        
        return value
    
    def validate_filters(self, value):
        allowed_filter_fields = [
            'id', 'user', 'task_definition', 'cron_expression', 'is_active', 'status',
            'created_at', 'updated_at', 'last_run', 'next_run', 'max_executions',
            'execution_count', 'max_failures', 'consecutive_failures',
            'task_definition__name', 'task_definition__description',
            'user__username', 'user__email'
        ]
        
        for field in value.keys():
            clean_field = field.split('__')[0]
            if clean_field not in [f.split('__')[0] for f in allowed_filter_fields]:
                raise serializers.ValidationError(f"Invalid filter field: {clean_field}")
        
        return value