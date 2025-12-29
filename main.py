"""
Main orchestration script for YouTube channel scraping pipeline.
Coordinates video discovery, metadata extraction, transcript fetching, and comment scraping.
"""

import os
import json
import time
from typing import List, Set
from dotenv import load_dotenv
from tqdm import tqdm

from youtube_api import (
    get_youtube_client,
    get_uploads_playlist,
    get_recent_videos,
    get_video_metadata_batch
)
from comments import get_all_comments
from transcripts import get_transcript_with_fallback, get_transcript


# Load environment variables
load_dotenv()


def load_processed_videos(output_dir: str, filename: str) -> Set[str]:
    """
    Load already processed video IDs from JSONL file for idempotency.
    
    Args:
        output_dir: Output directory
        filename: JSONL filename
        
    Returns:
        Set of video IDs already processed
    """
    filepath = os.path.join(output_dir, filename)
    video_ids = set()
    
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    video_ids.add(data['video_id'])
                except:
                    pass
    
    return video_ids


def append_jsonl(output_dir: str, filename: str, data: dict):
    """
    Append a record to a JSONL file.
    
    Args:
        output_dir: Output directory
        filename: JSONL filename
        data: Dictionary to append
    """
    filepath = os.path.join(output_dir, filename)
    os.makedirs(output_dir, exist_ok=True)
    
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False) + '\n')


def append_jsonl_batch(output_dir: str, filename: str, data_list: List[dict]):
    """
    Append multiple records to a JSONL file.
    
    Args:
        output_dir: Output directory
        filename: JSONL filename
        data_list: List of dictionaries to append
    """
    if not data_list:
        return
    
    filepath = os.path.join(output_dir, filename)
    os.makedirs(output_dir, exist_ok=True)
    
    with open(filepath, 'a', encoding='utf-8') as f:
        for data in data_list:
            f.write(json.dumps(data, ensure_ascii=False) + '\n')


def scrape_channel(
    channel_id: str,
    api_key: str,
    output_dir: str = 'output',
    years: int = 2,
    skip_transcripts: bool = False,
    skip_comments: bool = False,
    skip_whisper: bool = True
):
    """
    Scrape all videos from a YouTube channel from the last N years.
    
    Args:
        channel_id: YouTube channel ID
        api_key: YouTube Data API v3 key
        output_dir: Directory to save output files
        years: Number of years to look back
        skip_transcripts: If True, skip transcript extraction
        skip_comments: If True, skip comment extraction
    """
    print(f"\n{'='*60}")
    print(f"Scraping channel: {channel_id}")
    print(f"{'='*60}\n")
    
    # Initialize YouTube client
    youtube = get_youtube_client(api_key)
    
    # Get uploads playlist
    print("Fetching uploads playlist...")
    uploads_playlist = get_uploads_playlist(youtube, channel_id)
    if not uploads_playlist:

        return
    
    # Get recent videos
    print(f"Fetching videos from last {years} years...")
    video_ids = get_recent_videos(youtube, uploads_playlist, years)
    print(f"Found {len(video_ids)} videos")
    
    if not video_ids:
        return
    
    # Load already processed videos for idempotency
    processed_metadata = load_processed_videos(output_dir, 'videos.jsonl')
    processed_transcripts = load_processed_videos(output_dir, 'transcripts.jsonl')
    processed_comments = load_processed_videos(output_dir, 'comments.jsonl')
    
    # Filter videos that need metadata
    videos_needing_metadata = [vid for vid in video_ids if vid not in processed_metadata]
    
    if videos_needing_metadata:
        print(f"\nFetching metadata for {len(videos_needing_metadata)} videos...")
        metadata_list = get_video_metadata_batch(youtube, videos_needing_metadata)
        
        # Save metadata
        append_jsonl_batch(output_dir, 'videos.jsonl', metadata_list)
        print(f"Saved metadata for {len(metadata_list)} videos")
    else:
        print("All video metadata already processed")
    
    # Extract transcripts
    if not skip_transcripts:
        videos_needing_transcripts = [vid for vid in video_ids if vid not in processed_transcripts]
        
        if videos_needing_transcripts:
            print(f"\nExtracting transcripts for {len(videos_needing_transcripts)} videos...")
            for video_id in tqdm(videos_needing_transcripts, desc="Transcripts"):
                transcript = get_transcript_with_fallback(video_id, force_whisper=False) if not skip_whisper else get_transcript(video_id)
                if transcript:
                    append_jsonl(output_dir, 'transcripts.jsonl', transcript)
                else:
                    # Record failed attempt to avoid retrying
                    append_jsonl(output_dir, 'transcripts.jsonl', {
                        'video_id': video_id,
                        'transcript_source': 'failed',
                        'segments': []
                    })
                # Rate limiting: wait between requests to avoid 429 errors
                time.sleep(1.5)
        else:
            print("\nAll transcripts already processed")
    
    # Scrape comments
    if not skip_comments:
        videos_needing_comments = [vid for vid in video_ids if vid not in processed_comments]
        
        if videos_needing_comments:
            print(f"\nScraping comments for {len(videos_needing_comments)} videos...")
            for video_id in tqdm(videos_needing_comments, desc="Comments"):
                comments = get_all_comments(youtube, video_id)
                
                if comments:
                    append_jsonl_batch(output_dir, 'comments.jsonl', comments)
                else:
                    # Record that we attempted this video even if no comments
                    append_jsonl(output_dir, 'comments.jsonl', {
                        'video_id': video_id,
                        'comment_text': None,
                        'author_name': None,
                        'like_count': 0,
                        'published_at': None
                    })
                # Rate limiting: wait between requests
                time.sleep(0.5)
        else:
            print("\nAll comments already processed")
    
    print(f"\n{'='*60}")
    print(f"Completed scraping channel: {channel_id}")
    print(f"{'='*60}\n")


def scrape_channels(
    channel_ids: List[str],
    api_key: str,
    output_dir: str = 'output',
    years: int = 2,
    skip_transcripts: bool = False,
    skip_comments: bool = False,
    skip_whisper: bool = True
):
    """
    Scrape multiple YouTube channels.
    
    Args:
        channel_ids: List of YouTube channel IDs
        api_key: YouTube Data API v3 key
        output_dir: Directory to save output files
        years: Number of years to look back
        skip_transcripts: If True, skip transcript extraction
        skip_comments: If True, skip comment extraction
        skip_whisper: If True, skip Whisper fallback (only use YouTube captions)
    """
    for i, channel_id in enumerate(channel_ids, 1):
        print(f"\nProcessing channel {i}/{len(channel_ids)}")
        try:
            scrape_channel(
                channel_id,
                api_key,
                output_dir,
                years,
                skip_transcripts,
                skip_comments,
                skip_whisper
            )
        except Exception as e:
            continue


def main():
    """
    Main entry point.
    """
    # Get API key from environment
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
        print("Error: YOUTUBE_API_KEY not found in environment")
        print("Please create a .env file with your API key")
        return
    
    # All 8 channels for metadata and comments collection
    channel_ids = [
        'UCyLqyEa45kWaSZlpvJvKhHA',  # Hautemess Tom
        'UCc95c_6uMb1VyFEJjgydHRA',  # Tashira Halyard (Politics & Fashion)
        'UCD9VnTKTGliNFiPTBfQUBYw',  # Heylulaa (J Snyk - may not be correct)
        # 'Livvmarkley',              # Not found - may need different search term
        'UColKM5Unut13hF9_e41RGkw',  # alexonabudget (Alex Petrakieva)
        'UCMjoPHi64Ofikn-udtEra4w',  # stylecrusader (STYLE CRUSADER)
        'UCu0V4K1jf8cISkIzpi77p9Q',  # dermangelo (DermAngelo)
        'UCquUgphHkwCF_d0qBLrfAdA',  # olenabeley (Olena Beley)
    ]
    
    if not channel_ids:
        print("No channel IDs specified.")
        print("Edit main.py and add channel IDs to the channel_ids list")
        return
    
    # Configuration
    output_dir = 'output'
    years = 2
    
    # Run scraper with rate limiting enabled
    scrape_channels(
        channel_ids=channel_ids,
        api_key=api_key,
        output_dir=output_dir,
        years=years,
        skip_transcripts=True,       # Skip transcripts due to rate limit
        skip_comments=False,         # Collect comments
        skip_whisper=True
    )
    
    print("\n✓ Pipeline complete!")
    print(f"Output files saved to: {output_dir}/")
    print("  - videos.jsonl")
    print("  - transcripts.jsonl")
    print("  - comments.jsonl")


if __name__ == '__main__':
    main()
