"""
Comments scraper module.
Handles fetching all comments for YouTube videos with full pagination.
"""

from typing import List, Dict, Optional
from googleapiclient.errors import HttpError


def get_all_comments(youtube, video_id: str) -> List[Dict]:
    """
    Fetch all top-level comments for a video with full pagination.
    
    Args:
        youtube: YouTube API client
        video_id: YouTube video ID
        
    Returns:
        List of comment dictionaries with text, likes, author, and published_at
    """
    comments = []
    next_page_token = None
    
    try:
        while True:
            request = youtube.commentThreads().list(
                part='snippet',
                videoId=video_id,
                maxResults=100,
                pageToken=next_page_token,
                textFormat='plainText'
            )
            response = request.execute()
            
            for item in response.get('items', []):
                top_comment = item['snippet']['topLevelComment']['snippet']
                
                comment_data = {
                    'video_id': video_id,
                    'comment_text': top_comment['textDisplay'],
                    'author_name': top_comment['authorDisplayName'],
                    'like_count': top_comment['likeCount'],
                    'published_at': top_comment['publishedAt']
                }
                comments.append(comment_data)
            
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
        
        return comments
    
    except HttpError as e:
        error_reason = e.error_details[0].get('reason', '') if e.error_details else ''
        # Silently handle all errors
        return []
    
    except Exception as e:
        return []


def get_comment_count(youtube, video_id: str) -> int:
    """
    Get the total comment count for a video without fetching all comments.
    Useful for determining if comments are available.
    
    Args:
        youtube: YouTube API client
        video_id: YouTube video ID
        
    Returns:
        Number of comments or 0 if unavailable
    """
    try:
        request = youtube.videos().list(
            part='statistics',
            id=video_id
        )
        response = request.execute()
        
        if not response.get('items'):
            return 0
        
        return int(response['items'][0].get('statistics', {}).get('commentCount', 0))
    
    except Exception as e:
        return 0
