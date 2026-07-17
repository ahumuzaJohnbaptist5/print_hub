from django.contrib.auth import get_user_model
from django.conf import settings
from django.core import mail
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

User = get_user_model()


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RegistrationTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_registration_creates_client_role(self):
        response = self.client.post(reverse('register'), {
            'username': 'newstudent',
            'email': 'new@example.com',
            'password': 'securepass123',
            'role': 'admin',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('verification_sent'))
        user = User.objects.get(username='newstudent')
        self.assertEqual(user.role, 'client')
        self.assertFalse(user.email_verified)

    def test_registration_sends_verification_email(self):
        self.client.post(reverse('register'), {
            'username': 'emailuser',
            'email': 'verify@example.com',
            'password': 'securepass123',
        })
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Verify your PrintHub account', mail.outbox[0].subject)
        self.assertIn('verify@example.com', mail.outbox[0].to)

    def test_registration_page_has_no_role_field(self):
        response = self.client.get(reverse('register'))
        self.assertNotContains(response, 'name="role"')


class LoginTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.verified = User.objects.create_user(
            username='loginuser',
            email='login@example.com',
            password='testpass123',
            role='client',
            email_verified=True,
        )
        self.unverified = User.objects.create_user(
            username='unverified',
            email='unverified@example.com',
            password='testpass123',
            role='client',
            email_verified=False,
        )

    def test_verified_login_redirects_to_dashboard(self):
        response = self.client.post(reverse('login'), {
            'username': 'loginuser',
            'password': 'testpass123',
        })
        self.assertRedirects(response, reverse('dashboard'))

    def test_unverified_user_cannot_login(self):
        response = self.client.post(reverse('login'), {
            'username': 'unverified',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please verify your email first')

    def test_login_url_is_auth_login(self):
        response = self.client.get('/dashboard/')
        self.assertRedirects(response, '/auth/login/?next=/dashboard/')


class EmailVerificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='verifyme',
            email='verifyme@example.com',
            password='testpass123',
            email_verified=False,
        )

    def test_verify_email_activates_account(self):
        response = self.client.get(
            reverse('verify_email', args=[self.user.email_verification_token])
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)


class DatabaseSettingsTests(SimpleTestCase):
    def test_sqlite_database_has_no_sslmode_option(self):
        default_db = settings.DATABASES['default']
        if default_db.get('ENGINE') != 'django.db.backends.sqlite3':
            self.skipTest('This assertion only applies to sqlite settings')
        self.assertNotIn('sslmode', default_db.get('OPTIONS', {}))
