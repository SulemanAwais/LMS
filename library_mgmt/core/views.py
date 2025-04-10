from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.shortcuts import render, redirect
from django.urls import reverse

from .forms import LoginForm


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
