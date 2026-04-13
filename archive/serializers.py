from django.conf import settings
from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from .models import Video, Clip, Person, Piece, Company, Venue, Performance, PerformancePerformer, ClipPerformer, CustomField, CustomFieldValue


def _r2_url(key):
    """Generate a presigned read URL for an R2 object. Works with private buckets."""
    if not key:
        return ''
    try:
        from .utils.r2 import R2Client
        return R2Client().generate_presigned_read_url(key)
    except Exception:
        return ''


class CustomFieldsMixin:
    """Mixin to add custom fields support to serializers"""
    
    def get_custom_fields(self, obj):
        """Get all custom field values for this object"""
        content_type = ContentType.objects.get_for_model(obj)
        values = CustomFieldValue.objects.filter(
            content_type=content_type,
            object_id=str(obj.pk)
        ).select_related('field')
        
        custom_fields = {}
        for value in values:
            custom_fields[value.field.name] = {
                'value': value.value,
                'field_type': value.field.field_type.name,
                'help_text': value.field.help_text
            }
        return custom_fields
    
    def to_representation(self, instance):
        """Add custom fields to the serialized representation"""
        representation = super().to_representation(instance)
        representation['custom_fields'] = self.get_custom_fields(instance)
        return representation

class PersonSerializer(CustomFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = ['id', 'name', 'birth_year']

class CompanySerializer(CustomFieldsMixin, serializers.ModelSerializer):
    artistic_director = PersonSerializer(read_only=True)
    
    class Meta:
        model = Company
        fields = ['id', 'name', 'city', 'country', 'artistic_director']

class CompanyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['name', 'city', 'country', 'artistic_director']

class VenueSerializer(CustomFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ['id', 'name', 'city', 'country']

class VenueCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ['name', 'city', 'country']

class PieceSerializer(CustomFieldsMixin, serializers.ModelSerializer):
    choreographers = PersonSerializer(many=True, read_only=True)
    composer = PersonSerializer(read_only=True)
    librettist = PersonSerializer(read_only=True)

    class Meta:
        model = Piece
        fields = ['id', 'title', 'choreographers', 'composer', 'librettist', 'year_created']

class PieceCreateSerializer(serializers.ModelSerializer):
    choreographers = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Person.objects.all(), required=False
    )

    class Meta:
        model = Piece
        fields = ['title', 'choreographers', 'composer', 'librettist', 'year_created']

class PerformancePerformerSerializer(serializers.ModelSerializer):
    person = PersonSerializer(read_only=True)
    performance = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = PerformancePerformer
        fields = ['id', 'person', 'performance', 'role']

class ClipPerformerSerializer(serializers.ModelSerializer):
    person = PersonSerializer(read_only=True)
    clip = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ClipPerformer
        fields = ['id', 'person', 'clip', 'notes']

class PerformanceSerializer(CustomFieldsMixin, serializers.ModelSerializer):
    venue = VenueSerializer(read_only=True)
    company = CompanySerializer(read_only=True)
    conductor = PersonSerializer(read_only=True)
    stage_director = PersonSerializer(read_only=True)
    performance_performers = PerformancePerformerSerializer(many=True, read_only=True)

    class Meta:
        model = Performance
        fields = [
            'id', 'title', 'date', 'venue', 'company',
            'conductor', 'stage_director', 'performance_performers'
        ]

class PerformanceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Performance
        fields = [
            'title', 'date', 'venue', 'company',
            'conductor', 'stage_director'
        ]

class VideoSerializer(CustomFieldsMixin, serializers.ModelSerializer):
    duration_formatted = serializers.ReadOnlyField()
    clips_count = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Video
        fields = [
            'id', 'title', 'description', 'provenance',
            'cloudflare_stream_id', 'cloudflare_playback_url', 'cloudflare_thumbnail_url',
            'video_url', 'thumbnail_url',
            'duration_seconds', 'duration_formatted', 'upload_date', 'file_size_bytes',
            'needs_review', 'status', 'clips_count', 'created_at', 'updated_at'
        ]

    def get_clips_count(self, obj):
        return obj.clips.count()

    def get_video_url(self, obj):
        url = _r2_url(obj.r2_web_key)
        return url or obj.cloudflare_playback_url or ''

    def get_thumbnail_url(self, obj):
        url = _r2_url(obj.r2_thumbnail_key)
        return url or obj.cloudflare_thumbnail_url or ''

class ClipSerializer(CustomFieldsMixin, serializers.ModelSerializer):
    video = VideoSerializer(read_only=True)
    performance = PerformanceSerializer(read_only=True)
    piece = PieceSerializer(read_only=True)
    clip_performers = ClipPerformerSerializer(many=True, read_only=True)
    duration_seconds = serializers.ReadOnlyField()
    duration_formatted = serializers.ReadOnlyField()
    start_time_formatted = serializers.ReadOnlyField()
    end_time_formatted = serializers.ReadOnlyField()
    embed_code = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Clip
        fields = [
            'id', 'video', 'title', 'description',
            'start_time_seconds', 'end_time_seconds',
            'start_time_formatted', 'end_time_formatted',
            'duration_seconds', 'duration_formatted',
            'performance', 'piece', 'clip_performers',
            'verified_by', 'verification_date',
            'is_extracted', 'video_url', 'thumbnail_url',
            'embed_code', 'created_at', 'updated_at'
        ]

    def get_embed_code(self, obj):
        if obj.is_extracted and obj.r2_key:
            return ""
        from .utils.cloudflare import CloudflareStreamAPI
        try:
            api = CloudflareStreamAPI()
            return api.generate_embed_code(
                obj.video.cloudflare_stream_id,
                start_time=obj.start_time_seconds
            )
        except:
            return ""

    def get_video_url(self, obj):
        if obj.is_extracted and obj.r2_key:
            url = _r2_url(obj.r2_key)
            if url:
                return url
        url = _r2_url(obj.video.r2_web_key)
        return url or obj.video.cloudflare_playback_url or ''

    def get_thumbnail_url(self, obj):
        url = _r2_url(obj.r2_thumbnail_key)
        if url:
            return url
        url = _r2_url(obj.video.r2_thumbnail_key)
        return url or obj.video.cloudflare_thumbnail_url or ''

class ClipCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clip
        fields = [
            'video', 'title', 'description',
            'start_time_seconds', 'end_time_seconds',
            'performance', 'piece', 'performers'
        ]


class CustomFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomField
        fields = ['id', 'name', 'field_type', 'entity_types', 'choices', 'is_required', 'help_text', 'display_order']


class CustomFieldValueSerializer(serializers.ModelSerializer):
    field = CustomFieldSerializer(read_only=True)
    
    class Meta:
        model = CustomFieldValue
        fields = ['id', 'field', 'value', 'content_type', 'object_id']