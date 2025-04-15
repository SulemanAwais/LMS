import json
from functools import wraps
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST, require_http_methods
from django.views.generic import TemplateView
from django_datatables_view.base_datatable_view import BaseDatatableView
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, get_user, logout
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.db.models import Q, Sum, F, Count
from django.urls import reverse
from rest_framework.decorators import api_view
from rest_framework.generics import get_object_or_404
from django.utils import timezone
from datetime import timedelta, date, datetime

from rest_framework.response import Response

from .models import Book, BorrowRecord, Fine, Payment, Genre
from django.contrib.auth import get_user_model

from .serializers import GenreSerializer

User = get_user_model()


# Custom Decorators for Access Control
def staff_required(view_func):
    """Decorator for views that require staff status"""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if not request.user.is_staff:
            request.session['access_denied_message'] = "This action is restricted to library staff only."
            return redirect('access_denied')

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def member_required(view_func):
    """Decorator for views that require member status (non-staff)"""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if request.user.is_staff:
            request.session[
                'access_denied_message'] = "This action is for library members only. Staff accounts cannot perform member actions."
            return redirect('access_denied')

        return view_func(request, *args, **kwargs)

    return _wrapped_view


# For API views that return JSON responses
def staff_required_api(view_func):
    """Decorator for API views that require staff status"""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return HttpResponseForbidden("Staff access required")

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def member_required_api(view_func):
    """Decorator for API views that require member status"""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.is_staff:
            return HttpResponseForbidden("Member access required")

        return view_func(request, *args, **kwargs)

    return _wrapped_view


# Mixins for class-based views
class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            self.request.session['access_denied_message'] = "This action is restricted to library staff only."
            return redirect('access_denied')
        return redirect('login')


class MemberRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and not self.request.user.is_staff

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            self.request.session['access_denied_message'] = "This action is for library members only."
            return redirect('access_denied')
        return redirect('login')


# Access Denied View
@login_required
def access_denied(request):
    """View for access denied page"""
    # Default message
    message = "You don't have permission to access this resource."

    # Get custom message from session if available
    if 'access_denied_message' in request.session:
        message = request.session.pop('access_denied_message')

    return render(request, 'access_denied.html', {'message': message})


# Basic views
def home(request):
    if request.user.is_authenticated:
        print("staff", request.user.is_staff)
        if request.user.is_staff:
            return redirect('librarian_dashboard')
        else:
            return redirect(reverse('member_dashboard'))
    return render(request, 'core/home.html')


def about_view(request):
    return render(request, 'core/about.html')


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            # Check if the user's account is active
            if not user.is_active:
                messages.error(request, "Your account has been suspended by the librarian.")
                return redirect('login')  # Redirect back to the login page

            login(request, user)
            dashboard_url = reverse('home')
            return redirect(dashboard_url)
        else:
            if '__all__' in form.errors:
                print("error in login", form.errors)
                messages.error(request, "Incorrect username or password. Please try again.")
            else:
                # Show individual field errors (e.g., username or password missing)
                for field in form.errors:
                    for error in form.errors[field]:
                        messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = AuthenticationForm()

    return render(request, 'core/login.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    return redirect('home')


def signup_view(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        role = request.POST.get('role', 'member')  # Default to member if not specified
        is_staff = True if role == "librarian" else False

        # Server-side validation
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username is already taken')
            return render(request, 'core/signup.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email is already registered')
            return render(request, 'core/signup.html')

        if password1 != password2:
            messages.error(request, 'Passwords do not match')
            return render(request, 'core/signup.html')

        # Create user
        try:
            # Use create_user method for your custom User model
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                is_staff=is_staff,
            )
            print("user", user)
            # Log the user in
            login(request, user)

            # Redirect based on user role
            if role == 'librarian':
                return redirect(reverse('librarian_dashboard'))
            else:
                return redirect(reverse('member_dashboard'))

        except Exception as e:
            messages.error(request, f'Error creating account: {str(e)}')
            return render(request, 'core/signup.html')
    else:
        return render(request, 'core/signup.html')


# Member views
@login_required
@member_required
def member_dashboard_view(request):
    return render(request, 'core/member_dashboard.html')


# Staff views
@login_required
@staff_required
def librarian_dashboard_view(request):
    # Get all non-staff users (assuming they are members)
    members = User.objects.filter(is_staff=False)

    # Prepare list to hold member info with borrow counts
    member_data = []

    for member in members:
        borrowed_books = BorrowRecord.objects.filter(user=member, returned=False)
        overdue_books = borrowed_books.filter(due_date__lt=timezone.now())

        member_data.append({
            'id': member.id,
            'username': member.username,
            'first_name': member.first_name,
            'last_name': member.last_name,
            'email': member.email,
            'date_joined': member.date_joined,
            'borrowed_count': borrowed_books.count(),
            'overdue_count': overdue_books.count(),
            'is_active': member.is_active,
        })

    # Paginate the member data
    paginator = Paginator(member_data, 10)  # 10 members per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'core/librarian_dashboard.html', {'members': page_obj})


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
@member_required_api
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
@member_required_api
def total_borrowed_books(request):
    count = BorrowRecord.objects.filter(user=request.user, is_reserved=False).count()
    return JsonResponse({"total_borrowed_books": count})


@login_required
@member_required_api
def books_due_soon(request):
    today = timezone.now().date()
    upcoming_due_date = today + timedelta(days=4)
    due_soon_books = BorrowRecord.objects.filter(
        user=request.user,
        due_date__lte=upcoming_due_date,
        return_date__isnull=True,
        is_reserved=False,
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


@login_required
@member_required_api
def overdue_books(request):
    today = timezone.now().date()
    overdue_records = BorrowRecord.objects.filter(
        user=request.user,
        due_date__lt=today,
        is_reserved=False,
        returned=False,
    ).select_related("book", "user")

    books = [
        {
            "title": record.book.title,
            "due_date": record.due_date.strftime("%Y-%m-%d"),
            "borrower": record.user.username,
        }
        for record in overdue_records
    ]

    return JsonResponse({"overdue_books": books})


@login_required
@member_required_api
def total_payments_made(request):
    total = Payment.objects.filter(user=request.user).aggregate(
        total_amount=Sum('amount')
    )['total_amount'] or 0.0

    return JsonResponse({"total_payments": float(total)})


class BorrowedBooksListView(MemberRequiredMixin, BaseDatatableView):
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
            for record in qs if record.is_reserved is False
        ]


class BorrowedBooksPageView(MemberRequiredMixin, TemplateView):
    template_name = 'core/borrowed_books_list.html'


class ReturnedBooksListView(MemberRequiredMixin, BaseDatatableView):
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


class ReturnedBooksPageView(MemberRequiredMixin, TemplateView):
    template_name = 'core/return_renew_books_list.html'


class FinancialOverviewPageView(MemberRequiredMixin, TemplateView):
    template_name = 'core/financial_overview.html'


class EditProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'core/edit_profile.html'


@require_POST
@login_required
def edit_profile_view(request):
    data = json.loads(request.body)
    user = request.user

    # Update basic fields
    user.first_name = data.get('first_name', user.first_name)
    user.last_name = data.get('last_name', user.last_name)
    user.username = data.get('username', user.username)
    user.email = data.get('email', user.email)

    # Password update logic
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')

    if new_password and confirm_password:
        if not user.check_password(current_password):
            return JsonResponse({'success': False, 'message': 'Current password is incorrect.'}, status=400)
        if new_password != confirm_password:
            return JsonResponse({'success': False, 'message': 'New passwords do not match.'}, status=400)
        user.set_password(new_password)

    user.save()
    return JsonResponse({'success': True, 'message': 'Your profile has been updated!'})


@login_required
@member_required_api
def return_book_view(request, record_id):
    """
    Handle book return process
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)
    borrow_record = get_object_or_404(BorrowRecord, pk=record_id)
    if borrow_record.user != request.user:
        return JsonResponse({"error": "You can only return your own books"}, status=403)
    if borrow_record.returned:
        return JsonResponse({"message": "This book has already been returned"}, status=200)
    borrow_record.returned = True
    borrow_record.return_date = timezone.now().date()
    borrow_record.save()
    book = borrow_record.book
    book.available_copies += 1
    book.save()
    # Check if the book is overdue and create a fine if needed
    if borrow_record.due_date < timezone.now().date():
        days_overdue = (timezone.now().date() - borrow_record.due_date).days
        fine_amount = days_overdue * 1.00  # £1 per day

        fine, created = Fine.objects.update_or_create(
            borrow_record=borrow_record,
            user=request.user,
            is_paid=False,  # only update unpaid fines
            defaults={
                "amount": fine_amount,
                "remarks": f"Late return by {days_overdue} days",
            }
        )

    return JsonResponse({
        "success": True,
        "message": "Book returned successfully"
    })


@login_required
@member_required_api
def books_due_today(request):
    today = date.today()

    # First try to get books due exactly today
    books_due_today = BorrowRecord.objects.filter(
        user=request.user,
        due_date=today,
        returned=False
    ).select_related('book')

    # If no books are due today, get books due in the next 3 days
    if not books_due_today.exists():
        next_three_days = today + timedelta(days=3)
        books_due_today = BorrowRecord.objects.filter(
            user=request.user,
            due_date__gte=today,
            due_date__lte=next_three_days,
            returned=False
        ).select_related('book').order_by('due_date')

    # If still no books, get the most recently borrowed books that are not returned
    if not books_due_today.exists():
        books_due_today = BorrowRecord.objects.filter(
            user=request.user,
            returned=False
        ).select_related('book').order_by('-borrow_date')

    # Limit to 6 records maximum
    books_due_today = books_due_today[:6]

    data = {
        "books_due_today": [
            {
                "id": book.id,
                "title": book.book.title,
                "author": book.book.author,
                "due_date": book.due_date.strftime("%Y-%m-%d"),
                "days_left": (book.due_date - today).days,
                "is_overdue": book.due_date < today
            } for book in books_due_today
        ]
    }
    return JsonResponse(data)


@login_required
@member_required_api
def pay_fine_view(request, record_id):
    """
    Handle fine payment process
    """
    try:
        if request.method != "POST":
            return JsonResponse({"error": "Invalid request method"}, status=405)
        borrow_record = get_object_or_404(BorrowRecord, pk=record_id)
        if borrow_record.user != request.user:
            return JsonResponse({"error": "You can only pay fines for your own books"}, status=403)
        days_overdue = (timezone.now().date() - borrow_record.due_date).days
        fine_amount = days_overdue * 1.00  # £1 per day
        fine, _ = Fine.objects.update_or_create(
            borrow_record=borrow_record,
            user=request.user,
            is_paid=False,  # only update unpaid fines
            defaults={
                "amount": fine_amount,
                "remarks": f"Late return by {days_overdue} days",
            }
        )

        method = request.POST.get('method', '')
        valid_methods = ['card', 'paypal', 'apple_pay', 'google_pay', 'direct_debit']
        if method not in valid_methods:
            return JsonResponse({"error": "Invalid payment method"}, status=400)
        payment = Payment.objects.create(
            fine=fine,
            user=request.user,
            amount=fine_amount,
            method=method
        )

        borrow_record.returned = True
        borrow_record.return_date = timezone.now().date()
        borrow_record.save()
        book = borrow_record.book
        book.available_copies += 1
        book.save()
        fine.is_paid = True
        fine.paid_date = timezone.now().date()
        fine.save()

        return JsonResponse({
            "success": True,
            "message": "Payment processed successfully",
            "payment_id": payment.id,
            "amount": fine_amount,
            "method": method
        })
    except Exception as e:
        print(e)
        return JsonResponse({"error": "Something went wrong", "details": str(e)}, status=500)


@login_required
@member_required_api
def renew_book_view(request, record_id):
    try:
        record = get_object_or_404(BorrowRecord, id=record_id, user=request.user)

        if not record.returned:
            return JsonResponse({"error": "Cannot renew a already borrowed book."}, status=400)
        record.returned = False
        record.due_date += timedelta(days=7)
        record.return_date = None
        record.renew_count += 1
        record.save()

        return JsonResponse({
            "message": f'Book "{record.book.title}" renewed for 7 more days.',
            "new_due_date": record.due_date.strftime("%Y-%m-%d")
        })
    except Exception as e:
        print(e)
        return JsonResponse({"error": "Something went wrong", "details": str(e)}, status=500)


@login_required
@member_required_api
def get_financial_summary(request):
    """
    Get summary of financial information for the user
    """
    try:
        # Total paid
        total_paid = Payment.objects.filter(user=request.user).aggregate(
            total=Sum('amount')
        )['total'] or 0.0

        # Total unpaid fines (calculated from overdue books)
        today = timezone.now().date()
        overdue_records = BorrowRecord.objects.filter(
            user=request.user,
            due_date__lt=today,
            returned=False
        )

        total_unpaid = 0
        for record in overdue_records:
            days_overdue = (today - record.due_date).days
            fine_amount = days_overdue * 1.00  # £1 per day
            total_unpaid += fine_amount

        # Recent payments (last 3)
        recent_payments = Payment.objects.filter(user=request.user).order_by('-payment_date')[:3]
        recent_payments_data = [
            {
                "amount": float(payment.amount),
                "method": payment.method,
                "payment_date": payment.payment_date.strftime("%Y-%m-%d") if payment.payment_date else "N/A",
                "fine_details": payment.fine.remarks if payment.fine else "N/A",
            }
            for payment in recent_payments
        ]

        # Top 3 largest unpaid fines from overdue books
        largest_fines = []
        for record in overdue_records:
            days_overdue = (today - record.due_date).days
            fine_amount = days_overdue * 1.00  # £1 per day
            largest_fines.append({
                "book_title": record.book.title,
                "due_date": record.due_date.strftime("%Y-%m-%d"),
                "days_overdue": days_overdue,
                "amount": fine_amount
            })

        # Sort by amount (largest first) and take top 3
        largest_fines.sort(key=lambda x: x["amount"], reverse=True)
        largest_fines = largest_fines[:3]

        return JsonResponse({
            "total_paid": float(total_paid),
            "total_unpaid": float(total_unpaid),
            "recent_payments": recent_payments_data,
            "largest_fines": largest_fines
        })
    except Exception as e:
        print(e)
        return JsonResponse({"error": "Something went wrong", "details": str(e)}, status=500)


@login_required
@staff_required
def all_payments_view(request):
    payments = Payment.objects.select_related('user', 'fine').all()

    # 1. Total of all payments
    total_payments = payments.aggregate(total=Sum('amount'))['total'] or 0

    # 2. Outstanding fines: fine.amount > payment.amount
    outstanding_fines = payments.filter(
        fine__amount__gt=F('amount')
    ).aggregate(total=Sum(F('fine__amount') - F('amount')))['total'] or 0

    # 3. Monthly payments (current month)
    now = timezone.now()
    monthly_payments = payments.filter(
        payment_date__year=now.year,
        payment_date__month=now.month
    ).aggregate(total=Sum('amount'))['total'] or 0

    return render(request, 'core/all_payments.html', {
        'payments': payments,
        'outstanding_fines': outstanding_fines,
        'total_payments': total_payments,
        'monthly_payments': monthly_payments
    })


@login_required
@staff_required_api
def suspend_member_user(request, member_id):
    if request.method == "POST":
        user = get_object_or_404(User, id=member_id)
        user.is_active = not user.is_active
        user.save()
        return JsonResponse({"status": "success", "is_active": user.is_active})
    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)


@login_required
@staff_required_api
@require_http_methods(["POST"])
def add_book(request):
    """API endpoint to add a new book"""
    try:
        print("qdkjeqwekjqw")
        data = json.loads(request.body)
        print("data ", data)
        # Validate required fields
        required_fields = ['title', 'author', 'isbn', 'edition', 'publisher',
                           'year_published', 'language', 'total_copies', 'available_copies']

        for field in required_fields:
            if field not in data or not data[field]:
                return JsonResponse({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }, status=400)

        # Get genre if provided
        genre = None
        if 'genre' in data and data['genre']:
            genre = get_object_or_404(Genre, id=data['genre'])

        # Create the book
        book = Book.objects.create(
            title=data['title'],
            author=data['author'],
            isbn=data['isbn'],
            edition=data['edition'],
            publisher=data['publisher'],
            year_published=int(data['year_published']),
            language=data['language'],
            total_copies=int(data['total_copies']),
            available_copies=int(data['available_copies']),
            genre=genre,
        )

        return JsonResponse({
            'success': True,
            'message': 'Book added successfully',
            'book_id': book.id
        })

    except Exception as e:
        print(e)
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@ staff_required_api
@require_http_methods(["DELETE"])
def delete_book(request, book_id):
    """API endpoint to delete a book"""
    book = get_object_or_404(Book, id=book_id)

    try:
        # Check if book can be deleted (no active borrows)
        active_borrows = BorrowRecord.objects.filter(book=book, returned=False).count()
        if active_borrows > 0:
            return JsonResponse({
                'success': False,
                'error': 'Cannot delete book with active borrows'
            }, status=400)

        book.delete()
        return JsonResponse({'success': True, 'message': 'Book deleted successfully'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@staff_required_api
@require_http_methods(["PUT"])
def update_book(request, book_id):
    """API endpoint to update a book"""
    book = get_object_or_404(Book, id=book_id)

    try:
        data = json.loads(request.body)

        # Update book fields
        book.title = data.get('title', book.title)
        book.author = data.get('author', book.author)
        book.isbn = data.get('isbn', book.isbn)
        book.edition = data.get('edition', book.edition)
        book.publisher = data.get('publisher', book.publisher)
        book.year_published = data.get('year_published', book.year_published)
        book.language = data.get('language', book.language)
        book.total_copies = data.get('total_copies', book.total_copies)
        book.available_copies = data.get('available_copies', book.available_copies)

        # Update genre if provided
        genre_id = data.get('genre')
        if genre_id:
            book.genre = get_object_or_404(Genre, id=genre_id)

        book.save()

        return JsonResponse({'success': True, 'message': 'Book updated successfully'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def view_book(request, book_id):
    """API endpoint to get book details"""
    book = get_object_or_404(Book, id=book_id)

    data = {
        'id': book.id,
        'title': book.title,
        'author': book.author,
        'isbn': book.isbn,
        'edition': book.edition,
        'publisher': book.publisher,
        'year_published': book.year_published,
        'language': book.language,
        'total_copies': book.total_copies,
        'available_copies': book.available_copies,
        'genre': book.genre.id if book.genre else None,
        'genre_name': book.genre.name if book.genre else 'Unknown',
        'library': book.library.id if book.library else None,
        'library_name': book.library.name if book.library else 'Unknown',
    }

    return JsonResponse(data)


@login_required
@staff_required_api
@require_http_methods(["POST"])
def suspend_member(request, member_id):
    """API endpoint to suspend a member"""
    member = get_object_or_404(User, id=member_id)

    try:
        member.is_active = False
        member.save()
        return JsonResponse({'success': True, 'message': 'Member suspended successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@staff_required_api
@require_http_methods(["POST"])
def activate_member(request, member_id):
    """API endpoint to activate a member"""
    member = get_object_or_404(User, id=member_id)

    try:
        member.is_active = True
        member.save()
        return JsonResponse({'success': True, 'message': 'Member activated successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@staff_required
def edit_book(request, book_id):
    """View for editing a book"""
    return render(request, 'book_list.html')


@api_view(['GET'])
def genre_list(request):
    genres = Genre.objects.all()
    serializer = GenreSerializer(genres, many=True)
    return Response(serializer.data)


@login_required
@staff_required
def library_analytics(request):
    """View for library analytics dashboard"""
    # Basic metrics
    total_books = Book.objects.count()
    books_borrowed = BorrowRecord.objects.filter(return_date__isnull=True).count()
    books_reserved = BorrowRecord.objects.filter(is_reserved=True).count()
    overdue_books = BorrowRecord.objects.filter(
        return_date__isnull=True,
        due_date__lt=datetime.now().date()
    ).count()

    # Monthly borrow trends (last 6 months)
    today = datetime.now().date()
    six_months_ago = today - timedelta(days=180)

    monthly_data = []
    monthly_labels = []

    for i in range(6):
        month_start = today.replace(day=1) - timedelta(days=30 * i)
        month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

        month_borrows = BorrowRecord.objects.filter(
            borrow_date__gte=month_start,
            borrow_date__lte=month_end
        ).count()

        monthly_data.insert(0, month_borrows)
        monthly_labels.insert(0, month_start.strftime('%b %Y'))

    # Top categories
    categories = Book.objects.values('genre__name').annotate(
        count=Count('id')
    ).order_by('-count')[:5]

    category_labels = [cat['genre__name'] or 'Uncategorized' for cat in categories]
    category_data = [cat['count'] for cat in categories]

    # Most borrowed books
    most_borrowed_books = Book.objects.annotate(
        borrow_count=Count('borrowrecord')
    ).order_by('-borrow_count')[:10]

    most_borrowed_books_data = [
        {
            'title': book.title,
            'author': book.author,
            'borrow_count': book.borrow_count,
            'genre': book.genre.name if book.genre else 'Unknown'
        }
        for book in most_borrowed_books
    ]

    # Active borrowers
    active_borrowers = User.objects.annotate(
        books_borrowed=Count('borrowrecord', filter=Q(borrowrecord__return_date__isnull=True))
    ).filter(books_borrowed__gt=0).order_by('-books_borrowed')[:5]

    active_borrowers_data = [
        {
            'name': f"{borrower.first_name} {borrower.last_name}",
            'books_borrowed': borrower.books_borrowed,
            'join_date': borrower.date_joined.strftime('%b %d, %Y') if hasattr(borrower, 'date_joined') else None
        }
        for borrower in active_borrowers
    ]

    # Financial data
    total_fines_collected = Payment.objects.aggregate(total=Sum('amount'))['total'] or 0
    outstanding_fines = Fine.objects.filter(
        payment__isnull=True
    ).aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'total_books': total_books,
        'books_borrowed': books_borrowed,
        'books_reserved': books_reserved,
        'overdue_books': overdue_books,
        'monthly_labels': json.dumps(monthly_labels),
        'monthly_data': json.dumps(monthly_data),
        'category_labels': json.dumps(category_labels),
        'category_data': json.dumps(category_data),
        'most_borrowed_books': most_borrowed_books_data,
        'active_borrowers': active_borrowers_data,
        'total_fines_collected': "{:.2f}".format(total_fines_collected),
        'outstanding_fines': "{:.2f}".format(outstanding_fines),
    }

    return render(request, 'core/library_analytics.html', context)


@login_required
@staff_required_api
def export_analytics_data(request, report_type):
    """API endpoint to export analytics data in various formats"""
    if report_type not in ['csv', 'pdf', 'excel']:
        return JsonResponse({'error': 'Invalid report type'}, status=400)

    # Implementation for different export types would go here
    # This is a placeholder that returns success
    return JsonResponse({
        'success': True,
        'message': f'Analytics data exported as {report_type.upper()} successfully'
    })


@login_required
@staff_required_api
def get_analytics_data(request):
    """API endpoint to get analytics data for AJAX requests"""
    data_type = request.GET.get('type', 'summary')

    if data_type == 'summary':
        # Basic metrics for AJAX refresh
        total_books = Book.objects.count()
        books_borrowed = BorrowRecord.objects.filter(return_date__isnull=True).count()
        books_reserved = BorrowRecord.objects.filter(is_reserved=True).count()
        overdue_books = BorrowRecord.objects.filter(
            return_date__isnull=True,
            due_date__lt=datetime.now().date()
        ).count()

        return JsonResponse({
            'total_books': total_books,
            'books_borrowed': books_borrowed,
            'books_reserved': books_reserved,
            'overdue_books': overdue_books,
        })

    elif data_type == 'borrowing_trends':
        # Monthly borrowing data for charts
        today = datetime.now().date()

        monthly_data = []
        monthly_labels = []

        for i in range(6):
            month_start = today.replace(day=1) - timedelta(days=30 * i)
            month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

            month_borrows = BorrowRecord.objects.filter(
                borrow_date__gte=month_start,
                borrow_date__lte=month_end
            ).count()

            monthly_data.insert(0, month_borrows)
            monthly_labels.insert(0, month_start.strftime('%b %Y'))

        return JsonResponse({
            'labels': monthly_labels,
            'data': monthly_data,
        })

    return JsonResponse({'error': 'Invalid data type'}, status=400)