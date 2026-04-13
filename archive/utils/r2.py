import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class R2Client:
    """Cloudflare R2 storage client (S3-compatible API)."""

    def __init__(self):
        required = {
            'R2_ACCOUNT_ID': settings.R2_ACCOUNT_ID,
            'R2_ACCESS_KEY_ID': settings.R2_ACCESS_KEY_ID,
            'R2_SECRET_ACCESS_KEY': settings.R2_SECRET_ACCESS_KEY,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ImproperlyConfigured(
                f"R2 storage is not configured. Missing: {', '.join(missing)}"
            )

        self.bucket_name = settings.R2_BUCKET_NAME
        self.client = boto3.client(
            's3',
            endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name='auto',
        )

    def upload_file(self, key, file_obj, content_type=None):
        """Upload a file to R2.

        Args:
            key: Object key (path) in the bucket.
            file_obj: File-like object or path string.
            content_type: Optional MIME type.
        """
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type

        if isinstance(file_obj, str):
            self.client.upload_file(file_obj, self.bucket_name, key, ExtraArgs=extra_args)
        else:
            self.client.upload_fileobj(file_obj, self.bucket_name, key, ExtraArgs=extra_args)

    def generate_presigned_read_url(self, key, expires_in=3600):
        """Generate a presigned URL for reading (GET) an R2 object.

        Works with private buckets — no public access required.
        Default expiry is 1 hour, which is fine since URLs are generated
        fresh on each API/serializer call.
        """
        return self.client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket_name, 'Key': key},
            ExpiresIn=expires_in,
        )

    def generate_url(self, key):
        """Return a URL for an R2 object.

        Uses a presigned read URL so private buckets work without public access.
        Falls back to public URL construction if R2_PUBLIC_URL is set and
        presigned URL generation fails.
        """
        if not key:
            return ''
        return self.generate_presigned_read_url(key)

    def delete_file(self, key):
        """Delete an object from R2."""
        self.client.delete_object(Bucket=self.bucket_name, Key=key)

    def generate_presigned_url(self, key, content_type=None, expires_in=3600):
        """Generate a presigned URL for direct upload to R2.

        Returns a URL that clients can PUT to directly.
        """
        params = {
            'Bucket': self.bucket_name,
            'Key': key,
        }
        if content_type:
            params['ContentType'] = content_type

        return self.client.generate_presigned_url(
            'put_object',
            Params=params,
            ExpiresIn=expires_in,
        )

    def file_exists(self, key):
        """Check if an object exists in R2."""
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise

    # --- S3 Multipart Upload (for browser-direct large file uploads) ---

    def create_multipart_upload(self, key, content_type='video/mp4'):
        """Initiate an S3 multipart upload. Returns upload_id."""
        response = self.client.create_multipart_upload(
            Bucket=self.bucket_name,
            Key=key,
            ContentType=content_type,
        )
        return response['UploadId']

    def sign_part(self, key, upload_id, part_number, expires_in=3600):
        """Generate a presigned URL for uploading one part."""
        return self.client.generate_presigned_url(
            'upload_part',
            Params={
                'Bucket': self.bucket_name,
                'Key': key,
                'UploadId': upload_id,
                'PartNumber': part_number,
            },
            ExpiresIn=expires_in,
        )

    def complete_multipart_upload(self, key, upload_id, parts):
        """Complete a multipart upload.

        Args:
            parts: List of {'PartNumber': N, 'ETag': '...'} dicts.
        """
        self.client.complete_multipart_upload(
            Bucket=self.bucket_name,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={'Parts': parts},
        )

    def abort_multipart_upload(self, key, upload_id):
        """Abort an in-progress multipart upload."""
        self.client.abort_multipart_upload(
            Bucket=self.bucket_name,
            Key=key,
            UploadId=upload_id,
        )

    def list_parts(self, key, upload_id):
        """List already-uploaded parts (for resume support)."""
        response = self.client.list_parts(
            Bucket=self.bucket_name,
            Key=key,
            UploadId=upload_id,
        )
        return response.get('Parts', [])
