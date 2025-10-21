from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet
from core.permissions import IsOwnerOrSuperuser, ReadOnlyOrOwnerPermission


class OwnerOrSuperuserMixin:
    def get_queryset(self):
        if self.request.user.is_superuser:
            return self.queryset.all()
        return self.queryset.filter(user=self.request.user)


class OptimizedQueryMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related(
            'user', 'task_definition'
        ).prefetch_related(
            'task_definition__taskparameter_set'
        )


class ReadOnlyOwnerOrSuperuserViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    GenericViewSet
):
    permission_classes = [ReadOnlyOrOwnerPermission]


class OwnerOrSuperuserViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    GenericViewSet
):
    permission_classes = [IsOwnerOrSuperuser]
