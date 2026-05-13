from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_admin', '0003_uploadedleadrow'),
    ]

    operations = [
        migrations.AlterField(
            model_name='uploadjob',
            name='result_file_path',
            field=models.TextField(
                blank=True,
                null=True,
                default='',
                help_text='Deprecated local output CSV path (kept temporarily for safe rollout).',
            ),
        ),
    ]
