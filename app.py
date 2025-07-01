import streamlit as st
import os
import tempfile
import json
from pathlib import Path
import time
import traceback
import streamlit.components.v1 as components

AUDIO_PROCESSOR_CLASS = None
IMPORT_ERROR_TRACEBACK = None
try:
    from audio_processor import AudioProcessor
    AUDIO_PROCESSOR_CLASS = AudioProcessor
except Exception:
    IMPORT_ERROR_TRACEBACK = traceback.format_exc()

from video_generator import VideoGenerator
from mp3_embedder import MP3Embedder
from utils import format_timestamp, validate_audio_file, get_audio_info

# Page configuration
st.set_page_config(
    page_title="SyncMaster - AI Audio-Text Synchronization",
    page_icon="🎵",
    layout="wide"
)

# --- Function to log messages to the browser console ---
def log_to_browser_console(messages):
    """Injects JavaScript to log messages to the browser's console."""
    if isinstance(messages, str):
        messages = [messages]
    
    # Escape backticks, backslashes, and ${} to prevent breaking the template literal
    escaped_messages = []
    for msg in messages:
        # Simple JSON stringification is a safe way to escape the string for JS
        escaped_messages.append(json.dumps(msg))

    js_code = f"""
    <script>
    (function() {{
        const logs = [{', '.join(escaped_messages)}];
        console.group("Backend Logs from SyncMaster");
        logs.forEach(log => {{
            if (typeof log === 'string' && log.startsWith('--- ERROR')) {{
                console.error(log);
            }} else if (typeof log === 'string' && log.startsWith('--- WARNING')) {{
                console.warn(log);
            }} else {{
                console.log(log);
            }}
        }});
        console.groupEnd();
    }})();
    </script>
    """
    components.html(js_code, height=0)

# Initialize session state
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'audio_file' not in st.session_state:
    st.session_state.audio_file = None
if 'transcription_data' not in st.session_state:
    st.session_state.transcription_data = None
if 'edited_text' not in st.session_state:
    st.session_state.edited_text = ""
if 'video_style' not in st.session_state:
    st.session_state.video_style = {
        'animation_style': 'Karaoke Style',
        'text_color': '#FFFFFF',
        'highlight_color': '#FFD700',
        'background_color': '#000000',
        'font_family': 'Arial',
        'font_size': 48
    }

if not hasattr(st, "divider"):
    def _divider():
        st.markdown("---")
    st.divider = _divider

# Patch st.button for Streamlit versions that don't support the 'type' argument (<=1.12)
import inspect as _st_inspect
if "type" not in _st_inspect.signature(st.button).parameters:
    _orig_button = st.button

    def _patched_button(label, *args, **kwargs):
        kwargs.pop("type", None)
        kwargs.pop("use_container_width", None)
        return _orig_button(label, *args, **kwargs)

    st.button = _patched_button

if not hasattr(st, "rerun") and hasattr(st, "experimental_rerun"):
    st.rerun = st.experimental_rerun

if hasattr(st, "download_button"):
    import inspect as _dl_inspect
    _dl_sig = _dl_inspect.signature(st.download_button)
    if "use_container_width" not in _dl_sig.parameters:
        _orig_download_button = st.download_button

        def _patched_download_button(label, data, *args, **kwargs):
            kwargs.pop("use_container_width", None)
            return _orig_download_button(label, data, *args, **kwargs)

        st.download_button = _patched_download_button

def main():
    st.title("🎵 SyncMaster")
    st.markdown("### The Intelligent Audio-Text Synchronization Platform")
    st.markdown("Transform your audio files into mobile-compatible MP3s with synchronized lyrics and animated MP4 videos.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.session_state.step >= 1:
            st.success("Step 1: Upload & Process")
        else:
            st.info("Step 1: Upload & Process")
    with col2:
        if st.session_state.step >= 2:
            st.success("Step 2: Review & Customize")
        elif st.session_state.step == 1:
            st.info("Step 2: Review & Customize")
    with col3:
        if st.session_state.step >= 3:
            st.success("Step 3: Export")
        elif st.session_state.step >= 2:
            st.info("Step 3: Export")
    
    st.divider()

    if AUDIO_PROCESSOR_CLASS is None:
        st.error("فشل حاسم: لم يتمكن التطبيق من بدء التشغيل بشكل صحيح.")
        st.subheader("حدث خطأ أثناء محاولة استيراد `AudioProcessor`:")
        st.code(IMPORT_ERROR_TRACEBACK, language="python")
        st.warning("السبب المحتمل: خطأ في الكود في ملف `audio_processor.py` أو مشكلة في الاتصال بـ Google Gemini.")
        st.stop()
    
    if st.session_state.step == 1:
        step_1_upload_and_process()
    elif st.session_state.step == 2:
        step_2_review_and_customize()
    elif st.session_state.step == 3:
        step_3_export()

def step_1_upload_and_process():
    st.header("Step 1: Upload Your Audio File")
    
    uploaded_file = st.file_uploader(
        "Choose an audio file",
        type=['mp3', 'wav', 'm4a'],
        help="Supported formats: MP3, WAV, M4A"
    )
    
    if uploaded_file is not None:
        st.session_state.audio_file = uploaded_file
        st.success(f"File uploaded: {uploaded_file.name}")
        st.info(f"File size: {uploaded_file.size / 1024 / 1024:.2f} MB")
        st.audio(uploaded_file)
        
        if st.button("🚀 Start AI Processing", type="primary", use_container_width=True):
            process_audio()
    
    if st.session_state.audio_file is not None:
        if st.button("🔄 Upload Different File"):
            reset_session()
            st.rerun()

def process_audio():
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(st.session_state.audio_file.name).suffix) as tmp_file:
            tmp_file.write(st.session_state.audio_file.getvalue())
            tmp_file_path = tmp_file.name
        processor = AUDIO_PROCESSOR_CLASS()
        with st.spinner("🎤 Transcribing audio with AI..."):
            transcription_result = processor.transcribe_audio(tmp_file_path)
        if "Error:" in transcription_result or not transcription_result:
            st.error(f"Transcription failed: {transcription_result}")
            os.unlink(tmp_file_path)
            return
        word_timestamps = []
        if hasattr(processor, 'get_word_timestamps'):
            try:
                with st.spinner("🔍 Extracting word timestamps..."):
                    word_timestamps = processor.get_word_timestamps(tmp_file_path)
                # فحص محتوى word_timestamps وعرضه للمستخدم
                st.write("word_timestamps sample:", word_timestamps[:3])
                if not word_timestamps:
                    st.warning("No word timestamps extracted! SYLT embedding will not work.")
            except Exception as e:
                st.warning(f"Could not extract word timestamps: {e}")
        st.session_state.transcription_data = {
            'text': transcription_result,
            'word_timestamps': word_timestamps,
            'audio_path': tmp_file_path
        }
        st.session_state.edited_text = transcription_result
        st.session_state.step = 2
        st.success("🎉 Audio processing complete! Moving to customization...")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error("An error occurred during processing!")
        st.exception(e)
        if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)

def step_2_review_and_customize():
    st.header("Step 2: Review & Customize")
    
    if st.session_state.transcription_data is None:
        st.error("No transcription data found. Please go back to Step 1.")
        if st.button("← Back to Step 1"):
            st.session_state.step = 1
            st.rerun()
        return
    
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.subheader("📝 Text Editor")
        edited_text = st.text_area(
            "Transcribed Text",
            value=st.session_state.edited_text,
            height=300
        )
        st.session_state.edited_text = edited_text
        st.caption(f"Word count: {len(edited_text.split())}")
        
    with col2:
        st.subheader("🎨 Video Style Customization")
        st.session_state.video_style['animation_style'] = st.selectbox("Animation Style", ["Karaoke Style", "Pop-up Word"])
        st.session_state.video_style['text_color'] = st.color_picker("Text Color", st.session_state.video_style['text_color'])
        st.session_state.video_style['highlight_color'] = st.color_picker("Highlight Color", st.session_state.video_style['highlight_color'])

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("← Back to Upload"):
            st.session_state.step = 1
            st.rerun()
    with col3:
        if st.button("Continue to Export →", type="primary"):
            st.session_state.step = 3
            st.rerun()

def step_3_export():
    st.header("Step 3: Export Your Synchronized Media")
    
    if st.session_state.transcription_data is None:
        st.error("No data found. Please go back to Step 1.")
        if st.button("← Back to Step 1"):
            st.session_state.step = 1
            st.rerun()
        return

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🎵 MP3 Export")
        st.markdown("Export MP3 with embedded synchronized lyrics (SYLT).")
        if st.button("📱 Export MP3 with Lyrics", type="primary", use_container_width=True):
            export_mp3()
    
    with col2:
        st.subheader("🎬 MP4 Video Export")
        st.markdown("Create an animated video with synchronized text.")
        if st.button("🎥 Generate Video Summary", type="primary", use_container_width=True):
            export_mp4()

    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("← Back to Customize"):
            st.session_state.step = 2
            st.rerun()
    with col3:
        if st.button("🔄 Start Over"):
            reset_session()
            st.rerun()

def export_mp3():
    """Export MP3 file and log diagnostics to the browser console and Streamlit UI."""
    try:
        with st.spinner("Embedding lyrics into MP3..."):
            embedder = MP3Embedder()
            word_timestamps = st.session_state.transcription_data['word_timestamps']
            audio_path = st.session_state.transcription_data['audio_path']
            output_filename = f"synced_{Path(st.session_state.audio_file.name).stem}.mp3"
            st.info("🔄 بدء عملية دمج النصوص...")
            output_path, log_messages = embedder.embed_sylt_lyrics(
                audio_path, 
                word_timestamps, 
                st.session_state.edited_text,
                output_filename
            )
            log_to_browser_console(log_messages)
            # عرض الـ logs في Streamlit
            st.subheader("📝 تفاصيل العملية:")
            for log in log_messages:
                if "ERROR" in log:
                    st.error(log)
                elif "WARNING" in log:
                    st.warning(log)
                else:
                    st.info(log)

        st.subheader("✅ Export Complete")
        
        if os.path.exists(output_path):
            with open(output_path, 'rb') as audio_file:
                audio_bytes = audio_file.read()
            st.audio(audio_bytes, format='audio/mp3')

            # --- فحص التاغات بعد الدمج مباشرة ---
            from mutagen.mp3 import MP3
            from mutagen.id3 import ID3, SYLT, USLT
            audio_file_obj = MP3(output_path, ID3=ID3)
            sylt_frames = audio_file_obj.tags.getall('SYLT') if audio_file_obj.tags else []
            uslt_frames = audio_file_obj.tags.getall('USLT') if audio_file_obj.tags else []
            st.write(f"SYLT frames after export: {len(sylt_frames)}")
            st.write(f"USLT frames after export: {len(uslt_frames)}")
            if sylt_frames:
                st.write("SYLT frame sample:", sylt_frames[0])
            if uslt_frames:
                st.write("USLT frame sample:", uslt_frames[0])
            # --- نهاية الفحص ---

            verification = embedder.verify_sylt_embedding(output_path)
            st.json(verification)
            if verification['has_sylt']:
                st.success(f"Successfully embedded {verification['sylt_entries']} synchronized words!")
            else:
                st.warning("Warning: Could not verify SYLT embedding. The lyrics may not be synchronized.")
            st.download_button(
                label="Download Synced MP3",
                data=audio_bytes,
                file_name=output_filename,
                mime="audio/mpeg",
                use_container_width=True
            )
        else:
            st.error("Failed to create the MP3 file. Check the browser console for logs.")
            
    except Exception as e:
        st.error(f"An error occurred during MP3 export: {e}")
        log_to_browser_console([f"--- FATAL ERROR in export_mp3: {traceback.format_exc()} ---"])

def export_mp4():
    st.info("MP4 export functionality is not yet implemented with console logging.")

def get_audio_duration_seconds(audio_path: str) -> float:
    try:
        audio_info = get_audio_info(audio_path)
        return audio_info.get('duration', 0)
    except:
        return 0

def get_audio_duration_formatted(audio_path: str) -> str:
    duration = get_audio_duration_seconds(audio_path)
    minutes = int(duration // 60)
    seconds = int(duration % 60)
    return f"{minutes}:{seconds:02d}"

def reset_session():
    for key in list(st.session_state.keys()):
        if key not in ['step']:
            del st.session_state[key]
    st.session_state.step = 1
    st.session_state.audio_file = None
    st.session_state.transcription_data = None
    st.session_state.edited_text = ""
    st.session_state.video_style = {
        'animation_style': 'Karaoke Style',
        'text_color': '#FFFFFF',
        'highlight_color': '#FFD700',
        'background_color': '#000000',
        'font_family': 'Arial',
        'font_size': 48
    }

if __name__ == "__main__":
    main()