# orders/migrations/0005_add_file_metadata.py
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0004_systemsettings_alter_order_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='file_metadata',
            field=models.JSONField(blank=True, default=dict, help_text='File metadata from processing'),
        ),
        migrations.AddField(
            model_name='order',
            name='file_preview',
            field=models.TextField(blank=True, default='', help_text='Text preview of file content'),
        ),
        migrations.AddField(
            model_name='order',
            name='file_thumbnail',
            field=models.TextField(blank=True, default='', help_text='Base64 thumbnail for images'),
        ),
    ]
