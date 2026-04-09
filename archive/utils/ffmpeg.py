import json
import subprocess
import logging

logger = logging.getLogger(__name__)


def transcode_for_web(input_path, output_path):
    """Transcode video to web-optimized H.264/AAC MP4.

    Uses -crf 23 for good quality/size balance and -movflags +faststart
    so the video can start playing before fully downloaded.
    """
    cmd = [
        'ffmpeg', '-i', input_path,
        '-c:v', 'libx264', '-crf', '23', '-preset', 'medium',
        '-c:a', 'aac', '-b:a', '128k',
        '-movflags', '+faststart',
        '-y', output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("FFmpeg transcode failed: %s", result.stderr)
        raise RuntimeError(f"FFmpeg transcode failed: {result.stderr[-500:]}")


def extract_clip(input_path, output_path, start_seconds, end_seconds, precise=False):
    """Extract a clip from a video.

    By default uses stream copy (-c copy) for speed. Set precise=True to
    re-encode for frame-accurate boundaries (slower but exact).

    Note on -ss/-to placement: In precise mode, -ss comes after -i so FFmpeg
    decodes from the start (slow but frame-accurate), and -to is an absolute
    timestamp. In fast/copy mode, -ss comes before -i so FFmpeg seeks to the
    nearest keyframe (fast but may be a few frames off), and -to becomes
    relative to the new start — hence we pass a duration, not an absolute end.
    """
    if precise:
        # -ss after -i: decode from start, frame-accurate. -to is absolute.
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-ss', str(start_seconds),
            '-to', str(end_seconds),
            '-c:v', 'libx264', '-crf', '23', '-preset', 'medium',
            '-c:a', 'aac', '-b:a', '128k',
            '-movflags', '+faststart',
            '-y', output_path,
        ]
    else:
        # -ss before -i: fast keyframe seek. -to is a duration from the seek point.
        clip_duration = end_seconds - start_seconds
        cmd = [
            'ffmpeg',
            '-ss', str(start_seconds),
            '-i', input_path,
            '-to', str(clip_duration),
            '-c', 'copy',
            '-movflags', '+faststart',
            '-y', output_path,
        ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("FFmpeg clip extraction failed: %s", result.stderr)
        raise RuntimeError(f"FFmpeg clip extraction failed: {result.stderr[-500:]}")


def generate_thumbnail(input_path, output_path, timestamp_seconds=None):
    """Extract a single frame as a JPEG thumbnail.

    If timestamp_seconds is None, extracts from the 5-second mark
    (or 0 if video is shorter).
    """
    if timestamp_seconds is None:
        timestamp_seconds = 5
    cmd = [
        'ffmpeg',
        '-ss', str(timestamp_seconds),
        '-i', input_path,
        '-vframes', '1',
        '-q:v', '2',
        '-y', output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("FFmpeg thumbnail failed: %s", result.stderr)
        raise RuntimeError(f"FFmpeg thumbnail generation failed: {result.stderr[-500:]}")


def probe_metadata(input_path):
    """Get video metadata via ffprobe.

    Returns dict with keys: duration, width, height, codec, audio_codec.
    """
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        input_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("ffprobe failed: %s", result.stderr)
        raise RuntimeError(f"ffprobe failed: {result.stderr[-500:]}")

    data = json.loads(result.stdout)
    metadata = {
        'duration': None,
        'width': None,
        'height': None,
        'codec': None,
        'audio_codec': None,
    }

    # Duration from format
    fmt = data.get('format', {})
    if fmt.get('duration'):
        metadata['duration'] = float(fmt['duration'])

    # Video and audio stream info
    for stream in data.get('streams', []):
        if stream.get('codec_type') == 'video' and metadata['width'] is None:
            metadata['width'] = stream.get('width')
            metadata['height'] = stream.get('height')
            metadata['codec'] = stream.get('codec_name')
        elif stream.get('codec_type') == 'audio' and metadata['audio_codec'] is None:
            metadata['audio_codec'] = stream.get('codec_name')

    return metadata
