from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.shortcuts import render, redirect
from django.urls import reverse

from .forms import LoginForm
from .models import Book


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
    columns = ['title', 'author', 'isbn', 'edition', 'publisher', 'available_copies', 'genre']

    def get_initial_queryset(self):
        queryset = Book.objects.all()

        # Get search value from the AJAX request
        search_value = self.request.GET.get('searchTerm', None)

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

        return queryset

    def prepare_results(self, qs):
        return [
            {
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