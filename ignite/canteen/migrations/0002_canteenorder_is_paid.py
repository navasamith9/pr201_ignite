from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('canteen', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='canteenorder',
            name='is_paid',
            field=models.BooleanField(default=False),
        ),
    ]
