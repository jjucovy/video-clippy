from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from datetime import timedelta
import uuid

from .utils.cloudflare import CloudflareStreamAPI


class FieldType(models.Model):
    """Defines the type of custom field (text, number, choice, etc.)"""
    name = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=200, blank=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class CustomField(models.Model):
    """Admin-configurable metadata fields that can be attached to any entity"""
    name = models.CharField(max_length=100, help_text='The name for this field, e.g. "Genre" or "Era"')
    field_type = models.ForeignKey(FieldType, on_delete=models.CASCADE, help_text='What kind of field is this? Use "choice" for dropdowns with fixed options, "text" for free-form input.')
    entity_types = models.JSONField(help_text="Which types of items should have this field")
    choices = models.JSONField(null=True, blank=True, help_text='For choice/dropdown fields, list the options like: ["Ballet", "Modern", "Duncan"]. Leave blank for text fields.')
    is_required = models.BooleanField(default=False, help_text="If checked, this field must be filled in whenever it appears")
    help_text = models.CharField(max_length=200, blank=True, help_text="Optional hint shown to users when filling in this field")
    display_order = models.PositiveIntegerField(default=0, help_text="Fields with lower numbers appear first. Use 0, 10, 20 to leave room for future fields.")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order', 'name']
        unique_together = ['name', 'field_type']
    
    def __str__(self):
        return f"{self.name} ({self.field_type.name})"


class CustomFieldValue(models.Model):
    """Stores actual field values for any entity using generic foreign keys"""
    field = models.ForeignKey(CustomField, on_delete=models.CASCADE, related_name='values')
    
    # Generic foreign key to link to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=255)  # Support both UUID and int PKs
    content_object = GenericForeignKey('content_type', 'object_id')
    
    value = models.JSONField(help_text="Flexible storage for any field type")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['field', 'content_type', 'object_id']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['field']),
        ]
    
    def __str__(self):
        return f"{self.field.name}: {self.value} ({self.content_object})"

class Venue(models.Model):
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
        unique_together = ['name', 'city', 'country']
    
    def __str__(self):
        return f"{self.name}, {self.city}"


class Company(models.Model):
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    
    artistic_director = models.ForeignKey(
        'Person', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='directed_companies'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = "Companies"
    
    def __str__(self):
        return self.name


class Person(models.Model):
    name = models.CharField(max_length=255)
    birth_year = models.PositiveIntegerField(null=True, blank=True)
    
    # Career info
    current_company = models.ForeignKey(
        Company, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='current_members'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = "People"
    
    def __str__(self):
        return self.name


class Piece(models.Model):
    title = models.CharField(max_length=255)
    choreographers = models.ManyToManyField(Person, blank=True, related_name='choreographed_pieces')
    year_created = models.PositiveIntegerField(null=True, blank=True)
    
    # Music info
    composer = models.ForeignKey(
        Person, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='composed_pieces'
    )
    librettist = models.ForeignKey(
        Person, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='libretto_pieces'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['title']
        verbose_name = "Dance Work"
        verbose_name_plural = "Dance Works"

    def __str__(self):
        return self.title


class Performance(models.Model):
    title = models.CharField(max_length=255, help_text="e.g., 'Giselle - Opening Night'")
    date = models.DateField()
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='performances')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='performances')

    # Key personnel
    conductor = models.ForeignKey(
        Person, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='conducted_performances'
    )
    stage_director = models.ForeignKey(
        Person, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='directed_performances'
    )

    # Performers in this performance
    performers = models.ManyToManyField(Person, through='PerformancePerformer', blank=True, related_name='performances')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        unique_together = ['title', 'date', 'venue']

    def __str__(self):
        return f"{self.title} - {self.venue.name} ({self.date})"


class PerformancePerformer(models.Model):
    """Junction table for performance cast with role information"""
    performance = models.ForeignKey(Performance, on_delete=models.CASCADE, related_name='performance_performers')
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='performance_roles')
    role = models.CharField(max_length=255, blank=True, help_text="Character or role name (e.g., 'Giselle', 'Albrecht', 'Corps de ballet')")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['performance', 'person', 'role']
        ordering = ['performance', 'person__name']

    def __str__(self):
        if self.role:
            return f"{self.person.name} as {self.role} in {self.performance.title}"
        return f"{self.person.name} in {self.performance.title}"


class ClipPerformer(models.Model):
    """Junction table for clip performers with notes"""
    clip = models.ForeignKey('Clip', on_delete=models.CASCADE, related_name='clip_performers')
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='clip_performances')
    notes = models.CharField(max_length=500, blank=True, help_text="Role, character, or performance notes for this clip")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['clip', 'person']
        ordering = ['clip', 'person__name']
    
    def __str__(self):
        return f"{self.person.name} in {self.clip.title}"


class Video(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, help_text="e.g., 'VHS Tape #47 - Mixed 1980s Content'")
    description = models.TextField(blank=True, help_text="What we know about this digitized content")
    
    # Core provenance info - essential for any archive
    provenance = models.TextField(blank=True, help_text="Chain of custody and acquisition history")
    
    # Cloudflare Stream fields (legacy, kept during migration to R2)
    cloudflare_stream_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    cloudflare_playback_url = models.URLField(blank=True)
    cloudflare_thumbnail_url = models.URLField(blank=True)

    # TUS upload tracking (legacy)
    tus_upload_url = models.URLField(blank=True, help_text="Cloudflare TUS upload URL for resumable uploads")
    upload_offset = models.BigIntegerField(default=0, help_text="Bytes uploaded so far")
    upload_total = models.BigIntegerField(null=True, blank=True, help_text="Total file size in bytes")
    original_filename = models.CharField(max_length=255, blank=True, help_text="Original file name")

    # R2 storage fields
    r2_key = models.CharField(max_length=500, blank=True, help_text="R2 object key for original upload")
    r2_web_key = models.CharField(max_length=500, blank=True, help_text="R2 key for web-optimized transcode")
    r2_thumbnail_key = models.CharField(max_length=500, blank=True, help_text="R2 key for thumbnail image")

    # Video metadata
    duration_seconds = models.FloatField(null=True, blank=True)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    upload_date = models.DateTimeField(auto_now_add=True)
    file_size_bytes = models.BigIntegerField(null=True, blank=True)

    needs_review = models.BooleanField(default=True, help_text="Needs archivist review to identify content")

    # R2 multipart upload tracking
    r2_upload_id = models.CharField(max_length=500, blank=True,
        help_text="S3 multipart upload ID for resumable R2 uploads")
    r2_upload_parts = models.JSONField(null=True, blank=True,
        help_text="Completed part ETags for multipart resume")

    # Status
    STATUS_CHOICES = [
        ('pending', 'Pending Upload'),
        ('uploading', 'Uploading'),
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('error', 'Error'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    processing_error = models.TextField(blank=True,
        help_text="Error details if processing failed")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    @property
    def duration_formatted(self):
        if not self.duration_seconds:
            return "Unknown"
        return str(timedelta(seconds=self.duration_seconds))

    def refresh_metadata(self):
        video = self
        api = CloudflareStreamAPI()
        details = api.get_video_details(video.cloudflare_stream_id)

        if details:
            # Handle invalid duration from failed video processing
            duration = details.get('duration')
            if duration is not None and duration < 0:
                duration = None
                video.status = 'error'
            else:
                video.status = 'ready' if details.get('status', {}).get('state') == 'ready' else 'processing'

            video.duration_seconds = duration
            video.cloudflare_playback_url = details.get('playback', {}).get('hls', '')
            video.cloudflare_thumbnail_url = details.get('thumbnail', '')
            video.save()
                
    
class Clip(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='clips')
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # R2 storage fields
    r2_key = models.CharField(max_length=500, blank=True, help_text="R2 key for extracted clip MP4")
    r2_thumbnail_key = models.CharField(max_length=500, blank=True, help_text="R2 key for clip thumbnail")
    is_extracted = models.BooleanField(default=False, help_text="True once a real MP4 has been extracted to R2")

    # Timestamp fields (in seconds)
    start_time_seconds = models.DecimalField(
        max_digits=20, decimal_places=3,
        validators=[MinValueValidator(0)]
    )
    end_time_seconds = models.DecimalField(
        max_digits=20, decimal_places=3,        
        validators=[MinValueValidator(0)]
    )
    
    # ARCHIVAL INTELLIGENCE - This is where the real metadata lives!
    performance = models.ForeignKey(
        Performance, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='clips',
        help_text="Which specific performance is this clip from? Leave blank for rehearsals, classes, etc."
    )
    piece = models.ForeignKey(Piece, on_delete=models.SET_NULL, null=True, blank=True)
    performers = models.ManyToManyField(Person, through='ClipPerformer', blank=True, related_name='clips')
    
    # Verification status - keep core archival workflow
    verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Which archivist verified this identification?"
    )
    verification_date = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['video', 'start_time_seconds']
    
    def clean(self):
        if self.start_time_seconds is not None and self.end_time_seconds is not None:
            if self.start_time_seconds >= self.end_time_seconds:
                raise ValidationError("End time must be after start time")

        # Clamp end time to video duration if it exceeds
        if self.video and self.video.duration_seconds:
            if self.end_time_seconds:
                if self.end_time_seconds > self.video.duration_seconds:
                    self.end_time_seconds = self.video.duration_seconds

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    @property
    def duration_seconds(self):
        return self.end_time_seconds - self.start_time_seconds
    
    @property
    def start_time_formatted(self):
        return self.start_time_seconds #str(timedelta(seconds=self.start_time_seconds))
    
    @property
    def end_time_formatted(self):
        return self.end_time_seconds # str(timedelta(seconds=self.end_time_seconds))
    
    @property
    def duration_formatted(self):
        return self.duration_seconds # str(timedelta(seconds=self.duration_seconds))
    
    def __str__(self):
        return f"{self.title} ({self.start_time_formatted}-{self.end_time_formatted})"
