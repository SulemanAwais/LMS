import json

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView
from django_datatables_view.base_datatable_view import BaseDatatableView
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, get_user, logout
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q, Sum
from django.urls import reverse
from rest_framework.generics import get_object_or_404
from django.utils import timezone
from datetime import timedelta, date
from .forms import LoginForm
from .models import Book, BorrowRecord, Fine, Payment
from django.contrib.auth import get_user_model


def home(request):
    if request.user.is_authenticated:
        print("staff", request.user.is_staff)
        if request.user.is_staff:
            return redirect('librarian_dashboard')
        else:
            return redirect(reverse('member_dashboard'))
    return render(request, 'core/home.html')


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            dashboard_url = reverse('home')
            return redirect(dashboard_url)
        else:
            if '__all__' in form.errors:
                messages.error(request, "Incorrect email or password. Please try again.")
            else:
                # Show individual field errors (e.g., username or password missing)
                for field in form.errors:
                    for error in form.errors[field]:
                        messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = LoginForm()
    return render(request, 'core/login.html', {'form': form})


@login_required()
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
        User = get_user_model()

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


@login_required
def member_dashboard_view(request):
    return render(request, 'core/member_dashboard.html')


@login_required
def librarian_dashboard_view(request):
    # Get all non-staff users (assuming they are members)
    User = get_user_model()
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
            'email': member.email,
            'joined_date': member.date_joined,
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
    count = BorrowRecord.objects.filter(user=request.user, is_reserved=False).count()
    return JsonResponse({"total_borrowed_books": count})


@login_required
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
def total_payments_made(request):
    total = Payment.objects.filter(user=request.user).aggregate(
        total_amount=Sum('amount')
    )['total_amount'] or 0.0

    return JsonResponse({"total_payments": float(total)})


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
            for record in qs if record.is_reserved is False
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


class FinancialOverviewPageView(LoginRequiredMixin, TemplateView):
    template_name = 'core/financial_overview.html'


class EditProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'core/edit_profile.html'


@require_POST
@login_required()
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
def renew_book_view(request, record_id):
    try:
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
    except Exception as e:
        print(e)
        return JsonResponse({"error": "Something went wrong", "details": str(e)}, status=500)


@login_required
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
@staff_member_required
def all_payments_view(request):
    payments = Payment.objects.select_related('user').all()

    # Total paid amount
    total_payments = payments.filter().aggregate(total=Sum('amount'))['total'] or 0

    # Total outstanding fines (unpaid)
    outstanding_fines = payments.filter(status='unpaid').aggregate(total=Sum('amount'))['total'] or 0

    # Payments made in current month
    now = timezone.now()
    monthly_payments = payments.filter(
        status='paid',
        date__year=now.year,
        date__month=now.month
    ).aggregate(total=Sum('amount'))['total'] or 0

    return render(request, 'core/all_payments.html', {
        'payments': payments,
        'outstanding_fines': outstanding_fines,
        'total_payments': total_payments,
        'monthly_payments': monthly_payments
    })