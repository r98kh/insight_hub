from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django_celery_beat.models import PeriodicTask
from .validators import validate_cron_expression, validate_cron_frequency, validate_parameter_type
import json

User = get_user_model()


class ScheduledJob(models.Model):

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('paused', 'Paused'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='scheduled_jobs'
    )
    task_definition = models.ForeignKey(
        'tasks.TaskDefinition',
        on_delete=models.CASCADE,
        related_name='scheduled_jobs'
    )
    
    cron_expression = models.CharField(
        max_length=50,
        validators=[validate_cron_expression, validate_cron_frequency],
    )
    
    parameters = models.JSONField(
        default=dict,
    )
    
    is_active = models.BooleanField(
        default=True,
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
    )
    
    celery_task = models.OneToOneField(
        PeriodicTask,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='scheduled_job'
    )
    
    created_at = models.DateTimeField(
        default=timezone.now,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )
    last_run = models.DateTimeField(
        null=True,
        blank=True,
    )
    next_run = models.DateTimeField(
        null=True,
        blank=True,
    )
    
    max_executions = models.PositiveIntegerField(
        null=True,
        blank=True,
    )
    execution_count = models.PositiveIntegerField(
        default=0,
    )
    
    max_failures = models.PositiveIntegerField(
        default=3,
    )
    consecutive_failures = models.PositiveIntegerField(
        default=0,
    )

    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['is_active', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['last_run']),
            models.Index(fields=['next_run']),
            models.Index(fields=['task_definition', 'is_active']),
        ]

    def get_cron_parts(self):
        parts = self.cron_expression.split()
        if len(parts) != 5:
            return None
        return {
            'minute': parts[0],
            'hour': parts[1],
            'day': parts[2],
            'month': parts[3],
            'day_of_week': parts[4]
        }

    def validate_parameters(self):
        task_params = self.task_definition.get_parameters()
        errors = []
        
        for param in task_params:
            param_name = param.parameter_name
            
            if param.is_required and param_name not in self.parameters:
                errors.append(f"Required parameter '{param_name}' is missing")
            
            if param_name in self.parameters:
                value = self.parameters[param_name]
                if not validate_parameter_type(value, param.parameter_type):
                    errors.append(f"Parameter '{param_name}' has invalid type. Expected: {param.parameter_type}")
        
        return errors

    def can_execute(self):
        if not self.is_active or self.status != 'active':
            return False
        
        if self.max_executions and self.execution_count >= self.max_executions:
            return False
        
        if self.consecutive_failures >= self.max_failures:
            return False
        
        return True

    def increment_execution_count(self):
        self.execution_count += 1
        self.save(update_fields=['execution_count'])

    def increment_failure_count(self):
        self.consecutive_failures += 1
        self.save(update_fields=['consecutive_failures'])

    def reset_failure_count(self):
        self.consecutive_failures = 0
        self.save(update_fields=['consecutive_failures'])


class JobExecutionLog(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('timeout', 'Timeout'),
    ]

    scheduled_job = models.ForeignKey(
        ScheduledJob,
        on_delete=models.CASCADE,
        related_name='execution_logs'
    )
    
    execution_time = models.DateTimeField(
        default=timezone.now,
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
    )
    
    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    
    duration = models.DurationField(
        null=True,
        blank=True,
    )
    
    result = models.JSONField(
        null=True,
        blank=True,
    )
    
    error_message = models.TextField(
        blank=True,
    )
    
    error_traceback = models.TextField(
        blank=True,
    )
    
    celery_task_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Celery Task ID"
    )
    
    memory_usage = models.PositiveIntegerField(
        null=True,
        blank=True,
    )
    
    cpu_time = models.DurationField(
        null=True,
        blank=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=['scheduled_job', 'status']),
            models.Index(fields=['execution_time']),
            models.Index(fields=['status', 'execution_time']),
            models.Index(fields=['scheduled_job', 'execution_time']),
        ]

    def calculate_duration(self):
        if self.started_at and self.completed_at:
            self.duration = self.completed_at - self.started_at
            self.save(update_fields=['duration'])

    def mark_as_started(self, celery_task_id=None):
        self.status = 'running'
        self.started_at = timezone.now()
        if celery_task_id:
            self.celery_task_id = celery_task_id
        self.save(update_fields=['status', 'started_at', 'celery_task_id'])

    def mark_as_completed(self, result=None):
        self.status = 'success'
        self.completed_at = timezone.now()
        if result:
            self.result = result
        self.calculate_duration()
        self.save(update_fields=['status', 'completed_at', 'result', 'duration'])

    def mark_as_failed(self, error_message="", error_traceback=""):         
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.error_traceback = error_traceback
        self.calculate_duration()
        self.save(update_fields=['status', 'completed_at', 'error_message', 'error_traceback', 'duration'])
