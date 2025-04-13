from django.urls import path
from .views import *


urlpatterns = [
    path('', home, name='home'),
    path('login/', login_view, name='login'),
    path('signup/', signup_view, name='signup'),
    path('edit-profile/', EditProfileView.as_view(), name='edit_profile'),
    path('dashboard/', member_dashboard_view, name='member_dashboard'),
    path('search/', search_book_view, name='search_book'),
    path('books/', BookListView.as_view(), name='books_list'),

    path('borrow/<int:book_id>/', borrow_book, name='borrow_book'),
    path("api/borrowed-books/count/", total_borrowed_books, name="total-borrowed-books"),
    path("api/borrowed-books/due-soon/", books_due_soon, name="books-due-soon"),

    path('api/borrowed-books/', BorrowedBooksListView.as_view(), name='borrowed_books_list'),
    path('borrowed-books/', BorrowedBooksPageView.as_view(), name='borrowed_books'),

    # Returns & renewals
    path('return-renew/', ReturnedBooksPageView.as_view(), name='return_renew_page'),
    path('api/return-renew/', ReturnedBooksListView.as_view(), name='return_renew_list'),
    path('return/<int:record_id>/', return_book_view, name='return_book'),
    path('renew/<int:record_id>/', renew_book_view, name='renew_book'),

    # Fines
    path('fines/', FinesPageView.as_view(), name='fines_page'),
    path('api/fines/', ReturnedBooksListView.as_view(), name='fines_list'),  # reuse if needed
    path('fine/pay/<int:record_id>/', pay_fine_view, name='pay_fine'),

]
