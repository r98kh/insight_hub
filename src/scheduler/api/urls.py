from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ScheduledJobViewSet, JobExecutionLogViewSet

app_name = 'scheduler'

router = DefaultRouter()
router.register(r'execution-logs', JobExecutionLogViewSet, basename='execution-log')

urlpatterns = [
    path('', include(router.urls)),
    path('', ScheduledJobViewSet.as_view({'get': 'list', 'post': 'create'}), name='scheduled-job-list'),
    path('<int:pk>/', ScheduledJobViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='scheduled-job-detail'),
]
