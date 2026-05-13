from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('crm_admin', '0004_remove_uploadjob_result_file_path'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='uploadjob',
            name='result_file_path',
        ),
    ]
