from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404, render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.contenttypes.models import ContentType
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as filters
from .models import Video, Clip, Person, Piece, Company, Venue, Performance, PerformancePerformer, ClipPerformer, CustomField, CustomFieldValue
from .serializers import (
    VideoSerializer, ClipSerializer, ClipCreateSerializer,
    PersonSerializer, PieceSerializer, PieceCreateSerializer,
    CompanySerializer, CompanyCreateSerializer,
    VenueSerializer, VenueCreateSerializer,
    PerformanceSerializer, PerformanceCreateSerializer,
    PerformancePerformerSerializer, ClipPerformerSerializer,
    CustomFieldSerializer, CustomFieldValueSerializer
)
from .utils.cloudflare import CloudflareStreamAPI


@staff_member_required
def homepage(request):
    """Homepage with workflow overview and quick links"""
    recent_videos = Video.objects.all().order_by('-upload_date')[:5]
    processing_videos = Video.objects.filter(status='processing').count()
    ready_videos = Video.objects.filter(status='ready').count()
    total_clips = Clip.objects.count()

    context = {
        'recent_videos': recent_videos,
        'processing_videos': processing_videos,
        'ready_videos': ready_videos,
        'total_clips': total_clips,
    }
    return render(request, 'archive/homepage.html', context)


class CustomFieldsFilterBackend:
    """Filter backend that allows filtering by custom field values"""
    
    def filter_queryset(self, request, queryset, view):
        # Look for custom field filters (prefixed with 'custom_')
        for param, value in request.query_params.items():
            if param.startswith('custom_'):
                field_name = param[7:]  # Remove 'custom_' prefix
                content_type = ContentType.objects.get_for_model(queryset.model)
                
                # Filter by objects that have this custom field value (exact match)
                custom_field_values = CustomFieldValue.objects.filter(
                    content_type=content_type,
                    field__name=field_name,
                    value=value
                )
                
                object_ids = custom_field_values.values_list('object_id', flat=True)
                # object_id is CharField (generic FK) but model PKs may be
                # integer/bigint — cast to int so Postgres doesn't choke on
                # the bigint = varchar comparison.
                try:
                    int_ids = [int(oid) for oid in object_ids]
                except (ValueError, TypeError):
                    int_ids = list(object_ids)
                queryset = queryset.filter(pk__in=int_ids)
        
        return queryset

class VideoViewSet(viewsets.ModelViewSet):
    queryset = Video.objects.all()
    serializer_class = VideoSerializer
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, CustomFieldsFilterBackend]
    
    @action(detail=False, methods=['post'])
    def upload(self, request):
        """Upload video file to Cloudflare Stream"""
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file_obj = request.FILES['file']
        title = request.data.get('title', file_obj.name)
        description = request.data.get('description', '')
        
        # Upload to Cloudflare Stream
        try:
            api = CloudflareStreamAPI()
            upload_result = api.upload_video(
                file_obj,
                metadata={'name': title}
            )
        except Exception as e:
            return Response(
                {'error': f'Cloudflare API error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        if not upload_result:
            return Response(
                {'error': 'Failed to upload to Cloudflare Stream'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Create Video record
        video = Video.objects.create(
            title=title,
            description=description,
            cloudflare_stream_id=upload_result['uid'],
            cloudflare_playback_url=upload_result.get('playback', {}).get('hls', ''),
            cloudflare_thumbnail_url=upload_result.get('thumbnail', ''),
            status='processing'
        )
        
        serializer = self.get_serializer(video)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def refresh_metadata(self, request, pk=None):
        """Refresh video metadata from Cloudflare Stream"""
        video = self.get_object()
        
        try:
            video.refresh_metadata()
        except Exception as e:
            return Response(
                {'error': f'Failed to refresh metadata: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        serializer = self.get_serializer(video)
        return Response(serializer.data)

class ClipFilter(filters.FilterSet):
    """Custom filter for Clip model supporting performer and venue filtering"""
    piece = filters.NumberFilter(field_name='piece__id')
    piece__in = filters.CharFilter(method='filter_by_pieces')
    performance = filters.NumberFilter(field_name='performance__id')
    video = filters.UUIDFilter(field_name='video__id')
    performers = filters.NumberFilter(method='filter_by_performer')
    venue = filters.NumberFilter(method='filter_by_venue')

    class Meta:
        model = Clip
        fields = ['piece', 'piece__in', 'performance', 'video', 'performers', 'venue']

    def filter_by_pieces(self, queryset, name, value):
        """Filter clips by multiple piece IDs (comma-separated)"""
        piece_ids = [int(pid) for pid in value.split(',') if pid.strip().isdigit()]
        return queryset.filter(piece_id__in=piece_ids)

    def filter_by_performer(self, queryset, name, value):
        """Filter clips that feature a specific performer via ClipPerformer junction table"""
        return queryset.filter(clip_performers__person_id=value).distinct()

    def filter_by_venue(self, queryset, name, value):
        """Filter clips by venue through the performance relationship"""
        return queryset.filter(performance__venue_id=value).distinct()


class ClipViewSet(viewsets.ModelViewSet):
    queryset = Clip.objects.select_related('video', 'performance', 'piece').all()
    filter_backends = [DjangoFilterBackend, CustomFieldsFilterBackend]
    filterset_class = ClipFilter
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ClipCreateSerializer
        return ClipSerializer
    
    @action(detail=True, methods=['get'])
    def embed_code(self, request, pk=None):
        """Get HTML embed code for this clip"""
        clip = self.get_object()
        
        try:
            api = CloudflareStreamAPI()
            embed_code = api.generate_embed_code(
                clip.video.cloudflare_stream_id,
                start_time=clip.start_time_seconds
            )
            return Response({'embed_code': embed_code})
        except Exception as e:
            return Response(
                {'error': f'Failed to generate embed code: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PersonViewSet(viewsets.ModelViewSet):
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
    filter_backends = [DjangoFilterBackend, CustomFieldsFilterBackend]

class PieceViewSet(viewsets.ModelViewSet):
    queryset = Piece.objects.all()
    filter_backends = [DjangoFilterBackend, CustomFieldsFilterBackend]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PieceCreateSerializer
        return PieceSerializer

class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    filter_backends = [DjangoFilterBackend, CustomFieldsFilterBackend]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CompanyCreateSerializer
        return CompanySerializer

class VenueViewSet(viewsets.ModelViewSet):
    queryset = Venue.objects.all()
    filter_backends = [DjangoFilterBackend, CustomFieldsFilterBackend]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return VenueCreateSerializer
        return VenueSerializer

class PerformanceViewSet(viewsets.ModelViewSet):
    queryset = Performance.objects.all()
    filter_backends = [DjangoFilterBackend, CustomFieldsFilterBackend]

    def get_serializer_class(self):
        if self.action == 'create':
            return PerformanceCreateSerializer
        return PerformanceSerializer

class PerformancePerformerViewSet(viewsets.ModelViewSet):
    queryset = PerformancePerformer.objects.all()
    serializer_class = PerformancePerformerSerializer

class ClipPerformerViewSet(viewsets.ModelViewSet):
    queryset = ClipPerformer.objects.all()
    serializer_class = ClipPerformerSerializer


class CustomFieldViewSet(viewsets.ModelViewSet):
    queryset = CustomField.objects.all()
    serializer_class = CustomFieldSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['field_type', 'is_required', 'name']
    search_fields = ['name', 'help_text']


class CustomFieldValueViewSet(viewsets.ModelViewSet):
    queryset = CustomFieldValue.objects.all()
    serializer_class = CustomFieldValueSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['field', 'content_type']
