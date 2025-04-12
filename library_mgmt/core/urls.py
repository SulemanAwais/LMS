from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import home, login_view, signup_view, member_dashboard_view, search_book_view, BookListView, borrow_book, \
    total_borrowed_books, books_due_soon
from .viewsets import BookDatatableViewSet

router = DefaultRouter()
router.register(r'book', BookDatatableViewSet, basename='book')

urlpatterns = [
    path('', home, name='home'),
    path('api/', include(router.urls)),
    path('login/', login_view, name='login'),
    path('signup/', signup_view, name='signup'),
    path('dashboard/', member_dashboard_view, name='member_dashboard'),
    path('search/', search_book_view, name='search_book'),
    path('books/', BookListView.as_view(), name='book-list'),
    path('borrow/<int:book_id>/', borrow_book, name='borrow_book'),
    path("api/borrowed-books/count/", total_borrowed_books, name="total-borrowed-books"),
    path("api/borrowed-books/due-soon/", books_due_soon, name="books-due-soon"),


]
