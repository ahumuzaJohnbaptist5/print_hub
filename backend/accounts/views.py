from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model, authenticate, login, logout
from django.contrib import messages

from .utils import send_verification_email

User = get_user_model()


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')

        if not username or not email or not password:
            return render(request, 'accounts/register.html', {'error': 'All fields are required'})

        if User.objects.filter(username=username).exists():
            return render(request, 'accounts/register.html', {'error': 'Username already exists'})

        if User.objects.filter(email=email).exists():
            return render(request, 'accounts/register.html', {'error': 'Email already exists'})

        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role='client',
                email_verified=False,
            )
            send_verification_email(request, user)
            return redirect('verification_sent')
        except Exception as e:
            return render(request, 'accounts/register.html', {'error': f'Registration failed: {str(e)}'})

    return render(request, 'accounts/register.html')


def verification_sent_view(request):
    return render(request, 'accounts/verification_sent.html')


def verify_email_view(request, token):
    user = get_object_or_404(User, email_verification_token=token)
    if not user.email_verified:
        user.email_verified = True
        user.save(update_fields=['email_verified'])
    messages.success(request, 'Email verified! You can now log in.')
    return render(request, 'accounts/verify_email.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(username=username, password=password)

        if user is None:
            return render(request, 'accounts/login.html', {'error': 'Invalid credentials'})

        if not user.email_verified:
            return render(request, 'accounts/login.html', {
                'error': 'Please verify your email first. Check your inbox for the verification link.',
            })

        login(request, user)
        messages.success(request, f'Welcome back, {username}!')
        return redirect('dashboard')

    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('home')
