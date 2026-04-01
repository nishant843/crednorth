# Gunicorn configuration for Render.com deployment
import multiprocessing
import os

# Bind to Render's PORT environment variable
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# Worker configuration
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'

# Timeout configuration - CRITICAL for bulk uploads
timeout = 300  # 5 minutes for processing large uploads
graceful_timeout = 300
keepalive = 5

# Request limits
max_requests = 2000
max_requests_jitter = 200

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Process naming
proc_name = 'crednorth-backend'
