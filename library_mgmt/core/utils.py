from .models import BorrowRecord
from django.utils.timezone import now


def release_expired_reservations():
    today = now().date()
    BorrowRecord.objects.filter(
        is_reserved=True,
        due_date__lt=today
    ).update(is_reserved=False)
