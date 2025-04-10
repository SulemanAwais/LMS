from django.urls import path
from .views import home
urlpatterns = [
    path('', home, name='home'),  # Root URL for the home page
    # path('login/', views.login_view, name='login'),  # Login URL
    # path('signup/', views.signup_view, name='signup'),  # Sign Up URL
]
