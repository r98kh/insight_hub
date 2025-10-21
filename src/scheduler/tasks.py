from celery import shared_task
from django.utils import timezone
from django.db import transaction
import logging

from .models import ScheduledJob, JobExecutionLog
from .services import TaskFunctionService, CronService, SystemStatisticsService, JobSyncService

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def execute_scheduled_job(self, scheduled_job_id):

    try:
        scheduled_job = ScheduledJob.objects.get(id=scheduled_job_id)
        
        if not scheduled_job.can_execute():
            logger.warning(f"Scheduled job {scheduled_job_id} cannot be executed")
            return {
                'status': 'skipped',
                'reason': 'Job cannot be executed',
                'scheduled_job_id': scheduled_job_id
            }
        
        execution_log = JobExecutionLog.objects.create(
            scheduled_job=scheduled_job,
            execution_time=timezone.now()
        )
        
        execution_log.mark_as_started(self.request.id)
        
        try:
            task_function = TaskFunctionService.get_task_function(scheduled_job.task_definition.function_path)
            result = task_function(**scheduled_job.parameters)
            
            execution_log.mark_as_completed(result)
            
            with transaction.atomic():
                scheduled_job.increment_execution_count()
                scheduled_job.reset_failure_count()
                scheduled_job.last_run = timezone.now()
                scheduled_job.next_run = CronService.get_next_run_time(scheduled_job.cron_expression)
                scheduled_job.save(update_fields=['execution_count', 'consecutive_failures', 'last_run', 'next_run'])
            
            logger.info(f"Successfully executed scheduled job {scheduled_job_id}")
            
            return {
                'status': 'success',
                'result': result,
                'execution_log_id': execution_log.id,
                'scheduled_job_id': scheduled_job_id
            }
            
        except Exception as e:
            execution_log.mark_as_failed(str(e))
            
            with transaction.atomic():
                scheduled_job.increment_failure_count()
                scheduled_job.last_run = timezone.now()
                scheduled_job.save(update_fields=['consecutive_failures', 'last_run'])
            
            logger.error(f"Failed to execute scheduled job {scheduled_job_id}: {e}")
            
            return {
                'status': 'failed',
                'error': str(e),
                'execution_log_id': execution_log.id,
                'scheduled_job_id': scheduled_job_id
            }
            
    except ScheduledJob.DoesNotExist:
        logger.error(f"Scheduled job {scheduled_job_id} not found")
        return {
            'status': 'error',
            'error': 'Scheduled job not found',
            'scheduled_job_id': scheduled_job_id
        }
    except Exception as e:
        logger.error(f"Unexpected error executing scheduled job {scheduled_job_id}: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'scheduled_job_id': scheduled_job_id
        }

@shared_task
def sync_scheduled_jobs():

    try:
        JobSyncService.sync_all_scheduled_jobs()
        JobSyncService.cleanup_orphaned_tasks()
        
        logger.info("Successfully synced scheduled jobs")
        return {
            'status': 'success',
            'message': 'Scheduled jobs synced successfully'
        }
        
    except Exception as e:
        logger.error(f"Error syncing scheduled jobs: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task
def health_check():

    try:
        stats = SystemStatisticsService.get_job_statistics()
        
        jobs_without_task = stats.get('jobs_without_celery_task', 0)
        if jobs_without_task > 0:
            logger.warning(f"{jobs_without_task} jobs without celery task")
        
        failed_jobs = stats.get('failed_jobs', 0)
        if failed_jobs > 0:
            logger.warning(f"{failed_jobs} jobs with consecutive failures")
        
        return {
            'status': 'healthy',
            'statistics': stats,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def execute_job_immediately(scheduled_job_id, custom_params=None):

    try:
        scheduled_job = ScheduledJob.objects.get(id=scheduled_job_id)
        
        if not scheduled_job.can_execute():
            return {
                'status': 'skipped',
                'reason': 'Job cannot be executed',
                'scheduled_job_id': scheduled_job_id
            }
        
        original_params = None
        if custom_params:
            original_params = scheduled_job.parameters.copy()
            scheduled_job.parameters.update(custom_params)
            scheduled_job.save(update_fields=['parameters'])
            
        try:
            result = execute_scheduled_job(scheduled_job_id)
            return result
        finally:
            if original_params is not None:
                scheduled_job.parameters = original_params
                scheduled_job.save(update_fields=['parameters'])
        
    except ScheduledJob.DoesNotExist:
        logger.error(f"Scheduled job {scheduled_job_id} not found")
        return {
            'status': 'error',
            'error': 'Scheduled job not found',
            'scheduled_job_id': scheduled_job_id
        }
    except Exception as e:
        logger.error(f"Error executing job immediately: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'scheduled_job_id': scheduled_job_id
        }
