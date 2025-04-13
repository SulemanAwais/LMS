# core/management/commands/daily_tasks.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import BorrowRecord, Fine
from datetime import date

class Command(BaseCommand):
    help = "Runs daily tasks: clears expired reservations and creates fines."

    def handle(self, *args, **kwargs):
        today = date.today()

        # Free expired reservations
        expired_reservations = BorrowRecord.objects.filter(
            is_reserved=True,
            due_date__lt=today,
            returned=False
        )

        for record in expired_reservations:
            record.returned = True
            record.return_date = today
            record.save()
            record.book.available_copies += 1
            record.book.save()
            self.stdout.write(self.style.SUCCESS(f"Reservation expired and freed: {record.book.title}"))

        # Fines for overdue borrowings
        overdue_borrowed = BorrowRecord.objects.filter(
            is_reserved=False,
            returned=False,
            due_date__lt=today
        )

        for borrow in overdue_borrowed:
            # Check if fine already exists for this borrow
            if not borrow.fines.exists():
                days_overdue = (today - borrow.due_date).days
                fine_amount = days_overdue * 10  # assuming Rs. 10 per day

                Fine.objects.create(
                    borrow_record=borrow,
                    amount=fine_amount,
                    remarks=f"Auto fine for being {days_overdue} days late."
                )
                self.stdout.write(self.style.WARNING(f"Fine created for {borrow.user.username}: Rs. {fine_amount}"))
