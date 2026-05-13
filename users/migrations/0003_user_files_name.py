from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_rename_idx_user_created_at_idx_user_created_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='files_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
