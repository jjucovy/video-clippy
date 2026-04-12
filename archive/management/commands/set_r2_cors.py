"""Management command to set CORS policy on the R2 bucket.

Run once after configuring R2 credentials:
    python manage.py set_r2_cors --origin https://video-clippy-mvoj.onrender.com
"""
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = 'Set CORS policy on the R2 bucket to allow browser uploads from a given origin'

    def add_arguments(self, parser):
        parser.add_argument(
            '--origin',
            required=True,
            help='The origin to allow (e.g. https://video-clippy-mvoj.onrender.com)',
        )

    def handle(self, *args, **options):
        from archive.utils.r2 import R2Client

        origin = options['origin'].rstrip('/')
        r2 = R2Client()

        cors_config = {
            'CORSRules': [
                {
                    'AllowedOrigins': [origin],
                    'AllowedMethods': ['GET', 'PUT', 'POST', 'DELETE', 'HEAD'],
                    'AllowedHeaders': ['*'],
                    'ExposeHeaders': ['ETag'],
                    'MaxAgeSeconds': 3600,
                }
            ]
        }

        r2.client.put_bucket_cors(
            Bucket=r2.bucket_name,
            CORSConfiguration=cors_config,
        )

        self.stdout.write(self.style.SUCCESS(
            f'CORS policy set on bucket "{r2.bucket_name}" for origin: {origin}'
        ))
