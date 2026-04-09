from archive.models import Video

video = Video.objects.get(pk='9abb6aa5-4d82-4869-9a0e-db966ed6bea1')
print(f"ID: {video.id}")
print(f"Title: {video.title}")
print(f"Status: {video.status}")
print(f"Stream ID: {video.cloudflare_stream_id}")
print(f"TUS Upload URL: {video.tus_upload_url}")
print(f"Upload offset: {video.upload_offset}")
print(f"Upload total: {video.upload_total}")
print(f"Playback URL: {video.cloudflare_playback_url}")
print(f"Created at: {video.created_at}")
