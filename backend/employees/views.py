# backend/employees/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.mail import send_mail
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.utils import timezone

from .models import Application
from .forms import ApplicationForm, ApplicationReviewForm


def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.role == 'admin')


def application_form_view(request):
    """Public application form."""
    if request.method == 'POST':
        form = ApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            application = form.save()
            
            # Send confirmation email
            try:
                send_mail(
                    subject='Application Received - PrintHub',
                    message=f"""
Dear {application.first_name},

Thank you for applying to PrintHub!

Your application for {application.get_applied_stage_display()} has been received.

We will review your application and contact you within 3-5 business days.

Best regards,
PrintHub Team
""",
                    from_email='noreply@printhubug.com',
                    recipient_list=[application.email],
                    fail_silently=True,
                )
            except Exception:
                pass
            
            messages.success(request, 'Application submitted successfully! We will contact you soon.')
            return redirect('application_success')
    else:
        form = ApplicationForm()
    
    return render(request, 'employees/application_form.html', {
        'form': form,
        'stages': Application.STAGE_CHOICES,
    })


def application_success_view(request):
    """Success page after application submission."""
    return render(request, 'employees/application_success.html')


@login_required
@user_passes_test(is_admin)
def application_list_view(request):
    """Admin view to list all applications."""
    status_filter = request.GET.get('status', '')
    stage_filter = request.GET.get('stage', '')
    search = request.GET.get('search', '')
    
    applications = Application.objects.all()
    
    if status_filter:
        applications = applications.filter(status=status_filter)
    if stage_filter:
        applications = applications.filter(applied_stage=stage_filter)
    if search:
        applications = applications.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search)
        )
    
    # Stats
    stats = {
        'total': Application.objects.count(),
        'pending': Application.objects.filter(status='pending').count(),
        'reviewing': Application.objects.filter(status='reviewing').count(),
        'shortlisted': Application.objects.filter(status='shortlisted').count(),
        'interview': Application.objects.filter(status='interview').count(),
        'accepted': Application.objects.filter(status='accepted').count(),
        'rejected': Application.objects.filter(status='rejected').count(),
    }
    
    paginator = Paginator(applications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'employees/application_list.html', {
        'page_obj': page_obj,
        'applications': page_obj.object_list,
        'stats': stats,
        'status_filter': status_filter,
        'stage_filter': stage_filter,
        'search': search,
        'status_choices': Application.STATUS_CHOICES,
        'stage_choices': Application.STAGE_CHOICES,
    })


@login_required
@user_passes_test(is_admin)
def application_detail_view(request, application_id):
    """Admin view to see application details."""
    application = get_object_or_404(Application, id=application_id)
    
    if request.method == 'POST':
        form = ApplicationReviewForm(request.POST, instance=application)
        if form.is_valid():
            form.save()
            application.reviewed_by = request.user
            application.reviewed_at = timezone.now()
            application.save()
            
            messages.success(request, f'Application #{application.id} updated!')
            return redirect('application_detail', application_id=application.id)
    else:
        form = ApplicationReviewForm(instance=application)
    
    return render(request, 'employees/application_detail.html', {
        'application': application,
        'form': form,
        'stage_questions': application.get_stage_questions(),
    })
