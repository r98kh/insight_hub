from rest_framework.exceptions import APIException
from rest_framework import status


class JobLimitExceededException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Job limit exceeded for user'
    default_code = 'job_limit_exceeded'


class CronValidationException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid cron expression'
    default_code = 'invalid_cron'


class TaskExecutionException(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Task execution failed'
    default_code = 'task_execution_failed'


class ParameterValidationException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid parameters provided'
    default_code = 'invalid_parameters'


class PermissionDeniedException(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Permission denied'
    default_code = 'permission_denied'


class ResourceNotFoundException(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Resource not found'
    default_code = 'resource_not_found'


class CeleryTaskException(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Celery task operation failed'
    default_code = 'celery_task_failed'
