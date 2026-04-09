from archive.models import Video

video = Video.objects.get(pk='e9c01f8e-f69d-46fc-9e3d-c55bf26282f1')
print(f"Video: {video.title}")
print(f"Status: {video.status}")
print(f"Stream ID: {video.cloudflare_stream_id}")

from archive.utils.cloudflare import CloudflareStreamAPI
api = CloudflareStreamAPI()
details = api.get_video_details(video.cloudflare_stream_id)

if details:
    print("\nCloudflare response:")
    import json
    print(json.dumps(details, indent=2))
    print(f"\nStatus state: {details.get('status', {}).get('state')}")
else:
    print("No details returned from Cloudflare")
