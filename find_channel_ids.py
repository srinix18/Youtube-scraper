"""
Helper script to find YouTube channel IDs from channel names/handles.
"""

import os
from dotenv import load_dotenv
from youtube_api import get_youtube_client
from googleapiclient.errors import HttpError

load_dotenv()


def search_channel_by_name(youtube, channel_name: str):
    """
    Search for a channel by name and return the channel ID.
    
    Args:
        youtube: YouTube API client
        channel_name: Channel name or handle
        
    Returns:
        Channel ID or None if not found
    """
    try:
        # Try searching by channel name
        request = youtube.search().list(
            part='snippet',
            q=channel_name,
            type='channel',
            maxResults=5
        )
        response = request.execute()
        
        if response.get('items'):
            print(f"\n'{channel_name}' - Found {len(response['items'])} results:")
            for i, item in enumerate(response['items'], 1):
                channel_id = item['snippet']['channelId']
                channel_title = item['snippet']['title']
                description = item['snippet']['description'][:100] + '...' if len(item['snippet']['description']) > 100 else item['snippet']['description']
                
                print(f"  {i}. {channel_title}")
                print(f"     ID: {channel_id}")
                print(f"     Description: {description}")
                print()
            
            return response['items'][0]['snippet']['channelId']
        else:
            print(f"No results found for '{channel_name}'")
            return None
    
    except HttpError as e:
        print(f"Error searching for '{channel_name}': {e}")
        return None


def get_channel_id_by_username(youtube, username: str):
    """
    Get channel ID from custom username (legacy method).
    
    Args:
        youtube: YouTube API client
        username: YouTube username
        
    Returns:
        Channel ID or None if not found
    """
    try:
        request = youtube.channels().list(
            part='id',
            forUsername=username
        )
        response = request.execute()
        
        if response.get('items'):
            return response['items'][0]['id']
        return None
    
    except HttpError:
        return None


def main():
    """Find channel IDs for the provided channel names."""
    
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
        print("Error: YOUTUBE_API_KEY not found in .env file")
        return
    
    youtube = get_youtube_client(api_key)
    
    # Channel names provided by user
    channel_names = [
        'Tashira Halyard',
        'Hautemess Tom',
        'Heylulaa',
        'Livvmarkley',
        'alexonabudget',  # Alex Petrakieva
        'stylecrusader',  # Jennifer
        'dermangelo',
        'olenabeley'
    ]
    
    print("="*70)
    print("Searching for YouTube Channel IDs")
    print("="*70)
    
    channel_ids = []
    
    for channel_name in channel_names:
        channel_id = search_channel_by_name(youtube, channel_name)
        if channel_id:
            channel_ids.append(channel_id)
    
    print("\n" + "="*70)
    print("SUMMARY - Copy these IDs to main.py:")
    print("="*70)
    print("\nchannel_ids = [")
    for channel_id in channel_ids:
        print(f"    '{channel_id}',")
    print("]")
    print()


if __name__ == '__main__':
    main()
