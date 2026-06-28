import os
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from orders.models import Order
from stations.models import Station

User = get_user_model()


class OrderPriceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='priceuser',
            email='price@example.com',
            password='testpass123',
            role='client',
        )
        self.station = Station.objects.create(name='Test Station')

    def _make_order(self, **kwargs):
        defaults = {
            'client': self.user,
            'station': self.station,
            'file_name': 'test.pdf',
            'page_count': 4,
            'is_color': False,
            'is_double_sided': False,
        }
        defaults.update(kwargs)
        order = Order(**defaults)
        order.file = SimpleUploadedFile('test.pdf', b'pdf content')
        order.save()
        return order

    def test_bw_single_sided_price(self):
        order = self._make_order(page_count=4, is_color=False, is_double_sided=False)
        self.assertEqual(order.total_price, 800)

    def test_color_single_sided_price(self):
        order = self._make_order(page_count=4, is_color=True, is_double_sided=False)
        self.assertEqual(order.total_price, 1200)

    def test_bw_double_sided_price(self):
        order = self._make_order(page_count=5, is_color=False, is_double_sided=True)
        self.assertEqual(order.total_price, 600)

    def test_color_double_sided_price(self):
        order = self._make_order(page_count=5, is_color=True, is_double_sided=True)
        self.assertEqual(order.total_price, 900)


class UploadViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='uploaduser',
            email='upload@example.com',
            password='testpass123',
            role='client',
        )
        self.station = Station.objects.create(name='Upload Station')
        self.client.login(username='uploaduser', password='testpass123')

    def test_rejects_invalid_file_type(self):
        bad_file = SimpleUploadedFile('malware.exe', b'bad', content_type='application/octet-stream')
        response = self.client.post(reverse('upload'), {
            'file': bad_file,
            'page_count': 1,
            'is_color': 'False',
            'station': self.station.id,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid file type')
        self.assertEqual(Order.objects.count(), 0)

    def test_accepts_valid_pdf(self):
        pdf = SimpleUploadedFile('doc.pdf', b'%PDF-1.4', content_type='application/pdf')
        response = self.client.post(reverse('upload'), {
            'file': pdf,
            'page_count': 2,
            'is_color': 'False',
            'station': self.station.id,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 1)


class UpdateOrderStatusTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.client_user = User.objects.create_user(
            username='student1',
            email='student@example.com',
            password='testpass123',
            role='client',
        )
        self.admin_user = User.objects.create_user(
            username='admin1',
            email='admin@example.com',
            password='testpass123',
            role='admin',
        )
        self.station = Station.objects.create(name='Status Station')
        self.order = Order.objects.create(
            client=self.client_user,
            station=self.station,
            file=SimpleUploadedFile('f.pdf', b'pdf'),
            file_name='f.pdf',
            page_count=1,
            status='paid',
        )

    def test_student_cannot_update_status(self):
        self.client.login(username='student1', password='testpass123')
        response = self.client.post(
            reverse('update_order_status', args=[self.order.id]),
            {'status': 'collected'},
        )
        self.assertEqual(response.status_code, 403)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')

    def test_admin_can_update_status(self):
        self.client.login(username='admin1', password='testpass123')
        response = self.client.post(
            reverse('update_order_status', args=[self.order.id]),
            {'status': 'printing'},
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'printing')
