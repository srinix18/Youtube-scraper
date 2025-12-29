"""
Transcript extraction module.
Attempts to fetch captions using youtube-transcript-api.
Falls back to Whisper transcription if captions are unavailable.
"""

import os
import tempfile
import time
from typing import Dict, List, Optional
from youtube_transcript_api import YouTubeTranscriptApi
try:
    from youtube_transcript_api._errors import (
        TranscriptsDisabled,
        NoTranscriptFound,
        VideoUnavailable,
        TooManyRequests
    )
except ImportError:
    # TooManyRequests may not exist in older versions
    from youtube_transcript_api._errors import (
        TranscriptsDisabled,
        NoTranscriptFound,
        VideoUnavailable
    )
    TooManyRequests = Exception
import yt_dlp
import whisper
import torch


# Load Whisper model lazily
_whisper_model = None


def get_whisper_model(model_name: str = "base"):
    """
    Get or initialize Whisper model (lazy loading).
    
    Args:
        model_name: Whisper model size (tiny, base, small, medium, large)
        
    Returns:
        Whisper model instance
    """
    global _whisper_model
    if _whisper_model is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _whisper_model = whisper.load_model(model_name, device=device)
    return _whisper_model


def get_transcript(video_id: str) -> Optional[Dict]:
    """
    Attempt to fetch transcript using YouTube captions.
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        Dictionary with transcript data and source, or None if unavailable
    """
    try:
        # Try to get transcript (prioritize English, but accept any language)
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Try to find English transcript first
        try:
            transcript = transcript_list.find_transcript(['en'])
        except:
            # Fall back to any available transcript
            transcript = transcript_list.find_generated_transcript(['en'])
        
        segments = transcript.fetch()
        
        # Format segments
        formatted_segments = []
        for seg in segments:
            formatted_segments.append({
                'start': seg['start'],
                'duration': seg['duration'],
                'text': seg['text']
            })
        
        return {
            'video_id': video_id,
            'transcript_source': 'youtube_captions',
            'segments': formatted_segments
        }
    
    except TranscriptsDisabled:
        return None
    except NoTranscriptFound:
        return None
    except VideoUnavailable:
        return None
    except TooManyRequests:
        time.sleep(60)
        return None
    except Exception as e:
        if '429' in str(e) or 'Too Many Requests' in str(e):
            time.sleep(60)
        return None


def download_audio(video_id: str, output_dir: str) -> Optional[str]:
    """
    Download audio from YouTube video using yt-dlp.
    
    Args:
        video_id: YouTube video ID
        output_dir: Directory to save audio file
        
    Returns:
        Path to downloaded audio file or None if error
    """
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    output_path = os.path.join(output_dir, f"{video_id}.mp3")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(output_dir, f"{video_id}.%(ext)s"),
        'quiet': True,
        'no_warnings': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        if os.path.exists(output_path):
            return output_path
        else:
            print(f"Audio file not found after download: {output_path}")
            return None
    
    except Exception as e:
        return None


def whisper_transcribe(video_id: str, audio_path: Optional[str] = None, 
                       model_name: str = "base") -> Optional[Dict]:
    """
    Transcribe video using Whisper.
    
    Args:
        video_id: YouTube video ID
        audio_path: Path to audio file (if None, will download)
        model_name: Whisper model size
        
    Returns:
        Dictionary with transcript data and source, or None if error
    """
    temp_audio = False
    
    try:
        # Download audio if not provided
        if audio_path is None:
            temp_dir = tempfile.mkdtemp()
            audio_path = download_audio(video_id, temp_dir)
            temp_audio = True
            
            if audio_path is None:
                return None
        
        # Load Whisper model
        model = get_whisper_model(model_name)
        
        # Transcribe

        result = model.transcribe(audio_path, verbose=False)
        
        # Format segments
        formatted_segments = []
        for seg in result['segments']:
            formatted_segments.append({
                'start': seg['start'],
                'duration': seg['end'] - seg['start'],
                'text': seg['text'].strip()
            })
        
        return {
            'video_id': video_id,
            'transcript_source': 'whisper',
            'language': result.get('language', 'unknown'),
            'segments': formatted_segments
        }
    
    except Exception as e:
        return None
    
    finally:
        # Clean up temporary audio file
        if temp_audio and audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                # Try to remove temp directory
                temp_dir = os.path.dirname(audio_path)
                if os.path.exists(temp_dir):
                    os.rmdir(temp_dir)
            except:
                pass


def get_transcript_with_fallback(video_id: str, force_whisper: bool = False) -> Optional[Dict]:
    """
    Get transcript with automatic fallback to Whisper if captions unavailable.
    
    Args:
        video_id: YouTube video ID
        force_whisper: If True, skip caption check and use Whisper directly
        
    Returns:
        Dictionary with transcript data or None if all methods fail
    """
    # Try YouTube captions first
    if not force_whisper:
        transcript = get_transcript(video_id)
        if transcript:
            return transcript

    
    # Fallback to Whisper
    return whisper_transcribe(video_id)
