from django.core.cache import cache
from django.conf import settings
from core.exceptions import ResourceNotFoundException, ParameterValidationException
from ..models import TaskDefinition, TaskParameter
from ..repositories import TaskDefinitionRepository, TaskParameterRepository


class TaskDefinitionService:
    @classmethod
    def get_available_tasks(cls):
        cache_key = 'available_tasks'
        cached_tasks = cache.get(cache_key)
        
        if cached_tasks is None:
            cached_tasks = TaskDefinitionRepository.get_active_tasks()
            cache.set(cache_key, cached_tasks, settings.CACHE_TTL['task_definitions'])
        
        return cached_tasks
    
    @classmethod
    def get_task_by_id(cls, task_id: int):
        task = TaskDefinitionRepository.get_task_by_id(task_id)
        if not task:
            raise ResourceNotFoundException("Task not found")
        return task
    
    @classmethod
    def create_task(cls, task_data):
        
        cls._validate_function_path(task_data.get('function_path'))
        
        task = TaskDefinitionRepository.create_task(task_data)
        
        cls.invalidate_cache()
        
        return task
    
    @classmethod
    def update_task(cls, task_id: int, task_data):
        task = cls.get_task_by_id(task_id)
        
        if 'function_path' in task_data:
            cls._validate_function_path(task_data['function_path'])
        
        updated_task = TaskDefinitionRepository.update_task(task, task_data)
        
        cls.invalidate_cache()
        
        return updated_task
    
    @classmethod
    def delete_task(cls, task_id: int):
        task = cls.get_task_by_id(task_id)
        
        if task.scheduled_jobs.exists():
            raise ParameterValidationException("Cannot delete task that is being used by scheduled jobs")
        
        TaskDefinitionRepository.delete_task(task)
        
        cls.invalidate_cache()
        
        return True
    
    @classmethod
    def search_tasks(cls, query: str):
        return TaskDefinitionRepository.search_tasks(query)
    
    @classmethod
    def _validate_function_path(cls, function_path: str):
        try:
            module_path, function_name = function_path.rsplit('.', 1)
            import importlib
            module = importlib.import_module(module_path)
            function = getattr(module, function_name)
            
            if not callable(function):
                raise ParameterValidationException(f"Function {function_path} is not callable")
                
        except (ImportError, AttributeError, ValueError) as e:
            raise ParameterValidationException(f"Invalid function path: {function_path}")
    
    @classmethod
    def invalidate_cache(cls):
        cache.delete('available_tasks')


class TaskParameterService:
    @classmethod
    def get_task_parameters(cls, task_definition: TaskDefinition):
        return TaskParameterRepository.get_parameters_for_task(task_definition)
    
    @classmethod
    def create_parameter(cls, task_id: int, param_data):
        task = TaskDefinitionService.get_task_by_id(task_id)
        
        existing_param = TaskParameterRepository.get_parameter_by_name(task, param_data['parameter_name'])
        if existing_param:
            raise ParameterValidationException(f"Parameter '{param_data['parameter_name']}' already exists")
        
        parameter = TaskParameterRepository.create_parameter(task, param_data)
        
        TaskDefinitionService.invalidate_cache()
        
        return parameter
    
    @classmethod
    def update_parameter(cls, task_id: int, param_id: int, param_data):
        task = TaskDefinitionService.get_task_by_id(task_id)
        
        try:
            parameter = TaskParameter.objects.get(id=param_id, task_definition=task)
        except TaskParameter.DoesNotExist:
            raise ResourceNotFoundException("Parameter not found")
        
        updated_parameter = TaskParameterRepository.update_parameter(parameter, param_data)
        
        TaskDefinitionService.invalidate_cache()
        
        return updated_parameter
    
    @classmethod
    def delete_parameter(cls, task_id: int, param_id: int):
        task = TaskDefinitionService.get_task_by_id(task_id)
        
        try:
            parameter = TaskParameter.objects.get(id=param_id, task_definition=task)
        except TaskParameter.DoesNotExist:
            raise ResourceNotFoundException("Parameter not found")
        
        TaskParameterRepository.delete_parameter(parameter)
        
        TaskDefinitionService.invalidate_cache()
        
        return True


class TaskExecutionService:
    @classmethod
    def execute_task(cls, task_definition: TaskDefinition, parameters: dict):
        cls._validate_parameters(task_definition, parameters)
        
        from scheduler.services import TaskFunctionService
        task_function = TaskFunctionService.get_task_function(task_definition.function_path)
        
        try:
            result = task_function(**parameters)
            return {
                'status': 'success',
                'result': result
            }
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    @classmethod
    def _validate_parameters(cls, task_definition: TaskDefinition, parameters: dict):
        task_params = TaskParameterRepository.get_parameters_for_task(task_definition)
        
        for param in task_params:
            param_name = param.parameter_name
            
            if param.is_required and param_name not in parameters:
                raise ParameterValidationException(f"Required parameter '{param_name}' is missing")
            
            if param_name in parameters:
                value = parameters[param_name]
                if not cls._validate_parameter_type(value, param.parameter_type):
                    raise ParameterValidationException(f"Parameter '{param_name}' has invalid type")
    
    @classmethod
    def _validate_parameter_type(cls, value, param_type: str) -> bool:
        try:
            if param_type == 'string':
                return isinstance(value, str)
            elif param_type == 'integer':
                return isinstance(value, int)
            elif param_type == 'float':
                return isinstance(value, (int, float))
            elif param_type == 'boolean':
                return isinstance(value, bool)
            elif param_type == 'email':
                return isinstance(value, str) and '@' in value
            elif param_type == 'url':
                return isinstance(value, str) and value.startswith(('http://', 'https://'))
            elif param_type == 'json':
                import json
                json.loads(value) if isinstance(value, str) else json.dumps(value)
                return True
            else:
                return True
        except:
            return False
