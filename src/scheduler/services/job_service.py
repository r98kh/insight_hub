from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Count, Q
from core.exceptions import JobLimitExceededException
from ..models import ScheduledJob, JobExecutionLog

User = get_user_model()


class JobLimitService:
    MAX_JOBS_NORMAL_USER = 5
    MAX_JOBS_SUPERUSER = 100
    
    @classmethod
    def can_create_job(cls, user):
        active_jobs_count = cls.get_active_jobs_count(user)
        max_jobs = cls.MAX_JOBS_SUPERUSER if user.is_superuser else cls.MAX_JOBS_NORMAL_USER
        return active_jobs_count < max_jobs
    
    @classmethod
    def get_active_jobs_count(cls, user):
        cache_key = f"active_jobs_count_{user.id}"
        count = cache.get(cache_key)
        
        if count is None:
            count = ScheduledJob.objects.filter(
                user=user, 
                is_active=True, 
                status='active'
            ).count()
            cache.set(cache_key, count, 300)
        
        return count
    
    @classmethod
    def invalidate_cache(cls, user):
        cache_key = f"active_jobs_count_{user.id}"
        cache.delete(cache_key)


class JobStatisticsService:
    @classmethod
    def get_user_statistics(cls, user):
        cache_key = f"user_stats_{user.id}"
        stats = cache.get(cache_key)
        
        if stats is None:
            stats = cls._calculate_statistics(user)
            cache.set(cache_key, stats, 600)
        
        return stats
    
    @classmethod
    def _calculate_statistics(cls, user):
        queryset = ScheduledJob.objects.filter(user=user)
        
        total_jobs = queryset.count()
        active_jobs = queryset.filter(is_active=True, status='active').count()
        paused_jobs = queryset.filter(status='paused').count()
        inactive_jobs = queryset.filter(is_active=False).count()
        
        execution_logs = JobExecutionLog.objects.filter(scheduled_job__user=user)
        total_executions = execution_logs.count()
        successful_executions = execution_logs.filter(status='success').count()
        failed_executions = execution_logs.filter(status='failed').count()
        
        success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0
        
        return {
            'total_jobs': total_jobs,
            'active_jobs': active_jobs,
            'paused_jobs': paused_jobs,
            'inactive_jobs': inactive_jobs,
            'total_executions': total_executions,
            'successful_executions': successful_executions,
            'failed_executions': failed_executions,
            'success_rate': round(success_rate, 2)
        }
    
    @classmethod
    def invalidate_cache(cls, user):
        cache_key = f"user_stats_{user.id}"
        cache.delete(cache_key)


class JobExecutionService:
    @classmethod
    def create_execution_log(cls, scheduled_job, celery_task_id=None):
        return JobExecutionLog.objects.create(
            scheduled_job=scheduled_job,
            celery_task_id=celery_task_id
        )
    
    @classmethod
    def mark_execution_started(cls, execution_log, celery_task_id=None):
        execution_log.mark_as_started(celery_task_id)
    
    @classmethod
    def mark_execution_completed(cls, execution_log, result=None):
        execution_log.mark_as_completed(result)
        execution_log.scheduled_job.increment_execution_count()
        execution_log.scheduled_job.reset_failure_count()
    
    @classmethod
    def mark_execution_failed(cls, execution_log, error_message="", error_traceback=""):
        execution_log.mark_as_failed(error_message, error_traceback)
        execution_log.scheduled_job.increment_failure_count()
    
    @classmethod
    def get_recent_executions(cls, scheduled_job, limit=10):
        return JobExecutionLog.objects.filter(
            scheduled_job=scheduled_job
        ).order_by('-execution_time')[:limit]


class TaskFunctionService:
    @classmethod
    def get_task_function(cls, function_path):
        try:
            module_path, function_name = function_path.rsplit('.', 1)
            
            import importlib
            module = importlib.import_module(module_path)
            function = getattr(module, function_name)
            
            return function
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting task function {function_path}: {e}")
            raise


class CronService:
    @classmethod
    def get_next_run_time(cls, cron_expression):
        try:
            from croniter import croniter
            from django.utils import timezone
            
            cron = croniter(cron_expression, timezone.now())
            return cron.get_next(timezone.now())
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error calculating next run time: {e}")
            return None


class SystemStatisticsService:
    @classmethod
    def get_job_statistics(cls):
        try:
            stats = {
                'total_jobs': ScheduledJob.objects.count(),
                'active_jobs': ScheduledJob.objects.filter(is_active=True).count(),
                'inactive_jobs': ScheduledJob.objects.filter(is_active=False).count(),
                'jobs_with_celery_task': ScheduledJob.objects.filter(celery_task__isnull=False).count(),
                'jobs_without_celery_task': ScheduledJob.objects.filter(celery_task__isnull=True).count(),
                'failed_jobs': ScheduledJob.objects.filter(consecutive_failures__gte=3).count(),
                'execution_logs_count': JobExecutionLog.objects.count(),
                'successful_executions': JobExecutionLog.objects.filter(status='success').count(),
                'failed_executions': JobExecutionLog.objects.filter(status='failed').count(),
            }
            
            return stats
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting job statistics: {e}")
            return {}


class JobSyncService:
    @classmethod
    def sync_all_scheduled_jobs(cls):
        try:
            from ..services.celery_service import CeleryTaskService
            
            scheduled_jobs = ScheduledJob.objects.filter(is_active=True)
            
            for job in scheduled_jobs:
                try:
                    if not job.celery_task:
                        CeleryTaskService.create_periodic_task(job)
                    else:
                        CeleryTaskService.update_periodic_task(job)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error syncing scheduled job {job.id}: {e}")
                    continue
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Synced {scheduled_jobs.count()} scheduled jobs")
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error syncing scheduled jobs: {e}")
            raise
    
    @classmethod
    def cleanup_orphaned_tasks(cls):
        try:
            from django_celery_beat.models import PeriodicTask
            
            orphaned_tasks = PeriodicTask.objects.filter(
                task='scheduler.tasks.execute_scheduled_job'
            ).exclude(
                scheduled_job__isnull=False
            )
            
            count = orphaned_tasks.count()
            orphaned_tasks.delete()
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Cleaned up {count} orphaned periodic tasks")
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error cleaning up orphaned tasks: {e}")
            raise
