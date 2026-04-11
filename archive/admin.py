import logging

from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django import forms
from .models import Video, Clip, Person, Piece, Company, Venue, Performance, PerformancePerformer, ClipPerformer, FieldType, CustomField, CustomFieldValue
import json
from django.conf import settings
from .utils.cloudflare import CloudflareStreamAPI

logger = logging.getLogger(__name__)


def _r2_is_configured():
    """Check if R2 storage is fully configured via environment variables."""
    return all([
        settings.R2_PUBLIC_URL,
        settings.R2_ACCOUNT_ID,
        settings.R2_ACCESS_KEY_ID,
        settings.R2_SECRET_ACCESS_KEY,
    ])

class CustomFieldValueForm(forms.ModelForm):
    """Custom form for CustomFieldValue — uses CharField to avoid JSONField 'null' display"""
    value = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Select a field first'}),
    )

    class Meta:
        model = CustomFieldValue
        fields = ['field', 'value']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Pre-populate value for existing instances
        if self.instance and self.instance.pk and self.instance.value is not None:
            self.initial['value'] = self.instance.value if isinstance(self.instance.value, str) else str(self.instance.value)

        # If editing an existing value with a choice field, use a select widget
        if self.instance and self.instance.pk and self.instance.field:
            field_obj = self.instance.field
            if field_obj.choices:
                choices = [('', '---------')] + [(c, c) for c in field_obj.choices]
                self.fields['value'] = forms.ChoiceField(
                    choices=choices,
                    initial=self.instance.value,
                    required=field_obj.is_required,
                    help_text=field_obj.help_text
                )

    def clean_value(self):
        value = self.cleaned_data.get('value')
        if not value or (isinstance(value, str) and value.strip() == ''):
            # Return None (SQL NULL) for empty values. This means "not set."
            # We intentionally don't use "" because JSONField would store '""'
            # (a JSON string), which is truthy and would confuse API consumers.
            return None
        return value


def make_custom_field_inline(entity_type):
    """Factory function to create entity-specific custom field inlines"""
    class EntityCustomFieldValueInline(GenericTabularInline):
        model = CustomFieldValue
        form = CustomFieldValueForm
        extra = 1
        ct_field = 'content_type'
        ct_fk_field = 'object_id'
        verbose_name = "Custom Field"
        verbose_name_plural = "Custom Fields"

        class Media:
            js = ('admin/js/custom_field_dynamic.js',)

        def get_queryset(self, request):
            qs = super().get_queryset(request)
            return qs.select_related('field', 'field__field_type')

        def formfield_for_foreignkey(self, db_field, request, **kwargs):
            if db_field.name == 'field':
                # Filter to only show fields applicable to this entity type
                kwargs['queryset'] = CustomField.objects.filter(
                    entity_types__contains=entity_type
                )
            return super().formfield_for_foreignkey(db_field, request, **kwargs)

    return EntityCustomFieldValueInline


# Create entity-specific inlines
PieceCustomFieldInline = make_custom_field_inline('piece')
VideoCustomFieldInline = make_custom_field_inline('video')
ClipCustomFieldInline = make_custom_field_inline('clip')
PersonCustomFieldInline = make_custom_field_inline('person')
CompanyCustomFieldInline = make_custom_field_inline('company')
VenueCustomFieldInline = make_custom_field_inline('venue')
PerformanceCustomFieldInline = make_custom_field_inline('performance')


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ['name', 'birth_year', 'current_company']
    list_filter = ['current_company']
    search_fields = ['name']
    autocomplete_fields = ['current_company']
    inlines = [PersonCustomFieldInline]

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'country', 'artistic_director']
    list_filter = ['country']
    search_fields = ['name', 'city', 'country']
    autocomplete_fields = ['artistic_director']
    inlines = [CompanyCustomFieldInline]

@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'country']
    list_filter = ['country', 'city']
    search_fields = ['name', 'city', 'country']
    inlines = [VenueCustomFieldInline]


class ChoreographerFilter(admin.SimpleListFilter):
    title = 'choreographer'
    parameter_name = 'choreographer'

    def lookups(self, request, model_admin):
        # Only show choreographers that are actually assigned to pieces
        people = Person.objects.filter(choreographed_pieces__isnull=False).distinct().order_by('name')
        return [(p.pk, p.name) for p in people]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(choreographers__pk=self.value())
        return queryset


@admin.register(Piece)
class PieceAdmin(admin.ModelAdmin):
    list_display = ['title', 'get_choreographers', 'composer', 'year_created']
    list_filter = ['year_created', ChoreographerFilter]
    search_fields = ['title', 'choreographers__name', 'composer__name']
    autocomplete_fields = ['composer', 'librettist']
    filter_horizontal = ['choreographers']
    inlines = [PieceCustomFieldInline]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('choreographers')

    @admin.display(description='Choreographers')
    def get_choreographers(self, obj):
        return ', '.join(p.name for p in obj.choreographers.all())

class PerformancePerformerInline(admin.TabularInline):
    model = PerformancePerformer
    extra = 0
    autocomplete_fields = ['person']
    fields = ['person', 'role']

class ClipPerformerInline(admin.TabularInline):
    model = ClipPerformer
    extra = 0
    autocomplete_fields = ['person']
    fields = ['person', 'notes']

@admin.register(Performance)
class PerformanceAdmin(admin.ModelAdmin):
    list_display = ['title', 'date', 'venue', 'company', 'performers_list']
    list_filter = ['date', 'venue', 'company']
    search_fields = ['title', 'venue__name', 'company__name']
    autocomplete_fields = ['venue', 'company', 'conductor', 'stage_director']
    date_hierarchy = 'date'
    inlines = [PerformancePerformerInline, PerformanceCustomFieldInline]

    def performers_list(self, obj):
        performance_performers = obj.performance_performers.all()[:3]
        names = [f"{pp.person.name}" + (f" ({pp.role})" if pp.role else "") for pp in performance_performers]
        total_count = obj.performance_performers.count()
        if total_count > 3:
            names.append(f"...+{total_count - 3} more")
        return ", ".join(names) if names else "-"
    performers_list.short_description = 'Cast'

class ClipInline(admin.TabularInline):
    model = Clip
    extra = 0
    fields = [
        'title', 'start_time_seconds', 'end_time_seconds', 'piece'
    ]
    autocomplete_fields = ['piece']

@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'duration_formatted', 'status', 
        'clips_count', 'needs_review', 'upload_date', 'view_cloudflare', 'create_clips_link'
    ]
    list_filter = [
        'status', 'needs_review', 'upload_date'
    ]
    search_fields = [
        'title', 'description', 'provenance'
    ]
    readonly_fields = [
        'id', 'cloudflare_stream_id', 'cloudflare_playback_url',
        'cloudflare_thumbnail_url', 'upload_date', 'created_at', 'updated_at',
        'r2_key', 'r2_web_key', 'r2_thumbnail_key', 'processing_error',
    ]
    inlines = [ClipInline, VideoCustomFieldInline]
    actions = ['refetch_from_cloudflare', 'upload_video_action', 'ingest_from_cloudflare_action']
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['upload_url'] = reverse('admin:video_upload')
        return super().changelist_view(request, extra_context=extra_context)
    
    fieldsets = [
        ('Basic Information', {
            'fields': ('title', 'description', 'status', 'needs_review')
        }),
        ('Source & Provenance', {
            'fields': (
                'provenance',
            )
        }),
        ('Technical Details', {
            'fields': (
                'duration_seconds',
                'file_size_bytes'
            )
        }),
        ('R2 Storage', {
            'fields': (
                'r2_key', 'r2_web_key', 'r2_thumbnail_key', 'processing_error',
            ),
            'classes': ['collapse']
        }),
        ('Cloudflare Stream', {
            'fields': (
                'cloudflare_stream_id', 'cloudflare_playback_url',
                'cloudflare_thumbnail_url'
            ),
            'classes': ['collapse']
        }),
        ('System', {
            'fields': ('id', 'upload_date'),
            'classes': ['collapse']
        })
    ]
    
    def clips_count(self, obj):
        return obj.clips.count()
    clips_count.short_description = 'Clips'
    
    def view_cloudflare(self, obj):
        if obj.cloudflare_stream_id:
            return format_html(
                '<a href="{}" target="_blank">View in CF</a>',
                'https://dash.cloudflare.com/'
            )
        return '-'
    view_cloudflare.short_description = 'Cloudflare'
    
    def create_clips_link(self, obj):
        if obj.status == 'ready' and (obj.cloudflare_stream_id or obj.r2_web_key):
            url = reverse('admin:video_clipper', args=[obj.pk])
            return format_html(
                '<a href="{}" class="button">Create Clips</a>', url
            )
        return '-'
    create_clips_link.short_description = 'Clipping'

    def refetch_from_cloudflare(self, request, queryset):
        for obj in queryset:
            if obj.cloudflare_stream_id:
                obj.refresh_metadata()
            
    def upload_video_action(self, request, queryset):
        # This redirects to the upload page
        return redirect('admin:video_upload')
    upload_video_action.short_description = "Upload new video"
    
    def ingest_from_cloudflare_action(self, request, queryset):
        # This redirects to the ingestion page
        return redirect('admin:video_ingest')
    ingest_from_cloudflare_action.short_description = "Ingest from Cloudflare"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload/', self.admin_site.admin_view(self.upload_video_view), name='video_upload'),
            path('ingest/', self.admin_site.admin_view(self.ingest_video_view), name='video_ingest'),
            path('get-upload-url/', self.admin_site.admin_view(self.get_upload_url_view), name='get_upload_url'),
            path('start-upload/', self.admin_site.admin_view(self.start_upload_view), name='start_upload'),
            path('pending-uploads/', self.admin_site.admin_view(self.pending_uploads_view), name='pending_uploads'),
            path('<path:object_id>/update-progress/', self.admin_site.admin_view(self.update_progress_view), name='update_progress'),
            path('create-video/', self.admin_site.admin_view(self.create_video_view), name='create_video'),
            path('<path:object_id>/clipper/', self.admin_site.admin_view(self.video_clipper_view), name='video_clipper'),
            # R2 multipart upload endpoints
            path('r2/create-multipart/', self.admin_site.admin_view(self.r2_create_multipart_view), name='r2_create_multipart'),
            path('r2/sign-part/', self.admin_site.admin_view(self.r2_sign_part_view), name='r2_sign_part'),
            path('r2/complete-multipart/', self.admin_site.admin_view(self.r2_complete_multipart_view), name='r2_complete_multipart'),
            path('r2/abort-multipart/', self.admin_site.admin_view(self.r2_abort_multipart_view), name='r2_abort_multipart'),
            path('r2/list-parts/', self.admin_site.admin_view(self.r2_list_parts_view), name='r2_list_parts'),
            path('<path:object_id>/processing-status/', self.admin_site.admin_view(self.processing_status_view), name='processing_status'),
        ]
        return custom_urls + urls
    
    def upload_video_view(self, request):
        if request.method == 'POST' and not _r2_is_configured():
            # Legacy CF Stream direct POST upload
            if 'video_file' not in request.FILES:
                messages.error(request, 'No video file provided')
                return render(request, 'admin/archive/video/upload.html')

            file_obj = request.FILES['video_file']
            title = request.POST.get('title', file_obj.name)
            description = request.POST.get('description', '')
            provenance = request.POST.get('provenance', '')

            try:
                api = CloudflareStreamAPI()
                upload_result = api.upload_video(file_obj, metadata={'name': title})

                if upload_result:
                    video = Video.objects.create(
                        title=title,
                        description=description,
                        provenance=provenance,
                        cloudflare_stream_id=upload_result['uid'],
                        cloudflare_playback_url=upload_result.get('playback', {}).get('hls', ''),
                        cloudflare_thumbnail_url=upload_result.get('thumbnail', ''),
                        status='processing'
                    )
                    messages.success(request, f'Video "{title}" uploaded successfully!')
                    return redirect('admin:archive_video_change', video.pk)
                else:
                    messages.error(request, 'Failed to upload video to Cloudflare Stream')
            except Exception as e:
                messages.error(request, f'Upload error: {str(e)}')

        return render(request, 'admin/archive/video/upload.html', {
            'title': 'Upload Video',
            'use_r2': _r2_is_configured(),
        })
    
    def ingest_video_view(self, request):
        """Ingest video from Cloudflare Stream using video ID"""
        if request.method == 'POST':
            stream_id = request.POST.get('stream_id', '').strip()
            title = request.POST.get('title', '').strip()
            description = request.POST.get('description', '').strip()
            provenance = request.POST.get('provenance', '').strip()
            
            if not stream_id:
                messages.error(request, 'Cloudflare Stream ID is required')
                return render(request, 'admin/archive/video/ingest.html', {'title': 'Ingest Video'})
            
            # Check if video already exists
            if Video.objects.filter(cloudflare_stream_id=stream_id).exists():
                messages.error(request, f'Video with Stream ID "{stream_id}" already exists')
                return render(request, 'admin/archive/video/ingest.html', {'title': 'Ingest Video'})
            
            try:
                api = CloudflareStreamAPI()
                details = api.get_video_details(stream_id)
                
                if not details:
                    messages.error(request, f'Video not found in Cloudflare Stream with ID: {stream_id}')
                    return render(request, 'admin/archive/video/ingest.html', {'title': 'Ingest Video'})
                
                # Check if Cloudflare failed to process the video
                duration = details.get('duration')
                if duration is not None and duration < 0:
                    messages.error(
                        request,
                        f'Cloudflare could not process this video (ID: {stream_id}). '
                        'The file was not recognized as a valid video file. '
                        'Please check the file format and try uploading again.'
                    )
                    return render(request, 'admin/archive/video/ingest.html', {'title': 'Ingest Video'})

                # Use provided title or fallback to Cloudflare metadata
                final_title = title or details.get('meta', {}).get('name', f'Video {stream_id}')

                video = Video.objects.create(
                    title=final_title,
                    description=description,
                    provenance=provenance,
                    cloudflare_stream_id=stream_id,
                    cloudflare_playback_url=details.get('playback', {}).get('hls', ''),
                    cloudflare_thumbnail_url=details.get('thumbnail', ''),
                    duration_seconds=duration,
                    file_size_bytes=details.get('size'),
                    status='ready' if details.get('status', {}).get('state') == 'ready' else 'processing'
                )
                
                messages.success(request, f'Video "{final_title}" ingested successfully!')
                return redirect('admin:archive_video_change', video.pk)
                
            except Exception as e:
                messages.error(request, f'Ingestion error: {str(e)}')
        
        return render(request, 'admin/archive/video/ingest.html', {
            'title': 'Ingest Video from Cloudflare',
        })
    
    def get_upload_url_view(self, request):
        """Proxy TUS creation requests to Cloudflare Stream API"""
        if request.method == 'POST':
            try:
                import requests as http_requests
                from django.conf import settings

                # Get TUS headers from the client
                upload_length = request.headers.get('Upload-Length')
                upload_metadata = request.headers.get('Upload-Metadata', '')
                tus_resumable = request.headers.get('Tus-Resumable', '1.0.0')

                if not upload_length:
                    return JsonResponse({'success': False, 'error': 'Missing Upload-Length header'}, status=400)

                account_id = getattr(settings, 'CLOUDFLARE_ACCOUNT_ID', None)
                api_token = getattr(settings, 'CLOUDFLARE_API_TOKEN', None)
                if not account_id or not api_token:
                    return JsonResponse({
                        'success': False,
                        'error': 'Cloudflare credentials not configured on server (CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN)',
                    }, status=500)

                # Proxy the request to Cloudflare Stream with TUS headers.
                # Content-Length: 0 is required by the TUS spec for creation requests (no body).
                endpoint = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/stream?direct_user=true"

                response = http_requests.post(
                    endpoint,
                    headers={
                        'Authorization': f'Bearer {api_token}',
                        'Tus-Resumable': tus_resumable,
                        'Upload-Length': str(upload_length),
                        'Upload-Metadata': upload_metadata,
                        'Content-Length': '0',
                    },
                    data=b'',
                )

                # Get the upload URL from the Location header
                destination = response.headers.get('Location')

                if destination:
                    from django.http import HttpResponse
                    http_response = HttpResponse(status=response.status_code)
                    http_response['Access-Control-Expose-Headers'] = 'Location'
                    http_response['Access-Control-Allow-Headers'] = '*'
                    http_response['Access-Control-Allow-Origin'] = '*'
                    http_response['Location'] = destination
                    return http_response
                else:
                    logger.error(
                        "CF Stream TUS creation failed: status=%s body=%r headers=%r",
                        response.status_code, response.text[:500], dict(response.headers)
                    )
                    return JsonResponse({
                        'success': False,
                        'error': 'No location header in Cloudflare response',
                        'cf_status': response.status_code,
                        'cf_body': response.text[:500],
                    }, status=500)

            except Exception as e:
                logger.exception("get_upload_url_view error")
                return JsonResponse({'success': False, 'error': str(e)}, status=500)

        return JsonResponse({'success': False, 'error': 'POST required'}, status=400)

    def start_upload_view(self, request):
        """Create a Video record before upload starts"""
        if request.method == 'POST':
            try:
                data = json.loads(request.body)

                title = data.get('title', 'Untitled Video')
                description = data.get('description', '')
                provenance = data.get('provenance', '')
                filename = data.get('filename', '')
                file_size = data.get('file_size', 0)

                # Create video record in pending state
                video = Video.objects.create(
                    title=title,
                    description=description,
                    provenance=provenance,
                    original_filename=filename,
                    upload_total=file_size,
                    status='pending'
                )

                return JsonResponse({
                    'success': True,
                    'video_id': str(video.pk)
                })
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)}, status=500)

        return JsonResponse({'success': False, 'error': 'POST required'}, status=400)

    def pending_uploads_view(self, request):
        """Get list of pending/uploading videos"""
        if request.method == 'GET':
            pending_videos = Video.objects.filter(
                status__in=['pending', 'uploading']
            ).values(
                'id', 'title', 'original_filename', 'upload_offset', 'upload_total',
                'tus_upload_url', 'r2_upload_id', 'r2_key', 'created_at',
            )

            return JsonResponse({
                'success': True,
                'uploads': list(pending_videos)
            })

        return JsonResponse({'success': False, 'error': 'GET required'}, status=400)

    def update_progress_view(self, request, object_id):
        """Update upload progress for a video"""
        from django.views.decorators.csrf import csrf_exempt

        if request.method == 'PATCH':
            try:
                data = json.loads(request.body)

                video = Video.objects.get(pk=object_id)

                # Update fields
                if 'tus_upload_url' in data:
                    video.tus_upload_url = data['tus_upload_url']
                if 'upload_offset' in data:
                    video.upload_offset = data['upload_offset']
                if 'status' in data:
                    video.status = data['status']
                if 'cloudflare_stream_id' in data:
                    video.cloudflare_stream_id = data['cloudflare_stream_id']

                video.save()

                return JsonResponse({'success': True})
            except Video.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Video not found'}, status=404)
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)}, status=500)

        return JsonResponse({'success': False, 'error': 'PATCH required'}, status=400)

    # --- R2 Multipart Upload Views ---

    def r2_create_multipart_view(self, request):
        """Initiate an R2 multipart upload for a video."""
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=400)
        try:
            from .utils.r2 import R2Client
            data = json.loads(request.body)
            video_id = data['video_id']
            filename = data.get('filename', 'video.mp4')
            content_type = data.get('content_type', 'video/mp4')

            video = Video.objects.get(pk=video_id)
            key = f"videos/{video.pk}/raw/{filename}"

            # Only allow video content types to prevent XSS via stored content-type
            if not content_type.startswith('video/'):
                content_type = 'video/mp4'

            r2 = R2Client()
            upload_id = r2.create_multipart_upload(key, content_type=content_type)

            video.r2_key = key
            video.r2_upload_id = upload_id
            video.status = 'uploading'
            video.save(update_fields=['r2_key', 'r2_upload_id', 'status'])

            return JsonResponse({'key': key, 'uploadId': upload_id})
        except Video.DoesNotExist:
            return JsonResponse({'error': 'Video not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def _get_video_for_r2_upload(self, video_id):
        """Look up a Video and verify it has an active R2 multipart upload.
        Returns (video, error_response) — error_response is None on success."""
        try:
            video = Video.objects.get(pk=video_id)
        except Video.DoesNotExist:
            return None, JsonResponse({'error': 'Video not found'}, status=404)
        if not video.r2_key or not video.r2_upload_id:
            return None, JsonResponse({'error': 'No active R2 upload for this video'}, status=400)
        return video, None

    def r2_sign_part_view(self, request):
        """Generate a presigned URL for uploading one part."""
        if request.method != 'GET':
            return JsonResponse({'error': 'GET required'}, status=400)
        try:
            from .utils.r2 import R2Client
            video, err = self._get_video_for_r2_upload(request.GET.get('video_id'))
            if err:
                return err
            part_number = int(request.GET['part_number'])

            r2 = R2Client()
            url = r2.sign_part(video.r2_key, video.r2_upload_id, part_number)
            return JsonResponse({'url': url})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def r2_complete_multipart_view(self, request):
        """Complete a multipart upload and queue processing."""
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=400)
        try:
            from .utils.r2 import R2Client
            from django_q.tasks import async_task
            data = json.loads(request.body)

            # Verify video ownership BEFORE committing R2 upload
            video, err = self._get_video_for_r2_upload(data.get('video_id'))
            if err:
                return err

            r2 = R2Client()
            r2.complete_multipart_upload(video.r2_key, video.r2_upload_id, data['parts'])

            video.status = 'processing'
            video.r2_upload_id = ''  # Clear upload tracking
            video.r2_upload_parts = None
            video.save(update_fields=['status', 'r2_upload_id', 'r2_upload_parts'])

            # Queue async processing
            async_task('archive.tasks.process_video_upload', str(video.pk))

            return JsonResponse({
                'success': True,
                'redirect_url': reverse('admin:archive_video_change', args=[video.pk]),
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def r2_abort_multipart_view(self, request):
        """Abort an in-progress multipart upload."""
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=400)
        try:
            from .utils.r2 import R2Client
            data = json.loads(request.body)

            video, err = self._get_video_for_r2_upload(data.get('video_id'))
            if err:
                return err

            r2 = R2Client()
            r2.abort_multipart_upload(video.r2_key, video.r2_upload_id)
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def r2_list_parts_view(self, request):
        """List already-uploaded parts for resume support."""
        if request.method != 'GET':
            return JsonResponse({'error': 'GET required'}, status=400)
        try:
            from .utils.r2 import R2Client
            video, err = self._get_video_for_r2_upload(request.GET.get('video_id'))
            if err:
                return err

            r2 = R2Client()
            parts = r2.list_parts(video.r2_key, video.r2_upload_id)
            return JsonResponse(parts, safe=False)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def processing_status_view(self, request, object_id):
        """Return processing status for polling from change_form."""
        if request.method != 'GET':
            return JsonResponse({'error': 'GET required'}, status=400)
        try:
            video = Video.objects.get(pk=object_id)
            return JsonResponse({
                'status': video.status,
                'processing_error': video.processing_error,
            })
        except Video.DoesNotExist:
            return JsonResponse({'error': 'Video not found'}, status=404)

    def create_video_view(self, request):
        """Create video record after successful upload"""
        if request.method == 'POST':
            try:
                data = json.loads(request.body)

                video = Video.objects.create(
                    title=data.get('title', 'Untitled Video'),
                    description=data.get('description', ''),
                    provenance=data.get('provenance', ''),
                    cloudflare_stream_id=data['stream_id'],
                    status='processing'
                )
                
                return JsonResponse({
                    'success': True,
                    'video_id': str(video.pk),
                    'redirect_url': reverse('admin:archive_video_change', args=[video.pk])
                })
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})
        
        return JsonResponse({'success': False, 'error': 'POST required'})
    
    def video_clipper_view(self, request, object_id):
        video = self.get_object(request, object_id)
        if not video:
            messages.error(request, 'Video not found')
            return redirect('admin:archive_video_changelist')
        
        if video.status != 'ready':
            messages.error(request, 'Video is not ready for clipping yet')
            return redirect('admin:archive_video_change', video.pk)
        
        if request.method == 'POST':
            # Handle clip creation with performers
            from decimal import Decimal
            
            try:
                # Create the clip
                clip = Clip.objects.create(
                    video=video,
                    title=request.POST.get('title', ''),
                    description=request.POST.get('description', ''),
                    start_time_seconds=Decimal(request.POST.get('start_time_seconds', '0')),
                    end_time_seconds=Decimal(request.POST.get('end_time_seconds', '0')),
                    piece_id=request.POST.get('piece') if request.POST.get('piece') else None,
                    performance_id=request.POST.get('performance') if request.POST.get('performance') else None,
                )
                
                # Add performers if provided
                performers_data = request.POST.get('performers_data')
                if performers_data:
                    try:
                        performers_list = json.loads(performers_data)
                        for performer_data in performers_list:
                            ClipPerformer.objects.create(
                                clip=clip,
                                person_id=performer_data['person_id'],
                                notes=performer_data.get('notes', '')
                            )
                    except (json.JSONDecodeError, KeyError) as e:
                        messages.warning(request, f'Clip created but could not add performers: {e}')
                
                # Queue clip extraction. R2 must be configured for the output.
                # Source can be either an R2-stored video or a Cloudflare Stream video.
                if (video.r2_web_key or video.cloudflare_stream_id) and _r2_is_configured():
                    from django_q.tasks import async_task
                    async_task('archive.tasks.extract_clip_task', str(clip.pk))

                messages.success(request, f'Clip "{clip.title}" created successfully!')
                return JsonResponse({'success': True})
                
            except Exception as e:
                messages.error(request, f'Error creating clip: {e}')
                return JsonResponse({'success': False, 'error': str(e)}, status=400)
        
        # Build R2 video URL if available
        r2_video_url = ''
        if video.r2_web_key and _r2_is_configured():
            from .utils.r2 import R2Client
            r2_video_url = R2Client().generate_url(video.r2_web_key)

        context = {
            'title': f'Create Clips - {video.title}',
            'video': video,
            'use_r2': bool(r2_video_url),
            'r2_video_url': r2_video_url,
            'pieces': Piece.objects.all(),
            'people': Person.objects.all(),
            'performances': Performance.objects.all(),
            'venues': Venue.objects.all(),
            'companies': Company.objects.all(),
        }
        return render(request, 'admin/archive/video/clipper.html', context)

@admin.register(Clip)
class ClipAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'video', 'start_time_formatted',
        'duration_formatted', 'piece', 'performers_list', 'extraction_status',
    ]
    list_filter = [
        'video', 'piece', 'is_extracted', 'created_at'
    ]
    search_fields = [
        'title', 'description', 'video__title',
        'piece__title', 'clip_performers__person__name'
    ]
    readonly_fields = ['r2_key', 'r2_thumbnail_key', 'is_extracted']
    autocomplete_fields = ['video', 'performance', 'piece', 'verified_by']
    inlines = [ClipPerformerInline, ClipCustomFieldInline]

    fieldsets = [
        ('Basic Information', {
            'fields': ('video', 'title', 'description')
        }),
        ('Timing', {
            'fields': ('start_time_seconds', 'end_time_seconds')
        }),
        ('Performance Context', {
            'fields': ('performance', 'piece')
        }),
        ('R2 Storage', {
            'fields': ('r2_key', 'r2_thumbnail_key', 'is_extracted'),
            'classes': ['collapse']
        }),
        ('Archival Verification', {
            'fields': ('verified_by', 'verification_date')
        }),
    ]

    @admin.display(description='Extracted', boolean=True)
    def extraction_status(self, obj):
        return obj.is_extracted
    
    def performers_list(self, obj):
        clip_performers = obj.clip_performers.all()[:3]
        names = [f"{cp.person.name}" + (f" ({cp.notes})" if cp.notes else "") for cp in clip_performers]
        total_count = obj.clip_performers.count()
        if total_count > 3:
            names.append(f"...+{total_count - 3} more")
        return ", ".join(names) if names else "-"
    performers_list.short_description = 'Performers'

@admin.register(PerformancePerformer)
class PerformancePerformerAdmin(admin.ModelAdmin):
    list_display = ['performance', 'person', 'role']
    list_filter = ['performance__date', 'performance__company', 'person']
    search_fields = ['person__name', 'role', 'performance__title']
    autocomplete_fields = ['performance', 'person']

@admin.register(ClipPerformer)
class ClipPerformerAdmin(admin.ModelAdmin):
    list_display = ['clip', 'person', 'notes']
    list_filter = ['clip__video', 'person']
    search_fields = ['person__name', 'notes', 'clip__title']
    autocomplete_fields = ['clip', 'person']


@admin.register(FieldType)
class FieldTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name', 'description']

    def has_module_permission(self, request):
        # Hide from admin sidebar — superusers can still access via direct URL
        return request.user.is_superuser


class PlainTextChoicesWidget(forms.Textarea):
    """Displays JSON list choices as one-per-line plain text"""
    def __init__(self, attrs=None):
        default_attrs = {'rows': 4, 'cols': 40,
                         'placeholder': 'Enter one choice per line, e.g.:\nBallet\nModern\nDuncan'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)

    def format_value(self, value):
        if value is None or value == 'null' or value == '':
            return ''
        if isinstance(value, list):
            return '\n'.join(str(item) for item in value)
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return '\n'.join(str(item) for item in parsed)
            except (json.JSONDecodeError, TypeError):
                pass
            return value
        return str(value)


class PlainTextChoicesField(forms.CharField):
    """Form field that accepts one-choice-per-line and returns a Python list"""
    widget = PlainTextChoicesWidget

    def clean(self, value):
        value = super().clean(value)
        if not value or not value.strip():
            return None
        choices = [line.strip() for line in value.split('\n') if line.strip()]
        return list(dict.fromkeys(choices))  # deduplicate, preserving order


class CustomFieldAdminForm(forms.ModelForm):
    """Custom form for CustomField admin with checkbox entity_types and plain-text choices"""
    ENTITY_TYPE_CHOICES = [
        ('video', 'Video'),
        ('clip', 'Clip'),
        ('piece', 'Dance Work'),
        ('person', 'Person'),
        ('company', 'Company'),
        ('venue', 'Venue'),
        ('performance', 'Performance'),
    ]

    entity_types = forms.MultipleChoiceField(
        choices=ENTITY_TYPE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select which types of items this field applies to"
    )

    choices = PlainTextChoicesField(
        required=False,
        help_text='Enter one option per line. Leave blank for free-text fields.'
    )

    class Meta:
        model = CustomField
        fields = ['name', 'field_type', 'entity_types', 'choices', 'is_required', 'help_text', 'display_order']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Auto-create standard field types so the user never has to
        choice_type, _ = FieldType.objects.get_or_create(
            name='choice', defaults={'description': 'Dropdown with fixed options'}
        )
        FieldType.objects.get_or_create(
            name='text', defaults={'description': 'Free-form text input'}
        )
        # Default to "choice" for new fields
        if not self.instance.pk:
            self.fields['field_type'].initial = choice_type.pk


@admin.register(CustomField)
class CustomFieldAdmin(admin.ModelAdmin):
    form = CustomFieldAdminForm
    list_display = ['name', 'field_type', 'entity_types_display', 'choices_preview', 'is_required', 'display_order']
    list_filter = ['field_type', 'is_required']
    search_fields = ['name', 'help_text']
    ordering = ['display_order', 'name']

    fieldsets = [
        ('Basic Information', {
            'fields': ('name', 'field_type', 'help_text'),
            'description': 'Give your field a name (e.g., "Genre") and pick what kind of field it is.'
        }),
        ('Configuration', {
            'fields': ('entity_types', 'choices', 'is_required', 'display_order'),
            'description': 'Check which types of items this field applies to, and enter the options (one per line).'
        }),
    ]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'choices-for-field/<int:field_id>/',
                self.admin_site.admin_view(self.choices_for_field_view),
                name='customfield_choices'
            ),
        ]
        return custom_urls + urls

    def choices_for_field_view(self, request, field_id):
        """Return choices for a given custom field as JSON (used by dynamic inline JS)"""
        try:
            field = CustomField.objects.get(pk=field_id)
            return JsonResponse({
                'choices': field.choices or [],
                'field_type': field.field_type.name,
                'name': field.name,
            })
        except CustomField.DoesNotExist:
            return JsonResponse({'choices': [], 'field_type': '', 'name': ''}, status=404)

    def entity_types_display(self, obj):
        """Display entity types as comma-separated list"""
        if obj.entity_types:
            return ", ".join(obj.entity_types)
        return "-"
    entity_types_display.short_description = 'Applies To'

    def choices_preview(self, obj):
        """Show preview of choices for choice-type fields"""
        if obj.choices:
            choices_list = obj.choices if isinstance(obj.choices, list) else []
            if len(choices_list) <= 3:
                return ", ".join(str(c) for c in choices_list)
            return f"{', '.join(str(c) for c in choices_list[:3])}... (+{len(choices_list) - 3})"
        return "-"
    choices_preview.short_description = 'Choices'


@admin.register(CustomFieldValue)
class CustomFieldValueAdmin(admin.ModelAdmin):
    list_display = ['field', 'content_object', 'value']
    list_filter = ['field', 'content_type']
    search_fields = ['field__name', 'value']
    autocomplete_fields = ['field']
