from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


def send_verification_email(request, user):
    verify_url = request.build_absolute_uri(
        f'/auth/verify-email/{user.email_verification_token}/'
    )
    context = {
        'user': user,
        'verify_url': verify_url,
        'site_name': 'PrintHub',
    }
    message = render_to_string('accounts/emails/verification_email.txt', context)
    send_mail(
        subject='Verify your PrintHub account',
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
