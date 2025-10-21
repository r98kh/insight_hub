from django.core.cache import cache
from django_celery_beat.models import PeriodicTask, CrontabSchedule
from core.exceptions import CeleryTaskException
from ..models import ScheduledJob


class CeleryTaskService:
    @classmethod
    def create_periodic_task(cls, scheduled_job):
        try:
            cron_parts = scheduled_job.get_cron_parts()
            if not cron_parts:
                raise CeleryTaskException("Invalid cron expression")
            
            schedule, created = CrontabSchedule.objects.get_or_create(
                minute=cron_parts['minute'],
                hour=cron_parts['hour'],
                day_of_week=cron_parts['day_of_week'],
                day_of_month=cron_parts['day'],
                month_of_year=cron_parts['month'],
            )
            
            task_name = f"scheduled_job_{scheduled_job.id}"
            
            periodic_task = PeriodicTask.objects.create(
                crontab=schedule,
                name=task_name,
                task='scheduler.tasks.execute_scheduled_job',
                args=[scheduled_job.id],
                enabled=scheduled_job.is_active,
            )
            
            scheduled_job.celery_task = periodic_task
            scheduled_job.save(update_fields=['celery_task'])
            
            return periodic_task
            
        except Exception as e:
            raise CeleryTaskException(f"Failed to create periodic task: {str(e)}")
    
    @classmethod
    def update_periodic_task(cls, scheduled_job):
        if not scheduled_job.celery_task:
            return cls.create_periodic_task(scheduled_job)
        
        try:
            cron_parts = scheduled_job.get_cron_parts()
            if not cron_parts:
                raise CeleryTaskException("Invalid cron expression")
            
            schedule, created = CrontabSchedule.objects.get_or_create(
                minute=cron_parts['minute'],
                hour=cron_parts['hour'],
                day_of_week=cron_parts['day_of_week'],
                day_of_month=cron_parts['day'],
                month_of_year=cron_parts['month'],
            )
            
            periodic_task = scheduled_job.celery_task
            periodic_task.crontab = schedule
            periodic_task.enabled = scheduled_job.is_active
            periodic_task.save()
            
            return periodic_task
            
        except Exception as e:
            raise CeleryTaskException(f"Failed to update periodic task: {str(e)}")
    
    @classmethod
    def delete_periodic_task(cls, scheduled_job):
        if scheduled_job.celery_task:
            try:
                scheduled_job.celery_task.delete()
            except Exception:
                pass
    
    @classmethod
    def pause_periodic_task(cls, scheduled_job):
        if scheduled_job.celery_task:
            scheduled_job.celery_task.enabled = False
            scheduled_job.celery_task.save()
    
    @classmethod
    def resume_periodic_task(cls, scheduled_job):
        if scheduled_job.celery_task:
            scheduled_job.celery_task.enabled = True
            scheduled_job.celery_task.save()
