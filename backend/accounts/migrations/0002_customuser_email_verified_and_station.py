# Generated for PrintHub

import uuid
import django.db.models.deletion
from django.db import migrations, models


def verify_existing_users(apps, schema_editor):
    User = apps.get_model('accounts', 'CustomUser')
    User.objects.all().update(email_verified=True)


class Migration(migrations.Migration):

    dependencies = [
        ('stations', '0002_seed_stations'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='email_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='customuser',
            name='email_verification_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False),
        ),
        migrations.AddField(
            model_name='customuser',
            name='station',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='agents',
                to='stations.station',
            ),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='email_verification_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.RunPython(verify_existing_users, migrations.RunPython.noop),
    ]
