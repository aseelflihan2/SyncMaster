from mutagen.mp3 import MP3
from mutagen.id3 import ID3, SYLT, USLT, Encoding
import os
import tempfile
import shutil
import subprocess
from typing import List, Dict, Tuple

# --- Helper function to check for ffmpeg ---
def is_ffmpeg_available():
    """Check if ffmpeg is installed and accessible in the system's PATH."""
    return shutil.which("ffmpeg") is not None

class MP3Embedder:
    """Handles embedding SYLT synchronized lyrics into MP3 files with robust error handling."""
    
    def __init__(self):
        """Initialize the MP3 embedder."""
        self.temp_dir = "/tmp/audio_sync"
        os.makedirs(self.temp_dir, exist_ok=True)

        self.ffmpeg_available = is_ffmpeg_available()

    def embed_sylt_lyrics(self, audio_path: str, word_timestamps: List[Dict], 
                         text: str, output_filename: str) -> Tuple[str, List[str]]:
        """
        Embeds SYLT synchronized lyrics into an MP3 file and returns logs.
        
        Returns:
            A tuple containing:
            - The path to the output MP3 file.
            - A list of log messages detailing the process.
        """
        log_messages = []
        def log_and_print(message):
            log_messages.append(message)
            print(f"MP3_EMBEDDER: {message}")
        log_and_print(f"--- MP3Embedder initialized. ffmpeg available: {self.ffmpeg_available} ---")
        log_and_print(f"--- Starting SYLT embedding for: {os.path.basename(audio_path)} ---")
        output_path = os.path.join(self.temp_dir, output_filename)
        try:
            # --- Step 1: Ensure the file is in MP3 format ---
            if not audio_path.lower().endswith('.mp3'):
                if self.ffmpeg_available:
                    log_and_print(f"'{os.path.basename(audio_path)}' is not an MP3. Converting with ffmpeg...")
                    try:
                        subprocess.run(
                            ['ffmpeg', '-i', audio_path, '-codec:a', 'libmp3lame', '-q:a', '2', output_path],
                            check=True, capture_output=True, text=True
                        )
                        log_and_print("--- ffmpeg conversion successful. ---")
                    except subprocess.CalledProcessError as e:
                        log_and_print("--- ERROR: ffmpeg conversion failed. ---")
                        log_and_print(f"--- ffmpeg stderr: {e.stderr} ---")
                        log_and_print("--- Fallback: Copying original file without conversion. ---")
                        shutil.copy2(audio_path, output_path)
                else:
                    log_and_print("--- WARNING: ffmpeg is not available. Cannot convert non-MP3 file. Copying directly. ---")
                    shutil.copy2(audio_path, output_path)
            else:
                log_and_print("--- Audio is already MP3. Copying to temporary location. ---")
                shutil.copy2(audio_path, output_path)

            # --- Step 2: Create SYLT data ---
            log_and_print("--- Creating SYLT data from timestamps... ---")
            sylt_data = self._create_sylt_data(word_timestamps)
            if not sylt_data:
                log_and_print("--- WARNING: No SYLT data could be created. Skipping embedding. ---")
                return output_path, log_messages

            log_and_print(f"--- Created {len(sylt_data)} SYLT entries. ---")

            # --- Step 3: Embed data into the MP3 file ---
            try:
                log_and_print("--- Loading MP3 file with mutagen... ---")
                audio_file = MP3(output_path, ID3=ID3)
                
                if audio_file.tags is None:
                    log_and_print("--- No ID3 tags found. Creating new ones. ---")
                    audio_file.add_tags()

                # --- Embed SYLT (Synchronized Lyrics) ---
                log_and_print("--- Creating and adding SYLT frame... ---")
                sylt_frame = SYLT(
                    encoding=Encoding.UTF8,
                    lang='eng',
                    format=2,
                    type=1,
                    text=sylt_data
                )
                audio_file.tags.delall('SYLT')
                audio_file.tags.add(sylt_frame)

                # --- Embed USLT (Unsynchronized Lyrics) as a fallback ---
                log_and_print("--- Creating and adding USLT frame... ---")
                uslt_frame = USLT(
                    encoding=Encoding.UTF8,
                    lang='eng',
                    desc='',
                    text=text
                )
                audio_file.tags.delall('USLT')
                audio_file.tags.add(uslt_frame)

                audio_file.save()
                log_and_print("--- Successfully embedded SYLT and USLT frames. ---")
                
            except Exception as e:
                log_and_print(f"--- ERROR: Failed to embed SYLT/USLT: {e} ---")
            return output_path, log_messages

        except Exception as e:
            log_and_print(f"--- ERROR: Unexpected error in embed_sylt_lyrics: {e} ---")
            return output_path, log_messages

    def _create_sylt_data(self, word_timestamps: List[Dict]) -> List[tuple]:
        """
        Create SYLT data format from word timestamps
        
        Args:
            word_timestamps: List of word timestamp dictionaries
            
        Returns:
            List of tuples (text, timestamp_in_milliseconds)
        """
        # Debug print to check incoming data
        print(f"DEBUG: word_timestamps received in _create_sylt_data: {word_timestamps}")
        try:
            sylt_data = []
            
            for word_data in word_timestamps:
                word = word_data.get('word', '').strip()
                start_time = word_data.get('start', 0)
                
                if word:
                    # Convert seconds to milliseconds
                    timestamp_ms = int(start_time * 1000)
                    sylt_data.append((word, timestamp_ms))
            
            return sylt_data
            
        except Exception as e:
            print(f"Error creating SYLT data: {str(e)}")
            return []
    
    def _create_line_based_sylt_data(self, word_timestamps: List[Dict], max_words_per_line: int = 6) -> List[tuple]:
        """
        Create line-based SYLT data (alternative approach)
        
        Args:
            word_timestamps: List of word timestamp dictionaries
            max_words_per_line: Maximum words per line
            
        Returns:
            List of tuples (line_text, timestamp_in_milliseconds)
        """
        try:
            sylt_data = []
            current_line = []
            
            for word_data in word_timestamps:
                current_line.append(word_data)
                
                # Check if we should end this line
                if len(current_line) >= max_words_per_line:
                    if current_line:
                        line_text = ' '.join([w.get('word', '') for w in current_line]).strip()
                        start_time = current_line[0].get('start', 0)
                        timestamp_ms = int(start_time * 1000)
                        
                        if line_text:
                            sylt_data.append((line_text, timestamp_ms))
                        
                        current_line = []
            
            # Add remaining words as final line
            if current_line:
                line_text = ' '.join([w.get('word', '') for w in current_line]).strip()
                start_time = current_line[0].get('start', 0)
                timestamp_ms = int(start_time * 1000)
                
                if line_text:
                    sylt_data.append((line_text, timestamp_ms))
            
            return sylt_data
            
        except Exception as e:
            print(f"Error creating line-based SYLT data: {str(e)}")
            return []
    
    def verify_sylt_embedding(self, mp3_path: str) -> Dict:
        """
        Verify that SYLT lyrics are properly embedded
        
        Args:
            mp3_path: Path to the MP3 file
            
        Returns:
            Dictionary with verification results
        """
        try:
            audio_file = MP3(mp3_path)
            
            result = {
                'has_sylt': False,
                'has_uslt': False,
                'sylt_entries': 0,
                'error': None
            }
            
            if audio_file.tags:
                # Check for SYLT
                sylt_frames = audio_file.tags.getall('SYLT')
                if sylt_frames:
                    result['has_sylt'] = True
                    result['sylt_entries'] = len(sylt_frames[0].text) if sylt_frames[0].text else 0
                
                # Check for USLT (fallback)
                uslt_frames = audio_file.tags.getall('USLT')
                if uslt_frames:
                    result['has_uslt'] = True
            
            return result
            
        except Exception as e:
            return {
                'has_sylt': False,
                'has_uslt': False,
                'sylt_entries': 0,
                'error': str(e)
            }
    
    def extract_sylt_lyrics(self, mp3_path: str) -> List[Dict]:
        """
        Extract SYLT lyrics from an MP3 file (for debugging)
        
        Args:
            mp3_path: Path to the MP3 file
            
        Returns:
            List of dictionaries with text and timestamp
        """
        try:
            audio_file = MP3(mp3_path)
            lyrics_data = []
            
            if audio_file.tags:
                sylt_frames = audio_file.tags.getall('SYLT')
                
                for frame in sylt_frames:
                    if frame.text:
                        for text, timestamp_ms in frame.text:
                            lyrics_data.append({
                                'text': text,
                                'timestamp': timestamp_ms / 1000.0  # Convert to seconds
                            })
            
            return lyrics_data
            
        except Exception as e:
            print(f"Error extracting SYLT lyrics: {str(e)}")
            return []
    
    def create_lrc_file(self, word_timestamps: List[Dict], output_path: str) -> str:
        """
        Create an LRC (lyrics) file as an additional export option
        
        Args:
            word_timestamps: List of word timestamp dictionaries
            output_path: Path for the output LRC file
            
        Returns:
            Path to the created LRC file
        """
        try:
            lrc_lines = []
            
            # Group words into lines
            current_line = []
            for word_data in word_timestamps:
                current_line.append(word_data)
                
                if len(current_line) >= 8:  # 8 words per line
                    if current_line:
                        line_text = ' '.join([w.get('word', '') for w in current_line])
                        start_time = current_line[0].get('start', 0)
                        
                        # Format timestamp as [mm:ss.xx]
                        minutes = int(start_time // 60)
                        seconds = start_time % 60
                        timestamp_str = f"[{minutes:02d}:{seconds:05.2f}]"
                        
                        lrc_lines.append(f"{timestamp_str}{line_text}")
                        current_line = []
            
            # Add remaining words
            if current_line:
                line_text = ' '.join([w.get('word', '') for w in current_line])
                start_time = current_line[0].get('start', 0)
                
                minutes = int(start_time // 60)
                seconds = start_time % 60
                timestamp_str = f"[{minutes:02d}:{seconds:05.2f}]"
                
                lrc_lines.append(f"{timestamp_str}{line_text}")
            
            # Write LRC file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lrc_lines))
            
            return output_path
            
        except Exception as e:
            raise Exception(f"Error creating LRC file: {str(e)}")
    
    def __del__(self):
        """Clean up temporary files"""
        import shutil
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except:
                pass
