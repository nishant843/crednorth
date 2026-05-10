from django.db import models
import json


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

	JOB_TYPE_USER_IMPORT = 'user_import'
	JOB_TYPE_LEAD_PROCESSING = 'lead_processing'
	
	JOB_TYPE_CHOICES = [
		(JOB_TYPE_USER_IMPORT, 'User Import'),
		(JOB_TYPE_LEAD_PROCESSING, 'Lead Processing (Dedupe+Push)'),
	]

	# Core fields
	file = models.FileField(upload_to='bulk_uploads/%Y/%m/%d/')
	job_type = models.CharField(
		max_length=20,
		choices=JOB_TYPE_CHOICES,
		default=JOB_TYPE_USER_IMPORT
	)
	status = models.CharField(
		max_length=20,
		choices=STATUS_CHOICES,
		default=STATUS_PENDING,
		db_index=True
	)

	# For lead processing: selected lenders (JSON-encoded)
	lenders = models.TextField(default='[]', help_text='JSON array of selected lenders')
	check_dedupe = models.BooleanField(default=True)
	send_leads = models.BooleanField(default=True)

	# Progress tracking
	total_rows = models.PositiveIntegerField(default=0)
	processed_rows = models.PositiveIntegerField(default=0)
	current_batch = models.PositiveIntegerField(default=0)
	total_batches = models.PositiveIntegerField(default=0)

	# Result counts
	success_count = models.PositiveIntegerField(default=0)
	failed_count = models.PositiveIntegerField(default=0)
	created_count = models.PositiveIntegerField(default=0)
	updated_count = models.PositiveIntegerField(default=0)

	# Timing
	started_at = models.DateTimeField(null=True, blank=True)
	completed_at = models.DateTimeField(null=True, blank=True)

	# Error tracking
	error_logs = models.TextField(
		default='',
		blank=True,
		help_text='Error summary and messages'
	)

	# Result file storage
	result_file_path = models.TextField(
		default='',
		blank=True,
		help_text='Path to output CSV result file'
	)

	# Metadata
	created_at = models.DateTimeField(auto_now_add=True, db_index=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'UploadJob {self.id} ({self.job_type}/{self.status})'

	def percentage(self):
		"""Calculate progress percentage."""
		if self.total_rows == 0:
			return 0
		return int((self.processed_rows / self.total_rows) * 100)

	def is_complete(self):
		"""Check if job has completed."""
		return self.status in [self.STATUS_COMPLETED, self.STATUS_FAILED]


class UploadedLeadRow(models.Model):
	"""
	Temporary staging table for uploaded CSV rows.
	Worker processes these DB rows instead of file paths.
	Optimize for batch querying and progress tracking.
	"""
	
	STATUS_PENDING = 'pending'
	STATUS_PROCESSING = 'processing'
	STATUS_SUCCESS = 'success'
	STATUS_FAILED = 'failed'
	
	STATUS_CHOICES = [
		(STATUS_PENDING, 'Pending'),
		(STATUS_PROCESSING, 'Processing'),
		(STATUS_SUCCESS, 'Success'),
		(STATUS_FAILED, 'Failed'),
	]
	
	# Relationship
	upload_job = models.ForeignKey(
		UploadJob,
		on_delete=models.CASCADE,
		related_name='lead_rows',
		db_index=True
	)
	
	# Core phone/identity fields
	phone_number = models.CharField(
		max_length=20,
		blank=True,
		db_index=True
	)
	pan_number = models.CharField(
		max_length=10,
		blank=True,
		db_index=True
	)
	pincode = models.CharField(max_length=6, blank=True)
	
	# Lead data (JSON for flexibility)
	raw_data = models.JSONField(
		default=dict,
		blank=True,
		help_text='Complete row data from CSV'
	)
	
	# Processing fields
	lender_selection = models.TextField(
		default='[]',
		help_text='JSON array of lenders to process for this row'
	)
	processing_status = models.CharField(
		max_length=20,
		choices=STATUS_CHOICES,
		default=STATUS_PENDING,
		db_index=True
	)
	
	# Results (can be processed by multiple lenders)
	lender_results = models.JSONField(
		default=dict,
		blank=True,
		help_text='Dict mapping lender name → result dict'
	)
	
	# Error tracking
	error_message = models.TextField(blank=True)
	
	# Timing
	processed_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True, db_index=True)
	updated_at = models.DateTimeField(auto_now=True)
	
	class Meta:
		ordering = ['created_at']
		db_table = 'crm_admin_uploaded_lead_row'
		indexes = [
			models.Index(fields=['upload_job', 'processing_status']),
			models.Index(fields=['upload_job', 'created_at']),
			models.Index(fields=['processing_status', 'created_at']),
		]
	
	def __str__(self):
		return f'Row {self.id} ({self.phone_number}) - {self.processing_status}'
