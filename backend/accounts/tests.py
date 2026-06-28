from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


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
        user = User.objects.get(username='newstudent')
        self.assertEqual(user.role, 'client')

    def test_registration_page_has_no_role_field(self):
        response = self.client.get(reverse('register'))
        self.assertNotContains(response, 'name="role"')


class LoginTests(TestCase):
    def setUp(self):
        self.client = Client()
        User.objects.create_user(
            username='loginuser',
            email='login@example.com',
            password='testpass123',
            role='client',
        )

    def test_login_redirects_to_dashboard(self):
        response = self.client.post(reverse('login'), {
            'username': 'loginuser',
            'password': 'testpass123',
        })
        self.assertRedirects(response, reverse('dashboard'))

    def test_login_url_is_auth_login(self):
        response = self.client.get('/dashboard/')
        self.assertRedirects(response, '/auth/login/?next=/dashboard/')
