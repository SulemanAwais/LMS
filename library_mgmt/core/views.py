import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django_datatables_view.base_datatable_view import BaseDatatableView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, get_user
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q
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
    return render(request, 'core/book_list.html', {'books': books})


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
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        data = json.loads(request.body)
        borrow_period = int(data.get("borrowing_period", 3))  # Default to 3 days if not provided
        is_reserved = data.get("is_reserved", False)  # Default to borrow (not reserve)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"error": "Invalid request data"}, status=400)

    # Validate borrowing period based on request type
    if is_reserved and borrow_period not in [1, 2]:
        return JsonResponse({"error": "Invalid reservation period. Must be 1 or 2 days."}, status=400)
    elif not is_reserved and borrow_period not in [3, 7, 15]:
        return JsonResponse({"error": "Invalid borrowing period. Must be 3, 7, or 15 days."}, status=400)

    book = get_object_or_404(Book, pk=book_id)
    user = get_user(request)

    if book.available_copies <= 0:
        return JsonResponse({"error": f'Sorry, "{book.title}" is currently not available.'}, status=400)

    # Calculate due date
    due_date = timezone.now().date() + timedelta(days=borrow_period)

    book.available_copies -= 1
    book.save()

    # Create borrow record
    BorrowRecord.objects.create(
        user=user,
        book=book,
        due_date=due_date,
        is_reserved=is_reserved,
    )

    if is_reserved:
        return JsonResponse({
            "message": f'You have successfully reserved "{book.title}" for pickup. Please collect within {borrow_period} days.',
            "due_date": due_date.strftime("%Y-%m-%d")
        })
    else:
        return JsonResponse({
            "message": f'You have successfully borrowed "{book.title}" for {borrow_period} days.',
            "due_date": due_date.strftime("%Y-%m-%d")
        })


@login_required
def total_borrowed_books(request):
    count = BorrowRecord.objects.filter(return_date__isnull=True).count()
    return JsonResponse({"total_borrowed_books": count})


@login_required
def books_due_soon(request):
    today = timezone.now().date()
    upcoming_due_date = today + timedelta(days=4)
    due_soon_books = BorrowRecord.objects.filter(
        due_date__lte=upcoming_due_date,
        return_date__isnull=True
    ).select_related("book")

    books_list = [
        {
            "title": record.book.title,
            "due_date": record.due_date.strftime("%Y-%m-%d"),
            "borrower": record.user.username
        }
        for record in due_soon_books
    ]

    return JsonResponse({"books_due_soon": books_list})


class BorrowedBooksListView(BaseDatatableView):
    model = BorrowRecord
    columns = ['id', 'title', 'author', 'borrow_date', 'due_date', 'returned', 'renew_count', 'return_date']

    def get_initial_queryset(self):
        user = self.request.user
        queryset = BorrowRecord.objects.filter(user=user).select_related('book')
        search_value = self.request.GET.get('searchTerm', None)
        return_filter = self.request.GET.get('status', None)
        if search_value:
            queryset = queryset.filter(
                Q(book__title__icontains=search_value) |
                Q(book__author__icontains=search_value)
            )

        if return_filter == 'current':
            queryset = queryset.filter(returned=False)
        elif return_filter == 'returned':
            queryset = queryset.filter(returned=True)

        return queryset

    def prepare_results(self, qs):
        return [
            {
                "id": record.id,
                "title": record.book.title,
                "author": record.book.author,
                "borrow_date": record.borrow_date.strftime("%Y-%m-%d"),
                "due_date": record.due_date.strftime("%Y-%m-%d"),
                "returned": "Yes" if record.returned else "No",
                "renew_count": record.renew_count,
                "return_date": record.return_date.strftime("%Y-%m-%d") if record.return_date else "N/A",
            }
            for record in qs
        ]


class BorrowedBooksPageView(LoginRequiredMixin, TemplateView):
    template_name = 'core/borrowed_books_list.html'


class ReturnedBooksListView(BaseDatatableView):
    model = BorrowRecord
    columns = ['id', 'title', 'author', 'return_date', 'fine_paid']

    def get_initial_queryset(self):
        return BorrowRecord.objects.filter(user=self.request.user, returned=True).select_related('book')

    def prepare_results(self, qs):
        return [
            {
                "id": record.id,
                "title": record.book.title,
                "author": record.book.author,
                "return_date": record.return_date.strftime("%Y-%m-%d"),
                "fine_paid": "Yes" if getattr(record, 'fine_paid', False) else "No",
            }
            for record in qs
        ]


class ReturnedBooksPageView(LoginRequiredMixin, TemplateView):
    template_name = 'core/return_renew_books_list.html'


class FinesPageView(LoginRequiredMixin, TemplateView):
    template_name = 'core/fines_list.html'


class EditProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'core/edit_profile.html'


@login_required
def pay_fine_view(request, record_id):
    record = get_object_or_404(BorrowRecord, id=record_id, user=request.user)

    today = timezone.now().date()
    overdue_days = (today - record.due_date).days

    if overdue_days <= 0:
        return JsonResponse({"message": "No fine due."})

    fine_amount = overdue_days * 10  # Rs.10/day

    # Simulate payment
    record.fine_paid = True
    record.save()

    return JsonResponse({
        "message": f"Fine of Rs.{fine_amount} paid successfully for \"{record.book.title}\".",
        "amount_paid": fine_amount
    })


@login_required
def renew_book_view(request, record_id):
    record = get_object_or_404(BorrowRecord, id=record_id, user=request.user)

    if record.returned:
        return JsonResponse({"error": "Cannot renew a returned book."}, status=400)

    record.due_date += timedelta(days=7)
    record.renew_count += 1
    record.save()

    return JsonResponse({
        "message": f'Book "{record.book.title}" renewed for 7 more days.',
        "new_due_date": record.due_date.strftime("%Y-%m-%d")
    })


@login_required
def return_book_view(request, record_id):
    try:
        print("record_id", record_id, request.user)

        record = get_object_or_404(BorrowRecord, id=record_id, user=request.user)
        print("pass")
        if record.returned:
            return JsonResponse({"error": "Book already returned."}, status=400)
        print("record", record.returned)
        record.returned = True
        record.return_date = timezone.now().date()
        record.book.available_copies += 1
        record.book.save()
        record.save()

        return JsonResponse({"message": f'Book "{record.book.title}" returned successfully.'})
    except Exception as e:
        print(e)
