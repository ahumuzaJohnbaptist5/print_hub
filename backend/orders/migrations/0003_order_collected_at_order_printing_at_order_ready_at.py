# Generated for PrintHub

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_order_paid_at_order_transaction_id_order_tx_ref'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='collected_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='printing_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='ready_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
