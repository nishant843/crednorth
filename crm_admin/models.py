from django.db import models


class UploadJob(models.Model):
	STATUS_PENDING = 'pending'
	STATUS_PROCESSING = 'processing'
	STATUS_COMPLETED = 'completed'
	STATUS_FAILED = 'failed'

	STATUS_CHOICES = [
		(STATUS_PENDING, 'Pending'),
		(STATUS_PROCESSING, 'Processing'),
		(STATUS_COMPLETED, 'Completed'),
		(STATUS_FAILED, 'Failed'),
	]

	file = models.FileField(upload_to='bulk_uploads/%Y/%m/%d/')
	total_rows = models.PositiveIntegerField(default=0)
	processed_rows = models.PositiveIntegerField(default=0)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
	created_at = models.DateTimeField(auto_now_add=True, db_index=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'UploadJob {self.id} ({self.status})'
