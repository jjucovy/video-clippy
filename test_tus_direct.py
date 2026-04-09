from archive.utils.cloudflare import CloudflareStreamAPI

api = CloudflareStreamAPI()
result = api.get_direct_upload_url(metadata={'name': 'Test Video'})
if result:
    print("Direct upload URL:", result['uploadURL'])
    print("\nTesting TUS handshake...")
    import subprocess
    cmd = [
        'curl', '-X', 'POST', result['uploadURL'],
        '-H', 'Tus-Resumable: 1.0.0',
        '-H', 'Upload-Length: 1000000'
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    print("Output:", proc.stdout + proc.stderr)
else:
    print("Failed to get upload URL")
