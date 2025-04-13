from django.contrib import admin
from .models import Book, Genre, User, BorrowRecord, Payment, Fine, Library

admin.site.register(Book)
admin.site.register(Genre)
admin.site.register(User)
admin.site.register(BorrowRecord)
admin.site.register(Payment)
admin.site.register(Fine)
admin.site.register(Library)
