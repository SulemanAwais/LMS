from django.shortcuts import redirect
from django.urls import reverse


class RoleBasedAccessMiddleware:
    """
    Middleware to handle role-based access control.
    This is a more sophisticated approach than using decorators for every view.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Define URL patterns that require staff access
        self.staff_only_urls = [
            '/librarian-dashboard/',
            '/add-book/',
            '/edit-book/',
            '/all-members/',
            '/register-member/',
            '/process-returns/',
            '/all-payments/',
            '/generate-reports/',
        ]

    def __call__(self, request):
        # Check if the current URL requires staff access
        path = request.path

        # If the URL requires staff access and the user is not staff, redirect to access denied
        if any(path.startswith(url) for url in self.staff_only_urls):
            if not request.user.is_authenticated or not request.user.is_staff:
                return redirect(reverse('access_denied') + '?staff_only=True')

        response = self.get_response(request)
        return response
