from django.db import models
from django.core.validators import MinLengthValidator
from django.utils import timezone


class TaskDefinition(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name="Task Name",
    )
    description = models.TextField(
        verbose_name="Description",
    )
    function_path = models.CharField(
        max_length=200,
        verbose_name="Function Path",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Active",
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Created At"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated At"
    )

    class Meta:
        verbose_name = "Task Definition"
        verbose_name_plural = "Task Definitions"
        ordering = ['name']
        unique_together = ['name', 'function_path']


    def get_parameters(self):
        return self.taskparameter_set.filter(is_active=True).order_by('parameter_name')


class TaskParameter(models.Model):
    PARAMETER_TYPES = [
        ('string', 'String'),
        ('integer', 'Integer'),
        ('float', 'Float'),
        ('boolean', 'Boolean'),
        ('email', 'Email'),
        ('url', 'URL'),
        ('date', 'Date'),
        ('datetime', 'DateTime'),
        ('file', 'File'),
        ('json', 'JSON'),
    ]

    task_definition = models.ForeignKey(
        TaskDefinition,
        on_delete=models.CASCADE,
        verbose_name="Task Definition",
        related_name='taskparameter_set'
    )
    parameter_name = models.CharField(
        max_length=50,
        verbose_name="Parameter Name",
    )
    parameter_type = models.CharField(
        max_length=20,
        choices=PARAMETER_TYPES,
        verbose_name="Parameter Type"
    )
    is_required = models.BooleanField(
        default=True,
        verbose_name="Required",
    )
    default_value = models.TextField(
        blank=True,
        null=True,
        verbose_name="Default Value",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Parameter Description",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Active"
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Created At"
    )

    class Meta:
        verbose_name = "Task Parameter"
        verbose_name_plural = "Task Parameters"
        ordering = ['task_definition', 'parameter_name']
        unique_together = ['task_definition', 'parameter_name']
