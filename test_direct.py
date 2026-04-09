from archive.utils.cloudflare import CloudflareStreamAPI

api = CloudflareStreamAPI()
result = api.get_direct_upload_url(metadata={'name': 'Test Video'})
print("Direct upload result:", result)
print("\nTesting with small POST...")
import subprocess
if result:
    # Create a tiny test file
    with open('/tmp/test.mp4', 'wb') as f:
        f.write(b'test data')
    
    cmd = [
        'curl', '-X', 'POST', result['uploadURL'],
        '-F', 'file=@/tmp/test.mp4'
    ]
    subprocess.run(cmd)
