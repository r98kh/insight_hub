from django.core.management.base import BaseCommand
from tasks.models import TaskDefinition, TaskParameter
from tasks.task_functions import AVAILABLE_TASK_FUNCTIONS


class Command(BaseCommand):
    help = 'Populate database with predefined task definitions'

    def handle(self, *args, **options):
        self.stdout.write('Creating predefined task definitions...')
        
        created_count = 0
        updated_count = 0
        
        for task_name, task_info in AVAILABLE_TASK_FUNCTIONS.items():
            # Create or update TaskDefinition
            task_def, created = TaskDefinition.objects.get_or_create(
                name=task_name.replace('_', ' ').title(),
                defaults={
                    'description': task_info['description'],
                    'function_path': f'tasks.task_functions.{task_name}',
                    'is_active': True,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(f'Created task: {task_def.name}')
            else:
                updated_count += 1
                self.stdout.write(f'Updated task: {task_def.name}')
            
            # Create TaskParameters
            for param_info in task_info['parameters']:
                TaskParameter.objects.get_or_create(
                    task_definition=task_def,
                    parameter_name=param_info['name'],
                    defaults={
                        'parameter_type': param_info['type'],
                        'is_required': param_info['required'],
                        'description': param_info['description'],
                        'is_active': True,
                    }
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully processed {len(AVAILABLE_TASK_FUNCTIONS)} tasks. '
                f'Created: {created_count}, Updated: {updated_count}'
            )
        )
