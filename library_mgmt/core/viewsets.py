# views.py
from rest_framework.response import Response
from rest_framework_datatables.pagination import DatatablesPageNumberPagination
from rest_framework import viewsets
from .models import Book
from .serializers import BookSerializer


class BookDatatableViewSet(viewsets.ModelViewSet):
    serializer_class = BookSerializer
    def __init__(self, **kwargs):

        super().__init__(**kwargs)
        print("lmwdnjnsf")
    queryset = Book.objects.all()

    def retrieve(self, request, pk=None):
        queryset = Book.objects.all()
        serializer = BookSerializer(queryset, many=True)
        return Response(serializer.data)
    # def get_queryset(self):
    #     return Book.objects.all()
#