from django_celery_beat.models import PeriodicTask, CrontabSchedule
from django.utils import timezone
from django.db import transaction
from croniter import croniter
from datetime import datetime
import json
import logging

from .models import ScheduledJob, JobExecutionLog

logger = logging.getLogger(__name__)


def create_crontab_schedule(cron_expression):
    try:
        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValueError("Invalid cron expression format")
        
        minute, hour, day_of_month, month_of_year, day_of_week = parts
        
        crontab_schedule, created = CrontabSchedule.objects.get_or_create(
            minute=minute,
            hour=hour,
            day_of_month=day_of_month,
            month_of_year=month_of_year,
            day_of_week=day_of_week,
        )
        
        return crontab_schedule
        
    except Exception as e:
        logger.error(f"Error creating crontab schedule: {e}")
        raise


def create_periodic_task(scheduled_job):

    try:
        with transaction.atomic():
            crontab_schedule = create_crontab_schedule(scheduled_job.cron_expression)
            
            task_name = f"scheduled_job_{scheduled_job.id}_{scheduled_job.user.id}"
            
            periodic_task = PeriodicTask.objects.create(
                name=task_name,
                task='scheduler.tasks.execute_scheduled_job',
                crontab=crontab_schedule,
                args=json.dumps([scheduled_job.id]),
                enabled=scheduled_job.is_active,
                description=f"Scheduled job: {scheduled_job.task_definition.name}",
            )
            
            scheduled_job.celery_task = periodic_task
            
            next_run = get_next_run_time(scheduled_job.cron_expression)
            scheduled_job.next_run = next_run
            
            scheduled_job.save(update_fields=['celery_task', 'next_run'])
            
            logger.info(f"Created periodic task for scheduled job {scheduled_job.id}")
            return periodic_task
            
    except Exception as e:
        logger.error(f"Error creating periodic task: {e}")
        raise


def update_periodic_task(scheduled_job):

    try:
        if not scheduled_job.celery_task:
            return create_periodic_task(scheduled_job)
        
        with transaction.atomic():
            periodic_task = scheduled_job.celery_task
            
            crontab_schedule = create_crontab_schedule(scheduled_job.cron_expression)
            periodic_task.crontab = crontab_schedule
            
            periodic_task.enabled = scheduled_job.is_active
            
            periodic_task.description = f"Scheduled job: {scheduled_job.task_definition.name}"
            
            periodic_task.save()
            
            next_run = get_next_run_time(scheduled_job.cron_expression)
            scheduled_job.next_run = next_run
            scheduled_job.save(update_fields=['next_run'])
            
            logger.info(f"Updated periodic task for scheduled job {scheduled_job.id}")
            return periodic_task
            
    except Exception as e:
        logger.error(f"Error updating periodic task: {e}")
        raise


def delete_periodic_task(scheduled_job):
    try:
        if scheduled_job.celery_task:
            periodic_task = scheduled_job.celery_task
            periodic_task.delete()
            
            scheduled_job.celery_task = None
            scheduled_job.next_run = None
            scheduled_job.save(update_fields=['celery_task', 'next_run'])
            
            logger.info(f"Deleted periodic task for scheduled job {scheduled_job.id}")
            
    except Exception as e:
        logger.error(f"Error deleting periodic task: {e}")
        raise


def get_next_run_time(cron_expression):
    try:
        cron = croniter(cron_expression, timezone.now())
        return cron.get_next(datetime)
    except Exception as e:
        logger.error(f"Error calculating next run time: {e}")
        return None


def sync_all_scheduled_jobs():
    try:
        scheduled_jobs = ScheduledJob.objects.filter(is_active=True)
        
        for job in scheduled_jobs:
            try:
                if not job.celery_task:
                    create_periodic_task(job)
                else:
                    update_periodic_task(job)
            except Exception as e:
                logger.error(f"Error syncing scheduled job {job.id}: {e}")
                continue
        
        logger.info(f"Synced {scheduled_jobs.count()} scheduled jobs")
        
    except Exception as e:
        logger.error(f"Error syncing scheduled jobs: {e}")
        raise


def cleanup_orphaned_tasks():
    try:
        orphaned_tasks = PeriodicTask.objects.filter(
            task='scheduler.tasks.execute_scheduled_job'
        ).exclude(
            scheduled_job__isnull=False
        )
        
        count = orphaned_tasks.count()
        orphaned_tasks.delete()
        
        logger.info(f"Cleaned up {count} orphaned periodic tasks")
        
    except Exception as e:
        logger.error(f"Error cleaning up orphaned tasks: {e}")
        raise


def get_job_statistics():
    try:
        from django.db.models import Count, Q
        
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
        logger.error(f"Error getting job statistics: {e}")
        return {}


def get_task_function(function_path):
    try:
        module_path, function_name = function_path.rsplit('.', 1)
        
        import importlib
        module = importlib.import_module(module_path)
        function = getattr(module, function_name)
        
        return function
        
    except Exception as e:
        logger.error(f"Error getting task function {function_path}: {e}")
        raise


def validate_job_limits(user, task_definition):
    try:
        active_jobs_count = ScheduledJob.objects.filter(
            user=user,
            is_active=True
        ).count()

        max_active_jobs = 5 if not user.is_superuser else None
        
        if max_active_jobs and active_jobs_count >= max_active_jobs:
            return False, f"Maximum {max_active_jobs} active jobs allowed"
        
        return True, "OK"
        
    except Exception as e:
        logger.error(f"Error validating job limits: {e}")
        return False, "Validation error"


def get_user_job_statistics(user):
    try:
        user_jobs = ScheduledJob.objects.filter(user=user)
        
        stats = {
            'total_jobs': user_jobs.count(),
            'active_jobs': user_jobs.filter(is_active=True).count(),
            'inactive_jobs': user_jobs.filter(is_active=False).count(),
            'failed_jobs': user_jobs.filter(consecutive_failures__gte=3).count(),
            'total_executions': JobExecutionLog.objects.filter(scheduled_job__user=user).count(),
            'successful_executions': JobExecutionLog.objects.filter(
                scheduled_job__user=user,
                status='success'
            ).count(),
            'failed_executions': JobExecutionLog.objects.filter(
                scheduled_job__user=user,
                status='failed'
            ).count(),
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting user job statistics: {e}")
        return {}

