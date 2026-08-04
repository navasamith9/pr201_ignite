# Generated manually because this workspace has no active Django environment.

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bus', '0002_ticketbooking_boarding_verification'),
    ]

    operations = [
        migrations.AlterField(
            model_name='busschedule',
            name='max_capacity',
            field=models.PositiveSmallIntegerField(default=40, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(40)]),
        ),
        migrations.AlterField(
            model_name='ticketbooking',
            name='quantity',
            field=models.PositiveSmallIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(2)]),
        ),
    ]
