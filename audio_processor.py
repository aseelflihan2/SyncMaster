import os
from dotenv import load_dotenv
import tempfile
from typing import List, Dict, Optional
import json
import librosa
import numpy as np
from google import genai
from google.genai import types

class AudioProcessor:
    """Handles audio transcription and word-level timestamp extraction using Gemini AI"""
    
    def __init__(self):
        """Initialize the audio processor with Gemini client"""
        self.client = None
        self._initialize_gemini()
    
    def _initialize_gemini(self):
        """Initialize the Gemini client"""
        try:
            # Load environment variables from a .env file if present
            load_dotenv()

            # Obtain API key from environment variables
            api_key = os.getenv("GEMINI_API_KEY")

            if not api_key:
                raise ValueError("GEMINI_API_KEY not found in environment variables. Please set it in a .env file.")

            self.client = genai.Client(api_key=api_key)
        except Exception as e:
            print(f"Warning: Failed to initialize Gemini client: {str(e)}")
            self.client = None
    
    def transcribe_audio(self, audio_file_path: str) -> Optional[str]:
        """
        Transcribe audio file to text using Gemini AI
        
        Args:
            audio_file_path: Path to the audio file
            
        Returns:
            Transcribed text or None if failed
        """
        try:
            if not os.path.exists(audio_file_path):
                raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
            
            if not self.client:
                # Fallback to sample text if Gemini is not available
                return "Please edit this text to match your audio content. Gemini transcription is not available."
            
            # Read audio file as bytes
            with open(audio_file_path, 'rb') as f:
                audio_bytes = f.read()
            
            # Determine MIME type based on file extension
            file_ext = os.path.splitext(audio_file_path)[1].lower()
            mime_type_map = {
                '.mp3': 'audio/mpeg',
                '.wav': 'audio/wav',
                '.m4a': 'audio/mp4',
                '.flac': 'audio/flac',
                '.ogg': 'audio/ogg'
            }
            mime_type = mime_type_map.get(file_ext, 'audio/mpeg')
            
            # Transcribe with Gemini
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Part.from_bytes(
                        data=audio_bytes,
                        mime_type=mime_type,
                    ),
                    "Please transcribe this audio file accurately. Provide only the spoken text without any additional commentary, formatting, or explanations. Just return the pure transcribed text."
                ],
            )
            
            if response and response.text:
                return response.text.strip()
            else:
                return "Please edit this text to match your audio content. Transcription failed."
                
        except Exception as e:
            print(f"Error transcribing audio: {str(e)}")
            return "Please edit this text to match your audio content. An error occurred during transcription."
    
    def get_word_timestamps(self, audio_file_path: str) -> List[Dict]:
        """
        Create word-level timestamps from transcribed text and audio duration
        
        Args:
            audio_file_path: Path to the audio file
            
        Returns:
            List of dictionaries with word, start, and end timestamps
        """
        try:
            if not os.path.exists(audio_file_path):
                raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
            
            # First get the transcription
            transcription = self.transcribe_audio(audio_file_path)
            if not transcription:
                return []
            
            # Get audio duration
            audio_duration = self.get_audio_duration(audio_file_path)
            if audio_duration <= 0:
                return []
            
            # Split transcription into words
            words = transcription.split()
            if not words:
                return []
            
            # Calculate timing for each word
            word_timestamps = []
            total_words = len(words)
            
            for i, word in enumerate(words):
                # Distribute words evenly across the audio duration
                # Leave some silence at the beginning and end
                start_offset = 0.5  # 0.5 seconds at start
                end_offset = 0.5    # 0.5 seconds at end
                usable_duration = audio_duration - start_offset - end_offset
                
                if total_words == 1:
                    start_time = start_offset
                    end_time = audio_duration - end_offset
                else:
                    # Calculate word timing
                    word_duration = usable_duration / total_words
                    start_time = start_offset + (i * word_duration)
                    end_time = start_offset + ((i + 1) * word_duration)
                
                # Add some variation to make it more natural
                if i > 0:
                    # Small gap between words
                    start_time += 0.05
                
                word_data = {
                    'word': word.strip(),
                    'start': round(start_time, 3),
                    'end': round(end_time, 3)
                }
                word_timestamps.append(word_data)
            
            return word_timestamps
            
        except Exception as e:
            print(f"Error creating word timestamps: {str(e)}")
            return []
    
    def get_audio_duration(self, audio_file_path: str) -> float:
        """
        Get the duration of the audio file in seconds
        
        Args:
            audio_file_path: Path to the audio file
            
        Returns:
            Duration in seconds
        """
        try:
            audio_data, sample_rate = librosa.load(audio_file_path)
            duration = len(audio_data) / sample_rate
            return duration
        except Exception as e:
            print(f"Error getting audio duration: {str(e)}")
            return 0.0
    
    def validate_timestamps(self, word_timestamps: List[Dict], audio_duration: float) -> List[Dict]:
        """
        Validate and clean word timestamps
        
        Args:
            word_timestamps: List of word timestamp dictionaries
            audio_duration: Total duration of audio in seconds
            
        Returns:
            Cleaned list of word timestamps
        """
        cleaned_timestamps = []
        
        for word_data in word_timestamps:
            # Ensure start and end times are valid
            start_time = max(0, word_data.get('start', 0))
            end_time = min(audio_duration, word_data.get('end', start_time + 0.1))
            
            # Ensure end time is after start time
            if end_time <= start_time:
                end_time = start_time + 0.1
            
            cleaned_word = {
                'word': word_data.get('word', '').strip(),
                'start': round(start_time, 3),
                'end': round(end_time, 3)
            }
            
            if cleaned_word['word']:
                cleaned_timestamps.append(cleaned_word)
        
        return cleaned_timestamps
    
    def create_sentence_timestamps(self, word_timestamps: List[Dict], max_words_per_line: int = 8) -> List[Dict]:
        """
        Group words into sentences/lines for better video display
        
        Args:
            word_timestamps: List of word timestamp dictionaries
            max_words_per_line: Maximum words per line
            
        Returns:
            List of sentence/line dictionaries with timestamps
        """
        if not word_timestamps:
            return []
        
        sentences = []
        current_sentence = []
        
        for word_data in word_timestamps:
            current_sentence.append(word_data)
            
            # Check if we should end this sentence
            word = word_data.get('word', '')
            if (len(current_sentence) >= max_words_per_line or 
                word.endswith('.') or word.endswith('!') or word.endswith('?')):
                
                if current_sentence:
                    sentence_data = {
                        'text': ' '.join([w.get('word', '') for w in current_sentence]).strip(),
                        'start': current_sentence[0].get('start', 0),
                        'end': current_sentence[-1].get('end', 0),
                        'words': current_sentence.copy()
                    }
                    sentences.append(sentence_data)
                    current_sentence = []
        
        # Add remaining words as final sentence
        if current_sentence:
            sentence_data = {
                'text': ' '.join([w.get('word', '') for w in current_sentence]).strip(),
                'start': current_sentence[0].get('start', 0),
                'end': current_sentence[-1].get('end', 0),
                'words': current_sentence.copy()
            }
            sentences.append(sentence_data)
        
        return sentences
