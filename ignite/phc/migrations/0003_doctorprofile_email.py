from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('phc', '0002_doctorprofile_name_optional_user')]

    operations = [
        migrations.AddField(
            model_name='doctorprofile',
            name='email',
            field=models.EmailField(blank=True, max_length=254, null=True, unique=True),
        ),
    ]
