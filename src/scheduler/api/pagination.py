from rest_framework.pagination import PageNumberPagination


class SchedulePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_page_size(self, request):
        if request.user.is_superuser:
            return min(int(request.query_params.get('page_size', self.page_size)), self.max_page_size)
        else:
            return min(int(request.query_params.get('page_size', self.page_size)), 10)


class ExecutionLogPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
