from django.urls import path
from . import views

app_name = 'tasks'

urlpatterns = [
    path('available/', views.AvailableTasksListView.as_view(), name='available-tasks'),
]
