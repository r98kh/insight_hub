from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema

from ..models import ScheduledJob, JobExecutionLog
from .serializers import (
    ScheduledJobSerializer, ScheduledJobCreateSerializer,
    JobExecutionLogSerializer, AdvancedSearchSerializer
)
from .filtering import DynamicFilterBackend, DynamicOrderingFilter, AdvancedSearchFilter
from core.permissions import IsOwnerOrSuperuser, JobLimitPermission, TaskExecutionPermission
from core.pagination import SchedulePagination, ExecutionLogPagination
from core.mixins import OwnerOrSuperuserMixin, OptimizedQueryMixin
from ..services import JobLimitService, JobStatisticsService, JobExecutionService
from ..services.celery_service import CeleryTaskService
from ..repositories import ScheduledJobRepository, JobExecutionLogRepository
from ..tasks import execute_job_immediately
from core.exceptions import JobLimitExceededException, TaskExecutionException


class ScheduledJobViewSet(OwnerOrSuperuserMixin, OptimizedQueryMixin, viewsets.ModelViewSet):
    serializer_class = ScheduledJobSerializer
    permission_classes = [IsAuthenticated, JobLimitPermission]
    pagination_class = SchedulePagination
    filter_backends = [DynamicFilterBackend, DynamicOrderingFilter, AdvancedSearchFilter]
    ordering_fields = [
        'id', 'user', 'task_definition', 'cron_expression', 'is_active', 'status',
        'created_at', 'updated_at', 'last_run', 'next_run', 'max_executions',
        'execution_count', 'max_failures', 'consecutive_failures',
        'task_definition__name', 'task_definition__description',
        'user__username', 'user__email'
    ]
    search_fields = [
        'task_definition__name', 'task_definition__description',
        'cron_expression', 'user__username', 'user__email'
    ]
    
    def get_queryset(self):
        if self.request.user.is_superuser:
            return ScheduledJobRepository.get_all_jobs()
        return ScheduledJobRepository.get_user_jobs(self.request.user)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ScheduledJobCreateSerializer
        return ScheduledJobSerializer

    @swagger_auto_schema(
        operation_summary='List scheduled jobs',
        operation_description='Get paginated list of scheduled jobs with filtering options',
        tags=['ScheduledJob']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_summary='Create scheduled job',
        operation_description='Create a new scheduled job with cron expression and parameters',
        request_body=ScheduledJobCreateSerializer,
        tags=['ScheduledJob']
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_summary='Get scheduled job details',
        operation_description='Get detailed information about a specific scheduled job',
        tags=['ScheduledJob']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_summary='Update scheduled job',
        operation_description='Update an existing scheduled job',
        request_body=ScheduledJobSerializer,
        tags=['ScheduledJob']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_summary='Partially update scheduled job',
        operation_description='Partially update an existing scheduled job',
        request_body=ScheduledJobSerializer,
        tags=['ScheduledJob']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_summary='Delete scheduled job',
        operation_description='Delete a scheduled job and its associated periodic task',
        tags=['ScheduledJob']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        if not JobLimitService.can_create_job(self.request.user):
            raise JobLimitExceededException()
        
        scheduled_job = serializer.save(user=self.request.user)
        try:
            CeleryTaskService.create_periodic_task(scheduled_job)
            JobLimitService.invalidate_cache(self.request.user)
        except Exception as e:
            scheduled_job.delete()
            raise ValidationError({'error': f'Failed to create scheduled task: {str(e)}'})
    
    def perform_update(self, serializer):
        scheduled_job = serializer.save()
        try:
            CeleryTaskService.update_periodic_task(scheduled_job)
        except Exception as e:
            raise ValidationError({'error': f'Failed to update scheduled task: {str(e)}'})
    
    def perform_destroy(self, instance):
        try:
            CeleryTaskService.delete_periodic_task(instance)
            JobLimitService.invalidate_cache(instance.user)
        except Exception:
            pass
        instance.delete()

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy', 'pause', 'resume', 'execute_now']:
            return [IsAuthenticated(), IsOwnerOrSuperuser(), JobLimitPermission()]
        return [IsAuthenticated(), JobLimitPermission()]
    
    @swagger_auto_schema(
        operation_summary='Execute job immediately',
        operation_description='Execute a scheduled job immediately without waiting for the scheduled time',
        tags=['ScheduledJob - Job Control']
    )
    @action(detail=True, methods=['post'])
    def execute_now(self, request, pk=None):
        scheduled_job = self.get_object()
        
        if not scheduled_job.can_execute():
            raise TaskExecutionException("Job cannot be executed at this time")
        
        try:
            custom_params = request.data if request.data else {}
            job_params = scheduled_job.parameters.copy()
            job_params.update(custom_params)
            
            result = execute_job_immediately.delay(scheduled_job.id, custom_params)
            return Response({
                'message': 'Job execution started',
                'task_id': result.id
            })
        except Exception as e:
            raise TaskExecutionException(f'Failed to execute job: {str(e)}')
    
    @swagger_auto_schema(
        operation_summary='Pause scheduled job',
        operation_description='Pause a scheduled job to stop its execution',
        tags=['ScheduledJob - Job Control']
    )
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        scheduled_job = self.get_object()
        scheduled_job.is_active = False
        scheduled_job.status = 'paused'
        scheduled_job.save()
        
        try:
            CeleryTaskService.pause_periodic_task(scheduled_job)
            JobLimitService.invalidate_cache(scheduled_job.user)
        except Exception:
            pass
        
        return Response({'message': 'Job paused successfully'})
    
    @swagger_auto_schema(
        operation_summary='Resume scheduled job',
        operation_description='Resume a paused scheduled job to continue its execution',
        tags=['ScheduledJob - Job Control']
    )
    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        scheduled_job = self.get_object()
        scheduled_job.is_active = True
        scheduled_job.status = 'active'
        scheduled_job.save()
        
        try:
            CeleryTaskService.resume_periodic_task(scheduled_job)
            JobLimitService.invalidate_cache(scheduled_job.user)
        except Exception:
            pass
        
        return Response({'message': 'Job resumed successfully'})
    
    @swagger_auto_schema(
        operation_summary='Get user job statistics',
        operation_description='Get statistics about user\'s scheduled jobs and executions',
        tags=['ScheduledJob - Analytics & Reports']
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        stats = JobStatisticsService.get_user_statistics(request.user)
        return Response(stats)
    
    @swagger_auto_schema(
        operation_summary='Advanced search for scheduled jobs',
        operation_description='Search scheduled jobs with complex filters and sorting using POST method',
        request_body=AdvancedSearchSerializer,
        tags=['ScheduledJob - Advanced Search']
    )
    @action(detail=False, methods=['post'])
    def advanced_search(self, request):

        serializer = AdvancedSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        queryset = self.get_queryset()
        
        filters = serializer.validated_data.get('filters', {})
        if filters:
            filter_backend = DynamicFilterBackend()
            queryset = filter_backend.filter_queryset(request, queryset, self)
        
        search_query = serializer.validated_data.get('search', '')
        if search_query:
            search_backend = AdvancedSearchFilter()
            request.query_params = request.query_params.copy()
            request.query_params['search'] = search_query
            queryset = search_backend.filter_queryset(request, queryset, self)
        
        ordering = serializer.validated_data.get('ordering', [])
        if ordering:
            ordering_backend = DynamicOrderingFilter()
            request.data = request.data.copy()
            request.data['ordering'] = ordering
            queryset = ordering_backend.filter_queryset(request, queryset, self)
        
        page_size = serializer.validated_data.get('page_size', 10)
        page = serializer.validated_data.get('page', 1)
        
        start = (page - 1) * page_size
        end = start + page_size
        paginated_queryset = queryset[start:end]
        
        serializer_results = self.get_serializer(paginated_queryset, many=True)
        
        return Response({
            'results': serializer_results.data,
            'count': queryset.count(),
            'page': page,
            'page_size': page_size,
            'total_pages': (queryset.count() + page_size - 1) // page_size
        })


class JobExecutionLogViewSet(OwnerOrSuperuserMixin, OptimizedQueryMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = JobExecutionLogSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ExecutionLogPagination
    filter_backends = [DynamicFilterBackend, DynamicOrderingFilter, AdvancedSearchFilter]
    ordering_fields = [
        'id', 'scheduled_job', 'execution_time', 'status', 'started_at', 
        'completed_at', 'duration', 'celery_task_id',
        'scheduled_job__task_definition__name', 'scheduled_job__user__username'
    ]
    search_fields = [
        'scheduled_job__task_definition__name', 'status', 'error_message',
        'scheduled_job__user__username'
    ]
    
    @swagger_auto_schema(
        operation_summary='List execution logs',
        operation_description='Get paginated list of job execution logs with filtering options',
        tags=['JobExecutionLog']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_summary='Get execution log details',
        operation_description='Get detailed information about a specific execution log',
        tags=['JobExecutionLog']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    
    def get_queryset(self):
        if self.request.user.is_superuser:
            return JobExecutionLogRepository.get_all_execution_logs()
        return JobExecutionLogRepository.get_user_execution_logs(self.request.user)
    
    @swagger_auto_schema(
        operation_summary='Advanced search for execution logs',
        operation_description='Search execution logs with complex filters and sorting using POST method',
        request_body=AdvancedSearchSerializer,
        tags=['JobExecutionLog - Advanced Search']
    )
    @action(detail=False, methods=['post'])
    def advanced_search(self, request):
        serializer = AdvancedSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        queryset = self.get_queryset()
        
        filters = serializer.validated_data.get('filters', {})
        if filters:
            filter_backend = DynamicFilterBackend()
            queryset = filter_backend.filter_queryset(request, queryset, self)
        
        search_query = serializer.validated_data.get('search', '')
        if search_query:
            search_backend = AdvancedSearchFilter()
            request.query_params = request.query_params.copy()
            request.query_params['search'] = search_query
            queryset = search_backend.filter_queryset(request, queryset, self)
        
        ordering = serializer.validated_data.get('ordering', [])
        if ordering:
            ordering_backend = DynamicOrderingFilter()
            request.data = request.data.copy()
            request.data['ordering'] = ordering
            queryset = ordering_backend.filter_queryset(request, queryset, self)
        
        page_size = serializer.validated_data.get('page_size', 20)
        page = serializer.validated_data.get('page', 1)
        
        start = (page - 1) * page_size
        end = start + page_size
        paginated_queryset = queryset[start:end]
        
        serializer_results = self.get_serializer(paginated_queryset, many=True)
        
        return Response({
            'results': serializer_results.data,
            'count': queryset.count(),
            'page': page,
            'page_size': page_size,
            'total_pages': (queryset.count() + page_size - 1) // page_size
        })
