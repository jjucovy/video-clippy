"""
WSGI config for video_cms project.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'video_cms.settings')

application = get_wsgi_application()
