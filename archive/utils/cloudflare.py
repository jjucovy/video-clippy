import requests
import os
from django.conf import settings
from typing import Optional, Dict, Any

class CloudflareStreamAPI:
    def __init__(self):
        self.account_id = settings.CLOUDFLARE_ACCOUNT_ID
        self.api_token = settings.CLOUDFLARE_API_TOKEN
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/stream"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
        }
    
    def upload_video(self, file_obj, metadata: Dict[str, Any] = None) -> Optional[Dict]:
        """Upload video file to Cloudflare Stream"""
        url = f"{self.base_url}/direct_upload"
        
        # Create direct upload URL
        upload_data = {
            "maxDurationSeconds": 7200,  # 2 hours max
        }
        if metadata:
            upload_data["meta"] = metadata
        
        response = requests.post(
            url,
            headers=self.headers,
            json=upload_data
        )
        
        if response.status_code != 200:
            return None
        
        upload_info = response.json()["result"]
        upload_url = upload_info["uploadURL"]
        
        # Upload the actual file
        files = {"file": file_obj}
        upload_response = requests.post(upload_url, files=files)
        
        if upload_response.status_code != 200:
            return None
        
        return upload_info
    
    def get_direct_upload_url(self, metadata: Dict[str, Any] = None) -> Optional[Dict]:
        """Get a direct upload URL for client-side upload (basic, <200MB)"""
        url = f"{self.base_url}/direct_upload"
        
        upload_data = {
            "maxDurationSeconds": 7200,  # 2 hours max
        }
        if metadata:
            upload_data["meta"] = metadata
        
        response = requests.post(
            url,
            headers=self.headers,
            json=upload_data
        )
        
        if response.status_code == 200:
            return response.json()["result"]
        return None
    
    def get_resumable_upload_url(self, metadata: Dict[str, Any] = None) -> Optional[Dict]:
        """Get a resumable upload URL for large files via tus protocol"""
        url = f"{self.base_url}/direct_upload"

        upload_data = {
            "maxDurationSeconds": 7200,  # 2 hours max
            "requireSignedURLs": False
        }
        if metadata:
            upload_data["meta"] = metadata
        
        response = requests.post(
            url,
            headers=self.headers,
            json=upload_data
        )
        
        if response.status_code == 200:
            result = response.json()["result"]
            # For tus uploads, we need to use the upload URL directly
            return {
                "uploadURL": result["uploadURL"],
                "uid": result["uid"],
                "resumable": True
            }
        return None
    
    def get_video_details(self, video_id: str) -> Optional[Dict]:
        """Get video details from Cloudflare Stream"""
        url = f"{self.base_url}/{video_id}"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            return response.json()["result"]
        return None
    
    def list_videos(self, limit: int = 50, after: str = None) -> Optional[Dict]:
        """List videos in Cloudflare Stream"""
        url = f"{self.base_url}"
        params = {"limit": limit}
        if after:
            params["after"] = after
            
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code == 200:
            return response.json()["result"]
        return None
    
    def enable_downloads(self, video_id: str) -> Optional[Dict]:
        """Enable MP4 downloads for a CF Stream video.

        POST /stream/{id}/downloads creates a downloadable MP4.
        Returns the download info dict or None on failure.
        """
        url = f"{self.base_url}/{video_id}/downloads"
        response = requests.post(url, headers=self.headers)

        if response.status_code == 200:
            return response.json().get("result", {})
        return None

    def get_download_url(self, video_id: str) -> Optional[str]:
        """Get the MP4 download URL for a CF Stream video.

        Returns the URL string if downloads are enabled and ready, else None.
        """
        url = f"{self.base_url}/{video_id}/downloads"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            result = response.json().get("result", {})
            default = result.get("default", {})
            if default.get("status") == "ready":
                return default.get("url")
        return None

    def download_video(self, video_id: str, output_path: str, timeout: int = 600) -> None:
        """Enable downloads, poll for readiness, and download the MP4.

        Args:
            video_id: CF Stream video identifier
            output_path: Local file path to write the downloaded MP4
            timeout: Max seconds to wait for download URL to become ready

        Raises on failure.
        """
        import time

        # Enable downloads — check for failure
        result = self.enable_downloads(video_id)
        if result is None:
            # May already be enabled (409) — try polling anyway
            pass

        # Poll for download URL
        start = time.time()
        download_url = None
        while time.time() - start < timeout:
            download_url = self.get_download_url(video_id)
            if download_url:
                break
            time.sleep(5)

        if not download_url:
            raise TimeoutError(
                f"Download URL for video {video_id} not ready after {timeout}s"
            )

        # Stream download to file (1MB chunks for large files)
        response = requests.get(download_url, stream=True, timeout=(30, 300))
        response.raise_for_status()

        expected_size = int(response.headers.get('Content-Length', 0))
        bytes_written = 0
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
                bytes_written += len(chunk)

        if expected_size and bytes_written != expected_size:
            raise IOError(
                f"Download incomplete: got {bytes_written} bytes, "
                f"expected {expected_size}"
            )

    def generate_embed_code(self, video_id: str, start_time: int = None, autoplay: bool = False, poster_url: str = None) -> str:
        """Generate HTML embed code for Cloudflare Stream video"""
        from urllib.parse import quote
        embed_url = f"https://iframe.videodelivery.net/{video_id}"
        
        params = []
        
        # Start building the parameter string part by part
        base_params = ["defaultTextTrack="]
        if poster_url:
            base_params.append(f"poster={quote(poster_url)}")
        else:
            base_params.append("poster=") # Keep it empty as before
            
        if start_time:
            base_params.append(f"startTime={start_time}s")
        
        # Join the base params into one string, as it was in the original implementation
        params.append("&".join(base_params))

        if autoplay:
            params.append("autoplay=true")
        
        if params:
            embed_url += "?" + "&".join(params)
        
        embed_code = f'''
        <iframe
            src="{embed_url}"
            style="border: none; position: absolute; top: 0; height: 100%; width: 100%;"
            allow="accelerometer; gyroscope; autoplay; encrypted-media; picture-in-picture;"
            allowfullscreen="true">
        </iframe>
        '''
        
        return embed_code.strip()