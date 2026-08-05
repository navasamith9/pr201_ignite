from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('phc', '0004_remove_doctorprofile_active')]

    operations = [
        migrations.AlterField(
            model_name='consultationqueue',
            name='token_number',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
