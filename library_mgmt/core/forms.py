from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError


class LoginForm(AuthenticationForm):
    email = forms.EmailField(max_length=150, required=True,
                             widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}))
    password = forms.CharField(max_length=128, required=True,
                               widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove the default username field
        del self.fields['username']

    def clean(self):
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')

        # Check if both email and password are provided
        if email and password:
            # Get the user based on the email
            user = get_user_model().objects.filter(email=email).first()

            # If user exists and password matches
            if user and user.check_password(password):
                self.user_cache = user
            else:
                raise ValidationError('Invalid email or password')

        return self.cleaned_data

    def get_user(self):
        return self.user_cache
