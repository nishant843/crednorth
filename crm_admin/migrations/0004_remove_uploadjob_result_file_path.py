from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('crm_admin', '0003_uploadedleadrow'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='uploadjob',
            name='result_file_path',
        ),
    ]
