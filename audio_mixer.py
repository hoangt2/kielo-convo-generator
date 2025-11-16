import ffmpeg
from pathlib import Path
import os
import shutil

# --- Configuration ---
PRESETS_DIR = Path("presets")
SOURCE_DIR = Path("source")
OUTPUT_DIR = Path("output")

# Define the name of the background music file (must be in the /presets folder)
MUSIC_FILE_NAME = "background_music.mp3"

# Define the amount to reduce the background music's volume
MUSIC_VOLUME_REDUCTION_DB = -15.0
# --- End Configuration ---

# ... (setup_directories and get_video_duration remain the same) ...

def setup_directories():
    """Ensure required directories exist."""
    PRESETS_DIR.mkdir(exist_ok=True)
    SOURCE_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    
def get_video_duration(video_path: Path) -> float:
    """Get the duration of the video in seconds using ffprobe."""
    try:
        probe = ffmpeg.probe(str(video_path))
        
        # Check video stream duration
        video_stream = next((s for s in probe.get('streams', []) if s.get('codec_type') == 'video'), None)
        if video_stream and 'duration' in video_stream:
            return float(video_stream['duration'])
        
        # Fallback to format duration
        if 'duration' in probe.get('format', {}):
            return float(probe['format']['duration'])

    except ffmpeg.Error as e:
        print(f"Error probing video duration for {video_path.name}: {e.stderr.decode()}")
        return 0.0
    except Exception as e:
        print(f"An unexpected error occurred while getting duration: {e}")
        return 0.0
    
    return 0.0


def add_background_music(
    input_video_path: Path, 
    final_output_path: Path # This is the target file in /output
):
    """
    Adds background music to a video file, using a temporary file for mixing
    to avoid FFmpeg's 'same as input' error.
    """
    setup_directories() 
    
    music_path = PRESETS_DIR / MUSIC_FILE_NAME
    video_path = input_video_path
    
    # CRITICAL FIX: Define a temporary output path next to the final output file
    temp_output_path = final_output_path.with_name(f"temp_{final_output_path.name}")

    if not video_path.exists():
        print(f"Error: Video file not found at '{video_path}'")
        return
    
    if not music_path.exists():
        print(f"Error: Background music file not found at '{music_path}'")
        print(f"Please place '{MUSIC_FILE_NAME}' in the '{PRESETS_DIR.name}' folder.")
        return

    print(f"Processing audio for video: {video_path.name}")
    
    try:
        # 1. Get video duration
        video_duration = get_video_duration(video_path)
        if video_duration <= 0:
            print("Error: Could not determine video duration. Aborting music addition.")
            return
        print(f"Video duration: {video_duration:.2f} seconds.")

        # 2. Define inputs
        input_video = ffmpeg.input(str(video_path))
        input_music = ffmpeg.input(str(music_path), stream_loop=-1) 

        # 3. Process video audio (original sound)
        original_audio = input_video.audio
        
        # 4. Process background music
        volume_factor = 10**(MUSIC_VOLUME_REDUCTION_DB/20)
        bgm_volume_adjusted = input_music.audio.filter('volume', f'{volume_factor:.4f}')
        bgm_audio = bgm_volume_adjusted.filter('atrim', duration=video_duration)

        # 5. Mix and map
        mixed_audio = ffmpeg.filter(
            [original_audio, bgm_audio], 
            'amix', 
            inputs=2, 
            duration='first', 
            dropout_transition=0, 
            normalize=False
        )
        
        print(f"Mixing audio (BGM reduced by {MUSIC_VOLUME_REDUCTION_DB:.1f}dB) and original video audio...")

        # 6. Output video - WRITE TO TEMPORARY FILE
        (
            ffmpeg
            .output(
                input_video.video,
                mixed_audio,
                str(temp_output_path), # <--- WRITE TO TEMP FILE
                vcodec='libx264',
                acodec='aac',
                pix_fmt='yuv420p',
                strict='experimental',
                shortest=None
            )
            .overwrite_output()
            .run(quiet=True)
        )
        
        # 7. FINAL STEP: Move the temp file to the final destination, replacing the old file
        shutil.move(str(temp_output_path), str(final_output_path))
        
        print(f"✅ Audio mix complete. Output written to: '{final_output_path.name}'")
        print(f"Note: This file replaced the previous version in '{OUTPUT_DIR.name}'.")

    except ffmpeg.Error as e:
        print("FFmpeg Error during music addition:", e.stderr.decode() if e.stderr else str(e))
    except Exception as e:
        print("Unexpected error during music addition:", e)
    finally:
        # Clean up the temp file if it somehow still exists
        if temp_output_path.exists():
            os.remove(temp_output_path)