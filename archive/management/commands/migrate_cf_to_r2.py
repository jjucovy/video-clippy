"""Management command to migrate videos from Cloudflare Stream to R2.

For each CF Stream video that hasn't been migrated yet:
1. Download the MP4 from CF Stream
2. Upload raw file to R2
3. Run the processing pipeline (probe, transcode, thumbnail)
4. Extract all clips as standalone MP4s

Resumable: skips videos that already have r2_web_key set.
"""

import logging
import os
import tempfile

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migrate videos from Cloudflare Stream to R2 storage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--video-id',
            type=str,
            help='Migrate a single video by UUID',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without making changes',
        )
        parser.add_argument(
            '--skip-clips',
            action='store_true',
            help='Migrate videos only, skip clip extraction',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Process at most N videos (0 = all)',
        )

    def handle(self, *args, **options):
        from archive.models import Video

        video_id = options['video_id']
        dry_run = options['dry_run']
        skip_clips = options['skip_clips']
        limit = options['limit']

        # CF Stream videos not yet migrated (r2_web_key is empty)
        qs = Video.objects.exclude(
            cloudflare_stream_id='',
        ).exclude(
            cloudflare_stream_id__isnull=True,
        ).filter(
            r2_web_key='',
        )

        if video_id:
            qs = qs.filter(pk=video_id)

        if limit:
            qs = qs[:limit]

        videos = list(qs)

        if not videos:
            self.stdout.write(self.style.SUCCESS('No videos to migrate.'))
            return

        self.stdout.write(f'Found {len(videos)} video(s) to migrate.')

        if dry_run:
            for v in videos:
                clips_count = v.clips.count()
                self.stdout.write(
                    f'  [{v.pk}] {v.title} '
                    f'(CF: {v.cloudflare_stream_id}, '
                    f'{clips_count} clip(s))'
                )
            self.stdout.write(self.style.WARNING('Dry run — no changes made.'))
            return

        # Create clients once for reuse across all videos
        from archive.utils.cloudflare import CloudflareStreamAPI
        from archive.utils.r2 import R2Client
        cf = CloudflareStreamAPI()
        r2 = R2Client()

        success = 0
        failed = 0

        for i, video in enumerate(videos, 1):
            prior_status = video.status
            self.stdout.write(
                f'\n[{i}/{len(videos)}] Migrating: {video.title} '
                f'(CF: {video.cloudflare_stream_id})'
            )
            try:
                self._migrate_video(video, cf, r2, skip_clips)
                success += 1
                self.stdout.write(self.style.SUCCESS(f'  Done: {video.title}'))
            except Exception as e:
                failed += 1
                logger.exception('Failed to migrate video %s', video.pk)
                self.stdout.write(self.style.ERROR(f'  FAILED: {e}'))
                # Reset video state on failure
                video.status = prior_status
                video.processing_error = str(e)[:2000]
                video.save(update_fields=['status', 'processing_error'])

        self.stdout.write(
            f'\nMigration complete: {success} succeeded, {failed} failed.'
        )

    def _migrate_video(self, video, cf, r2, skip_clips):
        from archive.tasks import _run_processing_pipeline, _run_clip_extraction

        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: Download from CF Stream
            raw_path = os.path.join(tmpdir, 'source.mp4')
            self.stdout.write('  Downloading from CF Stream...')
            cf.download_video(video.cloudflare_stream_id, raw_path)

            file_size = os.path.getsize(raw_path)
            self.stdout.write(
                f'  Downloaded: {file_size / 1024 / 1024:.1f} MB'
            )

            # Step 2: Upload raw to R2
            raw_key = f"videos/{video.pk}/raw.mp4"
            self.stdout.write('  Uploading raw to R2...')
            r2.upload_file(raw_key, raw_path, content_type='video/mp4')
            video.r2_key = raw_key
            video.save(update_fields=['r2_key'])

            # Step 3: Run processing pipeline with local file (avoids re-download)
            self.stdout.write('  Processing (probe, transcode, thumbnail)...')
            video.status = 'processing'
            video.processing_error = ''
            video.save(update_fields=['status', 'processing_error'])

            _run_processing_pipeline(video, local_raw_path=raw_path)

            video.status = 'ready'
            video.save(update_fields=['status'])
            self.stdout.write(f'  Video ready: r2_web_key={video.r2_web_key}')

        # Step 4: Extract clips
        if not skip_clips:
            clips = list(video.clips.filter(is_extracted=False))
            if clips:
                self.stdout.write(f'  Extracting {len(clips)} clip(s)...')
                for clip in clips:
                    try:
                        _run_clip_extraction(clip, video)
                        self.stdout.write(f'    Clip "{clip.title}" extracted')
                    except Exception as e:
                        logger.exception(
                            'Clip extraction failed for clip %s', clip.pk
                        )
                        self.stdout.write(
                            self.style.WARNING(
                                f'    Clip "{clip.title}" FAILED: {e}'
                            )
                        )
