from django.db.models import QuerySet
from typing import Optional, Dict, Any
from ..models import TaskDefinition, TaskParameter


class TaskDefinitionRepository:
    @staticmethod
    def get_active_tasks() -> QuerySet:
        return TaskDefinition.objects.filter(is_active=True).prefetch_related(
            'taskparameter_set'
        ).order_by('name')
    
    @staticmethod
    def get_task_by_id(task_id: int) -> Optional[TaskDefinition]:
        try:
            return TaskDefinition.objects.select_related().prefetch_related(
                'taskparameter_set'
            ).get(id=task_id)
        except TaskDefinition.DoesNotExist:
            return None
    
    @staticmethod
    def get_task_by_name(name: str) -> Optional[TaskDefinition]:
        try:
            return TaskDefinition.objects.get(name=name)
        except TaskDefinition.DoesNotExist:
            return None
    
    @staticmethod
    def search_tasks(query: str) -> QuerySet:
        return TaskDefinition.objects.filter(
            name__icontains=query
        ).prefetch_related('taskparameter_set')
    
    @staticmethod
    def create_task(task_data: Dict[str, Any]) -> TaskDefinition:
        return TaskDefinition.objects.create(**task_data)
    
    @staticmethod
    def update_task(task: TaskDefinition, task_data: Dict[str, Any]) -> TaskDefinition:
        for field, value in task_data.items():
            setattr(task, field, value)
        task.save()
        return task
    
    @staticmethod
    def delete_task(task: TaskDefinition) -> bool:
        try:
            task.is_active = False
            task.save()
            return True
        except Exception:
            return False


class TaskParameterRepository:
    @staticmethod
    def get_parameters_for_task(task_definition: TaskDefinition) -> QuerySet:
        return TaskParameter.objects.filter(
            task_definition=task_definition,
            is_active=True
        ).order_by('parameter_name')
    
    @staticmethod
    def get_parameter_by_name(task_definition: TaskDefinition, param_name: str) -> Optional[TaskParameter]:
        try:
            return TaskParameter.objects.get(
                task_definition=task_definition,
                parameter_name=param_name
            )
        except TaskParameter.DoesNotExist:
            return None
    
    @staticmethod
    def create_parameter(task_definition: TaskDefinition, param_data: Dict[str, Any]) -> TaskParameter:
        param_data['task_definition'] = task_definition
        return TaskParameter.objects.create(**param_data)
    
    @staticmethod
    def update_parameter(parameter: TaskParameter, param_data: Dict[str, Any]) -> TaskParameter:
        for field, value in param_data.items():
            setattr(parameter, field, value)
        parameter.save()
        return parameter
    
    @staticmethod
    def delete_parameter(parameter: TaskParameter) -> bool:
        try:
            parameter.is_active = False
            parameter.save()
            return True
        except Exception:
            return False
