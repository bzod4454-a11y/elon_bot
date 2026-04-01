# Gunicorn configuration for production

import multiprocessing
import os

# Server socket
bind = f"127.0.0.1:{os.getenv('PORT', '5000')}"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
worker_connections = 1000
timeout = 120
graceful_timeout = 30
keepalive = 5

# Logging
accesslog = 'logs/gunicorn_access.log'
errorlog = 'logs/gunicorn_error.log'
loglevel = 'info'

# Process naming
proc_name = 'elonbot_api'

# Server mechanics
daemon = False
pidfile = 'logs/gunicorn.pid'
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (agar mavjud bo'lsa)
# keyfile = '/etc/ssl/private/your-domain.key'
# certfile = '/etc/ssl/certs/your-domain.crt'