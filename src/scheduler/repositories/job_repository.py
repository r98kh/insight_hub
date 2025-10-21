from django.db.models import QuerySet, Q
from django.contrib.auth import get_user_model
from typing import Optional, Dict, Any, List
from ..models import ScheduledJob, JobExecutionLog

User = get_user_model()


class ScheduledJobRepository:
    @staticmethod
    def get_user_jobs(user: User, include_inactive: bool = False) -> QuerySet:
        queryset = ScheduledJob.objects.filter(user=user)
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        return queryset.select_related('task_definition').prefetch_related(
            'task_definition__taskparameter_set'
        )
    
    @staticmethod
    def get_all_jobs(include_inactive: bool = False) -> QuerySet:
        queryset = ScheduledJob.objects.all()
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        return queryset.select_related('user', 'task_definition').prefetch_related(
            'task_definition__taskparameter_set'
        )
    
    @staticmethod
    def get_job_by_id(job_id: int, user: User = None) -> Optional[ScheduledJob]:
        queryset = ScheduledJob.objects.select_related('user', 'task_definition')
        if user and not user.is_superuser:
            queryset = queryset.filter(user=user)
        try:
            return queryset.get(id=job_id)
        except ScheduledJob.DoesNotExist:
            return None
    
    @staticmethod
    def get_active_jobs_by_user(user: User) -> QuerySet:
        return ScheduledJob.objects.filter(
            user=user, 
            is_active=True, 
            status='active'
        ).select_related('task_definition')
    
    @staticmethod
    def get_jobs_by_task_definition(task_definition_id: int) -> QuerySet:
        return ScheduledJob.objects.filter(
            task_definition_id=task_definition_id
        ).select_related('user', 'task_definition')
    
    @staticmethod
    def search_jobs(query: str, user: User = None) -> QuerySet:
        queryset = ScheduledJob.objects.all()
        if user and not user.is_superuser:
            queryset = queryset.filter(user=user)
        
        return queryset.filter(
            Q(task_definition__name__icontains=query) |
            Q(task_definition__description__icontains=query) |
            Q(cron_expression__icontains=query)
        ).select_related('user', 'task_definition')
    
    @staticmethod
    def filter_jobs(filters: Dict[str, Any], user: User = None) -> QuerySet:
        queryset = ScheduledJob.objects.all()
        if user and not user.is_superuser:
            queryset = queryset.filter(user=user)
        
        for field, value in filters.items():
            if hasattr(ScheduledJob, field):
                queryset = queryset.filter(**{field: value})
        
        return queryset.select_related('user', 'task_definition')
    
    @staticmethod
    def create_job(data: Dict[str, Any], user: User) -> ScheduledJob:
        return ScheduledJob.objects.create(user=user, **data)
    
    @staticmethod
    def update_job(job: ScheduledJob, data: Dict[str, Any]) -> ScheduledJob:
        for field, value in data.items():
            setattr(job, field, value)
        job.save()
        return job
    
    @staticmethod
    def delete_job(job: ScheduledJob) -> bool:
        try:
            job.delete()
            return True
        except Exception:
            return False


class JobExecutionLogRepository:
    @staticmethod
    def get_user_execution_logs(user: User) -> QuerySet:
        return JobExecutionLog.objects.filter(
            scheduled_job__user=user
        ).select_related('scheduled_job__task_definition')
    
    @staticmethod
    def get_all_execution_logs() -> QuerySet:
        return JobExecutionLog.objects.all().select_related(
            'scheduled_job__task_definition', 
            'scheduled_job__user'
        )
    
    @staticmethod
    def get_execution_log_by_id(log_id: int, user: User = None) -> Optional[JobExecutionLog]:
        queryset = JobExecutionLog.objects.select_related('scheduled_job__task_definition')
        if user and not user.is_superuser:
            queryset = queryset.filter(scheduled_job__user=user)
        try:
            return queryset.get(id=log_id)
        except JobExecutionLog.DoesNotExist:
            return None
    
    @staticmethod
    def get_logs_by_job(scheduled_job: ScheduledJob, limit: int = None) -> QuerySet:
        queryset = JobExecutionLog.objects.filter(
            scheduled_job=scheduled_job
        ).order_by('-execution_time')
        
        if limit:
            queryset = queryset[:limit]
        
        return queryset
    
    @staticmethod
    def get_logs_by_status(status: str, user: User = None) -> QuerySet:
        queryset = JobExecutionLog.objects.filter(status=status)
        if user and not user.is_superuser:
            queryset = queryset.filter(scheduled_job__user=user)
        return queryset.select_related('scheduled_job__task_definition')
    
    @staticmethod
    def search_execution_logs(query: str, user: User = None) -> QuerySet:
        queryset = JobExecutionLog.objects.all()
        if user and not user.is_superuser:
            queryset = queryset.filter(scheduled_job__user=user)
        
        return queryset.filter(
            Q(scheduled_job__task_definition__name__icontains=query) |
            Q(status__icontains=query) |
            Q(error_message__icontains=query)
        ).select_related('scheduled_job__task_definition')
    
    @staticmethod
    def create_execution_log(scheduled_job: ScheduledJob, **kwargs) -> JobExecutionLog:
        return JobExecutionLog.objects.create(scheduled_job=scheduled_job, **kwargs)
