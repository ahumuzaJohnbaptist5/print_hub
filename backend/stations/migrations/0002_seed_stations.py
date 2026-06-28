from django.db import migrations


def seed_stations(apps, schema_editor):
    Station = apps.get_model('stations', 'Station')
    stations = [
        ('Main Campus', 'Main campus print station'),
        ('Engineering Faculty', 'Engineering faculty pickup point'),
        ('In Town', 'In town pickup location'),
    ]
    for name, description in stations:
        Station.objects.get_or_create(
            name=name,
            defaults={'location_description': description},
        )


def unseed_stations(apps, schema_editor):
    Station = apps.get_model('stations', 'Station')
    Station.objects.filter(
        name__in=['Main Campus', 'Engineering Faculty', 'In Town'],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('stations', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_stations, unseed_stations),
    ]
