"""
YouTube Data API v3 integration module.
Handles channel data, video listing, and metadata extraction.
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import isodate


def get_youtube_client(api_key: str):
    """Initialize YouTube Data API v3 client."""
    return build('youtube', 'v3', developerKey=api_key)


def get_uploads_playlist(youtube, channel_id: str) -> Optional[str]:
    """
    Get the uploads playlist ID for a given channel.
    
    Args:
        youtube: YouTube API client
        channel_id: YouTube channel ID
        
    Returns:
        Uploads playlist ID or None if error
    """
    try:
        request = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        )
        response = request.execute()
        
        if not response.get('items'):
            print(f"Channel {channel_id} not found")
            return None
            
        uploads_playlist_id = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        return uploads_playlist_id
    
    except HttpError as e:
        print(f"HTTP error fetching uploads playlist for {channel_id}: {e}")
        return None
    except Exception as e:
        print(f"Error fetching uploads playlist for {channel_id}: {e}")
        return None


def get_recent_videos(youtube, playlist_id: str, years: int = 2) -> List[str]:
    """
    Get all video IDs from a playlist published in the last N years.
    Handles pagination correctly.
    
    Args:
        youtube: YouTube API client
        playlist_id: Uploads playlist ID
        years: Number of years to look back (default 2)
        
    Returns:
        List of video IDs
    """
    video_ids = []
    cutoff_date = datetime.now() - timedelta(days=years * 365)
    next_page_token = None
    
    try:
        while True:
            request = youtube.playlistItems().list(
                part='contentDetails,snippet',
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token
            )
            response = request.execute()
            
            for item in response.get('items', []):
                published_at_str = item['snippet']['publishedAt']
                published_at = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
                
                # Stop if video is older than cutoff
                if published_at < cutoff_date:
                    return video_ids
                
                video_id = item['contentDetails']['videoId']
                video_ids.append(video_id)
            
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
                
        return video_ids
    
    except HttpError as e:
        print(f"HTTP error fetching videos from playlist {playlist_id}: {e}")
        return video_ids
    except Exception as e:
        print(f"Error fetching videos from playlist {playlist_id}: {e}")
        return video_ids


def get_video_metadata(youtube, video_id: str) -> Optional[Dict]:
    """
    Get comprehensive metadata for a video.
    
    Args:
        youtube: YouTube API client
        video_id: YouTube video ID
        
    Returns:
        Dictionary with video metadata or None if error
    """
    try:
        request = youtube.videos().list(
            part='snippet,contentDetails,statistics',
            id=video_id
        )
        response = request.execute()
        
        if not response.get('items'):
            print(f"Video {video_id} not found")
            return None
        
        item = response['items'][0]
        snippet = item['snippet']
        content_details = item['contentDetails']
        statistics = item.get('statistics', {})
        
        # Parse ISO 8601 duration
        duration_iso = content_details['duration']
        
        metadata = {
            'video_id': video_id,
            'title': snippet['title'],
            'published_at': snippet['publishedAt'],
            'duration': duration_iso,
            'viewCount': int(statistics.get('viewCount', 0)),
            'likeCount': int(statistics.get('likeCount', 0)),
            'commentCount': int(statistics.get('commentCount', 0))
        }
        
        return metadata
    
    except HttpError as e:
        print(f"HTTP error fetching metadata for {video_id}: {e}")
        return None
    except Exception as e:
        print(f"Error fetching metadata for {video_id}: {e}")
        return None


def get_video_metadata_batch(youtube, video_ids: List[str]) -> List[Dict]:
    """
    Get metadata for multiple videos in batches (up to 50 at a time).
    More efficient than individual requests.
    
    Args:
        youtube: YouTube API client
        video_ids: List of video IDs
        
    Returns:
        List of metadata dictionaries
    """
    metadata_list = []
    batch_size = 50
    
    for i in range(0, len(video_ids), batch_size):
        batch = video_ids[i:i + batch_size]
        
        try:
            request = youtube.videos().list(
                part='snippet,contentDetails,statistics',
                id=','.join(batch)
            )
            response = request.execute()
            
            for item in response.get('items', []):
                snippet = item['snippet']
                content_details = item['contentDetails']
                statistics = item.get('statistics', {})
                
                metadata = {
                    'video_id': item['id'],
                    'title': snippet['title'],
                    'published_at': snippet['publishedAt'],
                    'duration': content_details['duration'],
                    'viewCount': int(statistics.get('viewCount', 0)),
                    'likeCount': int(statistics.get('likeCount', 0)),
                    'commentCount': int(statistics.get('commentCount', 0))
                }
                metadata_list.append(metadata)
        
        except HttpError as e:
            print(f"HTTP error fetching batch metadata: {e}")
            # Try individual requests for this batch
            for video_id in batch:
                meta = get_video_metadata(youtube, video_id)
                if meta:
                    metadata_list.append(meta)
        except Exception as e:
            print(f"Error fetching batch metadata: {e}")
    
    return metadata_list
