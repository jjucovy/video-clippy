from archive.utils.cloudflare import CloudflareStreamAPI
import json

api = CloudflareStreamAPI()

# Show what we're sending
upload_data = {
    "maxDurationSeconds": 7200,
    "requireSignedURLs": False,
    "meta": {"name": "Test Video"}
}

print("Request URL:", f"{api.base_url}/direct_upload")
print("Request headers:", api.headers)
print("Request body:", json.dumps(upload_data, indent=2))
print("\nCreating upload URL...")

result = api.get_resumable_upload_url(metadata={'name': 'Test Video'})
print("\nResponse:", result)
