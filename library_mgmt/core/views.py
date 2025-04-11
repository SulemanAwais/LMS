from django.contrib import messages
from django.contrib.auth import authenticate, login, get_user
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.shortcuts import render, redirect
from django.urls import reverse
from rest_framework.generics import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from .forms import LoginForm
from .models import Book, BorrowRecord


def home(request):
    return render(request, 'core/home.html')


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            dashboard_url = reverse('member_dashboard')
            return redirect(dashboard_url)
        else:
            messages.error(request, 'Invalid form submission')
    else:
        form = LoginForm()
    return render(request, 'core/login.html', {'form': form})


def signup_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()

    return render(request, 'core/signup.html', {'form': form})


@login_required
def member_dashboard_view(request):
    return render(request, 'core/member_dashboard.html')

@login_required
def search_book_view(request):
    books = Book.objects.all()
    return render(request, 'core/search_book.html', {'books': books})


from django.db.models import Q
from django_datatables_view.base_datatable_view import BaseDatatableView


class BookListView(BaseDatatableView):
    model = Book
    columns = ['id', 'title', 'author', 'isbn', 'edition', 'publisher', 'available_copies', 'genre']

    def get_initial_queryset(self):
        queryset = Book.objects.all()

        # Get search value from the AJAX request
        search_value = self.request.GET.get('searchTerm', None)
        genre_filter = self.request.GET.get('genre', None)
        availability_filter = self.request.GET.get('availability', None)

        if search_value:
            queryset = queryset.filter(
                Q(title__icontains=search_value) |
                Q(author__icontains=search_value) |
                Q(isbn__icontains=search_value) |
                Q(edition__icontains=search_value) |
                Q(publisher__icontains=search_value) |
                Q(language__icontains=search_value) |
                Q(genre__name__icontains=search_value)
            )

        # Apply genre filter if selected
        if genre_filter:
            queryset = queryset.filter(genre__name__iexact=genre_filter)

        # Apply availability filter if selected
        if availability_filter == "available":
            queryset = queryset.filter(available_copies__gt=0)
        elif availability_filter == "unavailable":
            queryset = queryset.filter(available_copies=0)

        return queryset

    def prepare_results(self, qs):
        return [
            {
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "isbn": book.isbn,
                "edition": book.edition,
                "publisher": book.publisher,
                "available_copies": book.available_copies,
                "genre": book.genre.name if book.genre else 'N/A'
            }
            for book in qs
        ]


@login_required
def borrow_book(request, book_id):
    # Fetch the book or return 404 if not found
    book = get_object_or_404(Book, pk=book_id)
    user = get_user(request)
    print("user:", user)
    # Check if there are available copies of the book
    if book.available_copies > 0:
        # Reduce available copies by 1
        book.available_copies -= 1
        book.save()

        # Calculate due date (e.g., 14 days from the borrow date)
        due_date = timezone.now().date() + timedelta(days=14)

        # Create a BorrowRecord to track the borrowing
        BorrowRecord.objects.create(
            user=user,
            book=book,
            due_date=due_date
        )

        # Success message
        messages.success(request, f'You have successfully borrowed "{book.title}".')

    else:
        # No available copies, show an error message
        messages.error(request, f'Sorry, "{book.title}" is currently not available.')

    # Redirect to the book list or a specific borrow confirmation page
    return redirect('book-list')