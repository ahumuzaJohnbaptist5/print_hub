# backend/employees/migrations/0001_initial.py
from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        # ✅ ADD THIS - Depends on Django's auth migrations
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Application',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(max_length=100)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('phone', models.CharField(max_length=15)),
                ('location', models.CharField(help_text='Current location/city', max_length=200)),
                ('applied_stage', models.CharField(choices=[
                    ('order_verifier', 'Order Verifier'),
                    ('document_processor', 'Document Processor'),
                    ('print_operator', 'Print Operator'),
                    ('qc_inspector', 'Quality Control Inspector'),
                    ('pickup_coordinator', 'Pickup/Delivery Coordinator'),
                    ('customer_support', 'Customer Support'),
                ], max_length=50)),
                ('experience_years', models.IntegerField(default=0)),
                ('availability', models.CharField(help_text='When can you start?', max_length=200)),
                ('why_work', models.TextField(help_text='Why do you want to work at PrintHub?', max_length=500)),
                ('experience', models.TextField(help_text='Describe your relevant experience', max_length=1000)),
                ('skills', models.TextField(help_text='List your skills', max_length=500)),
                ('attention_to_detail', models.IntegerField(
                    blank=True, null=True,
                    help_text='Rate your attention to detail (1-10)',
                    validators=[
                        django.core.validators.MinValueValidator(1),
                        django.core.validators.MaxValueValidator(10)
                    ]
                )),
                ('software_proficiency', models.CharField(blank=True, null=True, max_length=200, help_text="List software you're proficient with")),
                ('printer_experience', models.CharField(blank=True, null=True, max_length=500, help_text='Describe your printer experience')),
                ('quality_standards', models.CharField(blank=True, null=True, max_length=500, help_text='Do you know quality control standards?')),
                ('customer_service', models.CharField(blank=True, null=True, max_length=500, help_text='Describe your customer service experience')),
                ('resume', models.FileField(blank=True, null=True, upload_to='resumes/%Y/%m/%d/', help_text='Upload your CV/Resume (PDF, DOCX)')),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending Review'),
                        ('reviewing', 'Under Review'),
                        ('shortlisted', 'Shortlisted'),
                        ('interview', 'Interview Scheduled'),
                        ('accepted', 'Accepted'),
                        ('rejected', 'Rejected'),
                    ],
                    default='pending',
                    max_length=50
                )),
                ('reviewer_notes', models.TextField(blank=True, help_text='Internal notes for reviewers')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=models.SET_NULL,
                    to='auth.user',
                    related_name='reviewed_applications'
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
