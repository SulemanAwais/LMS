from django.db import models
from django.contrib.auth.models import AbstractUser


# User with roles
from django.db import models
from django.contrib.auth.models import AbstractUser


# User with roles and verification for Librarians
class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('librarian', 'Librarian'),
        ('member', 'Member'),
    )
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='core_user_set',
        blank=True,
        help_text='The groups this user belongs to.'
    )

    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='core_user_permissions_set',
        blank=True,
        help_text='Specific permissions for this user.'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    joined_date = models.DateField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.username} ({self.role})"


# Genre model
class Genre(models.Model):
    FICTION = 'fiction'
    NONFICTION = 'nonfiction'
    MYSTERY = 'mystery'
    SCIFI = 'sci-fi'
    FANTASY = 'fantasy'
    BIOGRAPHY = 'biography'
    HISTORY = 'history'
    CHILDREN = 'children'
    ROMANCE = 'romance'
    SELFHELP = 'selfhelp'

    GENRE_CHOICES = [
        (FICTION, 'Fiction'),
        (NONFICTION, 'Non-Fiction'),
        (MYSTERY, 'Mystery'),
        (SCIFI, 'Science Fiction'),
        (FANTASY, 'Fantasy'),
        (BIOGRAPHY, 'Biography'),
        (HISTORY, 'History'),
        (CHILDREN, 'Children'),
        (ROMANCE, 'Romance'),
        (SELFHELP, 'Self-Help'),
    ]

    name = models.CharField(
        max_length=20,
        choices=GENRE_CHOICES,
        unique=True
    )

    def __str__(self):
        return dict(self.GENRE_CHOICES).get(self.name, self.name)


# Book model
class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=100)
    isbn = models.CharField(max_length=20, unique=True)
    edition = models.CharField(max_length=20)
    publisher = models.CharField(max_length=100)
    year_published = models.IntegerField()
    language = models.CharField(max_length=50)
    total_copies = models.PositiveIntegerField()
    available_copies = models.PositiveIntegerField()
    genre = models.ForeignKey(Genre, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.title} by {self.author}"


# BorrowRecord
class BorrowRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    borrow_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    return_date = models.DateField(null=True, blank=True)
    returned = models.BooleanField(default=False)
    renew_count = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} borrowed {self.book.title}"


# Fine
class Fine(models.Model):
    borrow_record = models.OneToOneField(BorrowRecord, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    paid = models.BooleanField(default=False)
    fine_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"Fine for {self.borrow_record}"


# Payment
class Payment(models.Model):
    fine = models.ForeignKey(Fine, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    method = models.CharField(max_length=50)
    payment_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"Payment of {self.amount} by {self.user.username}"
