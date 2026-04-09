from archive.utils.cloudflare import CloudflareStreamAPI

api = CloudflareStreamAPI()
result = api.get_resumable_upload_url(metadata={'name': 'Test Video'})
print("Result:", result)
print("Testing upload URL with curl...")
import subprocess
if result:
    cmd = [
        'curl', '-X', 'POST', result['uploadURL'],
        '-H', 'Tus-Resumable: 1.0.0',
        '-H', 'Upload-Length: 1000000',
        '-v'
    ]
    subprocess.run(cmd)
