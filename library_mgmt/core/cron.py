from django_cron import CronJobBase, Schedule
from .models import BorrowRecord, Book
from django.utils.timezone import now


class ClearReservedBooksJob(CronJobBase):
    run_every_mins = 1
    RUN_AT_TIMES = ['01:00']  # 1:00 AM

    schedule = Schedule(run_at_times=RUN_AT_TIMES)
    code = 'library_mgmt.clear_reserved_books'

    def do(self):
        today = now().date()

        # Get the reserved borrow records that are overdue
        reserved_books = BorrowRecord.objects.filter(
            is_reserved=True,
            due_date__lt=today
        )

        # Iterate over each reserved record
        for record in reserved_books:
            # Update the available copies of the associated book
            book = record.book
            book.available_copies += 1
            book.save()

        # Delete the reserved borrow records
        reserved_books.delete()
