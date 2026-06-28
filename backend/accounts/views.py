from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model, authenticate, login, logout
from django.contrib import messages

User = get_user_model()


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = 'client'

        if not username or not email or not password:
            return render(request, 'accounts/register.html', {'error': 'All fields are required'})

        if User.objects.filter(username=username).exists():
            return render(request, 'accounts/register.html', {'error': 'Username already exists'})

        if User.objects.filter(email=email).exists():
            return render(request, 'accounts/register.html', {'error': 'Email already exists'})

        try:
            User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role=role,
            )
            messages.success(request, 'Registration successful! Please login.')
            return redirect('login')
        except Exception as e:
            return render(request, 'accounts/register.html', {'error': f'Registration failed: {str(e)}'})

    return render(request, 'accounts/register.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(username=username, password=password)

        if user is None:
            return render(request, 'accounts/login.html', {'error': 'Invalid credentials'})

        login(request, user)
        messages.success(request, f'Welcome back, {username}!')
        return redirect('dashboard')

    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('home')
