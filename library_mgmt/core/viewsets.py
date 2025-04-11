# views.py
from rest_framework.response import Response
from rest_framework_datatables.pagination import DatatablesPageNumberPagination
from rest_framework import viewsets
from .models import Book
from .serializers import BookSerializer


class BookDatatableViewSet(viewsets.ModelViewSet):
    serializer_class = BookSerializer
    queryset = Book.objects.all()

    def retrieve(self, request, pk=None):
        queryset = Book.objects.all()
        serializer = BookSerializer(queryset, many=True)
        return Response(serializer.data)
#