from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('phc', '0003_doctorprofile_email')]

    operations = [
        migrations.RemoveField(model_name='doctorprofile', name='active'),
    ]
