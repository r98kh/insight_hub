from rest_framework.filters import BaseFilterBackend, OrderingFilter
from django.db.models import Q
from django.core.exceptions import FieldError
import json
import logging

logger = logging.getLogger(__name__)


class DynamicFilterBackend(BaseFilterBackend):
    
    def filter_queryset(self, request, queryset, view):
        filters = self._extract_filters(request)
        
        if not filters:
            return queryset
        
        try:
            queryset = self._apply_filters(queryset, filters, view)
        except (FieldError, ValueError, TypeError) as e:
            logger.warning(f"Invalid filter applied: {e}")
            return queryset
        
        return queryset
    
    def _extract_filters(self, request):
        filters = {}
        
        if request.method == 'POST' and hasattr(request, 'data'):
            body_filters = request.data.get('filters', {})
            if isinstance(body_filters, dict):
                filters.update(body_filters)
        
        query_filters = request.query_params.get('filters')
        if query_filters:
            try:
                if isinstance(query_filters, str):
                    parsed_filters = json.loads(query_filters)
                else:
                    parsed_filters = query_filters
                
                if isinstance(parsed_filters, dict):
                    filters.update(parsed_filters)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON in filters query parameter")
        
        for key, value in request.query_params.items():
            if key not in ['filters', 'ordering', 'page', 'page_size']:
                filters[key] = value
        
        return filters
    
    def _apply_filters(self, queryset, filters, view):
        q_objects = []
        
        for field, value in filters.items():
            if not value or value == '':
                continue
            
            if field.endswith('__isnull'):
                field_name = field.replace('__isnull', '')
                q_objects.append(Q(**{field_name + '__isnull': value.lower() == 'true'}))
            elif field.endswith('__in'):
                if isinstance(value, str):
                    value = [v.strip() for v in value.split(',')]
                q_objects.append(Q(**{field: value}))
            elif field.endswith('__range'):
                if isinstance(value, str):
                    try:
                        start, end = value.split(',')
                        q_objects.append(Q(**{field.replace('__range', '__gte'): start.strip()}))
                        q_objects.append(Q(**{field.replace('__range', '__lte'): end.strip()}))
                    except ValueError:
                        continue
                else:
                    continue
            elif field.endswith('__date'):
                field_name = field.replace('__date', '')
                q_objects.append(Q(**{field_name + '__date': value}))
            elif field.endswith('__year'):
                field_name = field.replace('__year', '')
                q_objects.append(Q(**{field_name + '__year': value}))
            elif field.endswith('__month'):
                field_name = field.replace('__month', '')
                q_objects.append(Q(**{field_name + '__month': value}))
            elif field.endswith('__day'):
                field_name = field.replace('__day', '')
                q_objects.append(Q(**{field_name + '__day': value}))
            else:
                if '__' in field and not any(field.endswith(suffix) for suffix in 
                    ['__gte', '__lte', '__gt', '__lt', '__icontains', '__contains', 
                     '__exact', '__iexact', '__startswith', '__istartswith', 
                     '__endswith', '__iendswith']):
                    try:
                        q_objects.append(Q(**{field: value}))
                    except FieldError:
                        q_objects.append(Q(**{field + '__exact': value}))
                else:
                    q_objects.append(Q(**{field: value}))
        
        if q_objects:
            queryset = queryset.filter(*q_objects)
        
        return queryset


class DynamicOrderingFilter(OrderingFilter):
    
    def get_ordering(self, request, queryset, view):
        ordering = []
        
        if request.method == 'POST' and hasattr(request, 'data'):
            body_ordering = request.data.get('ordering', [])
            if isinstance(body_ordering, list):
                ordering.extend(body_ordering)
        
        query_ordering = request.query_params.get('ordering')
        if query_ordering:
            try:
                if isinstance(query_ordering, str):
                    parsed_ordering = json.loads(query_ordering)
                else:
                    parsed_ordering = query_ordering
                
                if isinstance(parsed_ordering, list):
                    ordering.extend(parsed_ordering)
                elif isinstance(parsed_ordering, str):
                    ordering.append(parsed_ordering)
            except json.JSONDecodeError:
                ordering.extend([o.strip() for o in query_ordering.split(',')])
        
        order_param = request.query_params.get('order')
        if order_param:
            ordering.append(order_param)
        
        ordering = self._validate_ordering_fields(ordering, view)
        
        return ordering
    
    def _validate_ordering_fields(self, ordering, view):
        if not ordering:
            return self.get_default_ordering(view)
        
        allowed_fields = getattr(view, 'ordering_fields', None)
        if not allowed_fields:
            model = view.get_queryset().model
            allowed_fields = [
                'id', 'created_at', 'updated_at'
            ]
            
            for field in model._meta.fields:
                if field.name not in allowed_fields:
                    allowed_fields.append(field.name)
            
            for field in model._meta.get_fields():
                if hasattr(field, 'related_model') and field.related_model:
                    allowed_fields.extend([
                        f"{field.name}__id",
                        f"{field.name}__name",
                        f"{field.name}__created_at"
                    ])
        
        validated_ordering = []
        for field in ordering:
            clean_field = field.lstrip('-')
            if clean_field in allowed_fields:
                validated_ordering.append(field)
            else:
                logger.warning(f"Invalid ordering field: {clean_field}")
        
        return validated_ordering if validated_ordering else self.get_default_ordering(view)


class AdvancedSearchFilter(BaseFilterBackend):
    
    def filter_queryset(self, request, queryset, view):
        search_query = request.query_params.get('search')
        if not search_query:
            return queryset
        
        search_fields = getattr(view, 'search_fields', [])
        if not search_fields:
            return queryset
        
        q_objects = Q()
        for field in search_fields:
            q_objects |= Q(**{f"{field}__icontains": search_query})
        
        return queryset.filter(q_objects)
