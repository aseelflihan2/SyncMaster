import os
import mimetypes
import tempfile
from pathlib import Path
from typing import Optional, List, Dict
import librosa
import numpy as np

def format_timestamp(seconds: float) -> str:
    """
    Format seconds into MM:SS.mmm format
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted timestamp string
    """
    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60
    return f"{minutes:02d}:{remaining_seconds:06.3f}"

def validate_audio_file(file_path: str) -> bool:
    """
    Validate if the file is a supported audio format
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        True if valid, False otherwise
    """
    try:
        if not os.path.exists(file_path):
            return False
        
        # Check file extension
        supported_extensions = ['.mp3', '.wav', '.m4a', '.flac', '.ogg']
        file_extension = Path(file_path).suffix.lower()
        
        if file_extension not in supported_extensions:
            return False
        
        # Check MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type and not mime_type.startswith('audio/'):
            return False
        
        # Try to load with librosa to verify it's a valid audio file
        try:
            librosa.load(file_path, duration=1.0)  # Load just 1 second for validation
            return True
        except:
            return False
            
    except Exception:
        return False

def get_audio_info(file_path: str) -> Dict:
    """
    Get information about the audio file
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Dictionary with audio information
    """
    try:
        # Load audio file
        y, sr = librosa.load(file_path)
        
        duration = len(y) / sr
        
        return {
            'duration': duration,
            'sample_rate': sr,
            'channels': 1 if len(y.shape) == 1 else y.shape[0],
            'file_size': os.path.getsize(file_path),
            'format': Path(file_path).suffix.lower()
        }
        
    except Exception as e:
        return {
            'error': str(e),
            'duration': 0,
            'sample_rate': 0,
            'channels': 0,
            'file_size': 0,
            'format': 'unknown'
        }

def clean_text(text: str) -> str:
    """
    Clean and normalize text for better processing
    
    Args:
        text: Input text
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    # Remove common transcription artifacts
    text = text.replace('[Music]', '')
    text = text.replace('[Applause]', '')
    text = text.replace('[Laughter]', '')
    text = text.replace('(Music)', '')
    text = text.replace('(Applause)', '')
    text = text.replace('(Laughter)', '')
    
    # Clean up extra spaces
    text = ' '.join(text.split())
    
    return text.strip()

def split_text_into_chunks(text: str, max_chars_per_chunk: int = 100) -> List[str]:
    """
    Split text into chunks suitable for video display
    
    Args:
        text: Input text
        max_chars_per_chunk: Maximum characters per chunk
        
    Returns:
        List of text chunks
    """
    if not text:
        return []
    
    words = text.split()
    chunks = []
    current_chunk = []
    current_length = 0
    
    for word in words:
        word_length = len(word) + 1  # +1 for space
        
        if current_length + word_length > max_chars_per_chunk and current_chunk:
            # Add current chunk and start new one
            chunks.append(' '.join(current_chunk))
            current_chunk = [word]
            current_length = len(word)
        else:
            current_chunk.append(word)
            current_length += word_length
    
    # Add final chunk
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

def convert_color_hex_to_rgb(hex_color: str) -> tuple:
    """
    Convert hex color to RGB tuple
    
    Args:
        hex_color: Hex color string (e.g., '#FF0000')
        
    Returns:
        RGB tuple (r, g, b)
    """
    hex_color = hex_color.lstrip('#')
    
    if len(hex_color) != 6:
        return (255, 255, 255)  # Default to white
    
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b)
    except ValueError:
        return (255, 255, 255)  # Default to white

def convert_rgb_to_hex(r: int, g: int, b: int) -> str:
    """
    Convert RGB values to hex color string
    
    Args:
        r, g, b: RGB color values (0-255)
        
    Returns:
        Hex color string
    """
    return f"#{r:02x}{g:02x}{b:02x}"

def estimate_video_file_size(duration: float, resolution: tuple = (1280, 720), 
                           bitrate_kbps: int = 2000) -> int:
    """
    Estimate the file size of a video based on duration and quality
    
    Args:
        duration: Video duration in seconds
        resolution: Video resolution tuple (width, height)
        bitrate_kbps: Video bitrate in kbps
        
    Returns:
        Estimated file size in bytes
    """
    # Simple estimation: bitrate * duration / 8 (to convert bits to bytes)
    estimated_size = (bitrate_kbps * 1000 * duration) / 8
    return int(estimated_size)

def create_safe_filename(filename: str) -> str:
    """
    Create a safe filename by removing/replacing invalid characters
    
    Args:
        filename: Original filename
        
    Returns:
        Safe filename
    """
    import re
    
    # Remove or replace invalid characters
    safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove extra underscores and spaces
    safe_filename = re.sub(r'[_\s]+', '_', safe_filename)
    
    # Trim leading/trailing underscores
    safe_filename = safe_filename.strip('_')
    
    # Ensure filename is not empty
    if not safe_filename:
        safe_filename = "output"
    
    return safe_filename

def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format
    
    Args:
        size_bytes: File size in bytes
        
    Returns:
        Formatted file size string
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = int(np.floor(np.log(size_bytes) / np.log(1024)))
    p = np.power(1024, i)
    s = round(size_bytes / p, 2)
    
    return f"{s} {size_names[i]}"

def validate_word_timestamps(word_timestamps: List[Dict]) -> List[Dict]:
    """
    Validate and clean word timestamps data
    
    Args:
        word_timestamps: List of word timestamp dictionaries
        
    Returns:
        Cleaned and validated word timestamps
    """
    validated_timestamps = []
    
    for word_data in word_timestamps:
        # Ensure required fields exist
        if not isinstance(word_data, dict):
            continue
        
        word = word_data.get('word', '').strip()
        start = word_data.get('start', 0)
        end = word_data.get('end', 0)
        
        # Skip empty words
        if not word:
            continue
        
        # Ensure numeric timestamps
        try:
            start = float(start)
            end = float(end)
        except (ValueError, TypeError):
            continue
        
        # Ensure logical timestamp order
        if start < 0:
            start = 0
        if end <= start:
            end = start + 0.1  # Minimum duration
        
        validated_timestamps.append({
            'word': word,
            'start': round(start, 3),
            'end': round(end, 3)
        })
    
    return validated_timestamps

def merge_overlapping_timestamps(word_timestamps: List[Dict], 
                               overlap_threshold: float = 0.05) -> List[Dict]:
    """
    Merge overlapping or very close word timestamps
    
    Args:
        word_timestamps: List of word timestamp dictionaries
        overlap_threshold: Threshold for merging close timestamps (seconds)
        
    Returns:
        List with merged timestamps
    """
    if not word_timestamps:
        return []
    
    merged_timestamps = []
    current_group = [word_timestamps[0]]
    
    for word_data in word_timestamps[1:]:
        last_end = current_group[-1]['end']
        current_start = word_data['start']
        
        # Check if words should be merged
        if current_start - last_end <= overlap_threshold:
            current_group.append(word_data)
        else:
            # Merge current group and start new one
            if len(current_group) == 1:
                merged_timestamps.append(current_group[0])
            else:
                # Merge multiple words
                merged_word = {
                    'word': ' '.join([w['word'] for w in current_group]),
                    'start': current_group[0]['start'],
                    'end': current_group[-1]['end']
                }
                merged_timestamps.append(merged_word)
            
            current_group = [word_data]
    
    # Handle final group
    if len(current_group) == 1:
        merged_timestamps.append(current_group[0])
    else:
        merged_word = {
            'word': ' '.join([w['word'] for w in current_group]),
            'start': current_group[0]['start'],
            'end': current_group[-1]['end']
        }
        merged_timestamps.append(merged_word)
    
    return merged_timestamps
