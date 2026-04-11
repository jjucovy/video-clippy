import logging
import os
import tempfile

logger = logging.getLogger(__name__)


def process_video_upload(video_id):
    """Top-level async task entry point. Called via django-q2 async_task().

    This is the stable public API. To swap to Modal.com later,
    change the body of _run_processing_pipeline() without touching callers.
    """
    from archive.models import Video

    video = Video.objects.get(pk=video_id)
    video.status = 'processing'
    video.processing_error = ''
    video.save(update_fields=['status', 'processing_error'])

    try:
        _run_processing_pipeline(video)
        video.status = 'ready'
        video.save(update_fields=['status'])
        logger.info("Video %s processing complete", video_id)
    except Exception as e:
        logger.exception("Processing failed for video %s", video_id)
        video.status = 'error'
        video.processing_error = str(e)[:2000]
        video.save(update_fields=['status', 'processing_error'])


def _run_processing_pipeline(video, local_raw_path=None):
    """Execute the full pipeline: probe -> transcode -> thumbnail -> upload.

    Currently runs locally via FFmpeg. This function is the swap point
    for Modal.com: replace its body with a Modal remote call.

    Args:
        video: Video model instance with r2_key set.
        local_raw_path: Optional path to a local copy of the raw file.
            If provided, skips the R2 download step (used by migration command).
    """
    from archive.utils.r2 import R2Client
    from archive.utils.ffmpeg import probe_metadata, transcode_for_web, generate_thumbnail

    r2 = R2Client()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Step 1: Download raw file from R2 (unless already local)
        if local_raw_path:
            raw_path = local_raw_path
        else:
            raw_path = os.path.join(tmpdir, 'raw_video')
            logger.info("Downloading %s from R2", video.r2_key)
            r2.client.download_file(r2.bucket_name, video.r2_key, raw_path)

        # Step 2: Probe metadata
        logger.info("Probing metadata for video %s", video.pk)
        metadata = probe_metadata(raw_path)
        video.duration_seconds = metadata.get('duration')
        video.width = metadata.get('width')
        video.height = metadata.get('height')
        video.save(update_fields=['duration_seconds', 'width', 'height'])

        # Step 3: Transcode for web
        web_path = os.path.join(tmpdir, 'web.mp4')
        logger.info("Transcoding video %s for web", video.pk)
        transcode_for_web(raw_path, web_path)

        web_key = f"videos/{video.pk}/web.mp4"
        r2.upload_file(web_key, web_path, content_type='video/mp4')
        video.r2_web_key = web_key
        video.save(update_fields=['r2_web_key'])

        # Step 4: Generate thumbnail
        thumb_path = os.path.join(tmpdir, 'thumb.jpg')
        logger.info("Generating thumbnail for video %s", video.pk)
        generate_thumbnail(raw_path, thumb_path)

        thumb_key = f"videos/{video.pk}/thumbnail.jpg"
        r2.upload_file(thumb_key, thumb_path, content_type='image/jpeg')
        video.r2_thumbnail_key = thumb_key
        video.save(update_fields=['r2_thumbnail_key'])

        # Step 5: Get file size from R2
        head = r2.client.head_object(Bucket=r2.bucket_name, Key=video.r2_key)
        video.file_size_bytes = head['ContentLength']
        video.save(update_fields=['file_size_bytes'])


def extract_clip_task(clip_id):
    """Extract a clip segment as a standalone MP4.

    Called via django-q2 async_task() after clip creation.
    Supports both R2-stored videos (downloaded from R2) and Cloudflare
    Stream videos (downloaded via the CF downloads API). Uploads the
    resulting clip MP4 and thumbnail to R2.
    """
    from archive.models import Clip

    try:
        clip = Clip.objects.select_related('video').get(pk=clip_id)
    except Clip.DoesNotExist:
        logger.warning("Clip %s not found (deleted before extraction?), skipping", clip_id)
        return

    video = clip.video

    if not video.r2_web_key and not video.cloudflare_stream_id:
        logger.warning(
            "Clip %s: parent video %s has neither r2_web_key nor cloudflare_stream_id, "
            "cannot extract", clip_id, video.pk
        )
        return

    try:
        _run_clip_extraction(clip, video)
        logger.info("Clip %s extraction complete", clip_id)
    except Exception as e:
        logger.exception("Clip extraction failed for clip %s", clip_id)


def _run_clip_extraction(clip, video):
    """Extract clip from source video via FFmpeg.

    Downloads from R2 if available, otherwise falls back to Cloudflare Stream.
    Swap point for Modal.com — same pattern as _run_processing_pipeline.
    """
    from archive.utils.r2 import R2Client
    from archive.utils.ffmpeg import extract_clip, generate_thumbnail

    r2 = R2Client()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Download source video — prefer R2 (already transcoded), fall back to CF Stream
        source_path = os.path.join(tmpdir, 'source.mp4')
        if video.r2_web_key:
            logger.info("Downloading R2 source %s for clip %s", video.r2_web_key, clip.pk)
            r2.client.download_file(r2.bucket_name, video.r2_web_key, source_path)
        else:
            logger.info(
                "Downloading CF Stream source %s for clip %s",
                video.cloudflare_stream_id, clip.pk
            )
            from archive.utils.cloudflare import CloudflareStreamAPI
            cf = CloudflareStreamAPI()
            cf.download_video(video.cloudflare_stream_id, source_path)

        # Extract clip segment
        clip_path = os.path.join(tmpdir, 'clip.mp4')
        start = float(clip.start_time_seconds)
        end = float(clip.end_time_seconds)
        if start >= end:
            raise ValueError(f"Clip {clip.pk}: start ({start}) >= end ({end})")
        logger.info("Extracting clip %s: %.1fs - %.1fs", clip.pk, start, end)
        extract_clip(source_path, clip_path, start, end)

        # Upload clip MP4
        clip_key = f"clips/{clip.pk}/clip.mp4"
        r2.upload_file(clip_key, clip_path, content_type='video/mp4')

        # Generate thumbnail at clip midpoint
        thumb_path = os.path.join(tmpdir, 'thumb.jpg')
        midpoint = (end - start) / 2
        generate_thumbnail(clip_path, thumb_path, timestamp_seconds=midpoint)

        thumb_key = f"clips/{clip.pk}/thumbnail.jpg"
        r2.upload_file(thumb_key, thumb_path, content_type='image/jpeg')

        # Update clip record
        clip.r2_key = clip_key
        clip.r2_thumbnail_key = thumb_key
        clip.is_extracted = True
        clip.save(update_fields=['r2_key', 'r2_thumbnail_key', 'is_extracted'])
