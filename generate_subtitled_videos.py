import os
import shutil
from pathlib import Path
import time

# ... (Imports for subtitle_generator, audio_mixer, slow_down_video remain, 
# although slow_down_video is no longer used, I'll keep the import list as in the original context) ...
from subtitle_generator import generate_subtitles, cleanup_temp_file
from audio_mixer import add_background_music 

# --- Configuration ---
SOURCE_DIR = Path("output_videos")
OUTPUT_DIR = Path("final_subtitled_videos")
SUBTITLES_DIR = Path("subtitles")
TEMP_DIR = Path("temp_processing") # Keeping TEMP_DIR setup for potential future use or other temporary files
# Use Google Gemini for translations in subtitle generation
TRANSLATION_MODEL = "gemini-2.5-flash"
# --- End Configuration ---


def setup_directories():
    """Ensure all required directories exist."""
    SOURCE_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    SUBTITLES_DIR.mkdir(exist_ok=True)
    TEMP_DIR.mkdir(exist_ok=True)
    print(f"Directories checked/created: {SOURCE_DIR.name}, {OUTPUT_DIR.name}, {SUBTITLES_DIR.name}, {TEMP_DIR.name}")


def batch_process_videos():
    """
    Loops through videos, performs subtitling, adds background music,
    and moves the .ass file.
    """
    setup_directories()
    
    video_extensions = ['*.mp4', '*.mov', '*.avi', '*.mkv']
    video_files = []
    for ext in video_extensions:
        video_files.extend(SOURCE_DIR.glob(ext))
        
    if not video_files:
        print(f"No video files found in the '{SOURCE_DIR.name}' folder.")
        return

    print(f"\nFound {len(video_files)} video(s) to process.")
    total_start_time = time.time()
    
    # We will use 'temp_subtitled_video_path' for the output of subtitling 
    # and 'final_output_video_path' for the output of audio mixing.
    
    for i, video_file_path in enumerate(video_files):
        print("\n" + "="*50)
        print(f"Processing video {i+1}/{len(video_files)}: {video_file_path.name}")
        print("="*50)
        
        # Define paths
        # Subtitles will be burned into a temporary file first
        temp_subtitled_video_path = TEMP_DIR / f"subtitled_{video_file_path.name}"
        # Final output will go directly into the OUTPUT directory
        final_output_video_path = OUTPUT_DIR / video_file_path.name
        ass_file_in_source = video_file_path.with_suffix(".ass")
        
        # --- STEP 1: Subtitling ---
        print("Subtitling Step...")
        # Subtitle the source video and output the result to a temporary file
        generate_subtitles(
            str(video_file_path),
            str(temp_subtitled_video_path),
            translation_model=TRANSLATION_MODEL,
            subtitle_folder=str(SUBTITLES_DIR)
        )
        print("Subtitling Step Complete.")
        
        if not temp_subtitled_video_path.exists():
            print("🛑 Cannot proceed: Subtitled video not found after Step 1.")
            continue
        
        # --- STEP 2: Adding Background Music ---
        print("\nAudio Mixing Step...")
        # Mix the audio in the temporary subtitled video, outputting the final result
        if temp_subtitled_video_path.exists():
            add_background_music(
                input_video_path=temp_subtitled_video_path, 
                final_output_path=final_output_video_path 
            )
        else:
            # This check is mostly redundant due to the 'continue' above, but good practice
            print("Skipping audio mixing: Subtitled video for mixing not found.")

        # --- STEP 3: Cleanup ---
        # Move the generated .ass file
        if ass_file_in_source.exists():
            target_ass_path = SUBTITLES_DIR / ass_file_in_source.name
            shutil.move(str(ass_file_in_source), str(target_ass_path))
            print(f"-> Moved subtitle file to: {target_ass_path.name}")
        
        # Clean up the temporary subtitled video
        cleanup_temp_file(temp_subtitled_video_path)
        print(f"-> Cleaned up temporary subtitled video: {temp_subtitled_video_path.name}")
        
        # Check if the final file exists
        if final_output_video_path.exists():
            print(f"✅ Successfully created final video: {final_output_video_path.name}")
        else:
            print(f"❌ Final output video was not created: {final_output_video_path.name}")


    # Clean up temp directory
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
        print(f"\n-> Removed temporary directory: {TEMP_DIR.name}")

    total_time = time.time() - total_start_time
    print("\n" + "*"*50)
    print(f"Batch processing complete! Processed {len(video_files)} video(s).")
    print(f"Total elapsed time: {total_time:.2f} seconds.")
    print(f"Final videos (subtitled and mixed) are in the '{OUTPUT_DIR.name}' folder.")
    print("*"*50)


if __name__ == "__main__":
    batch_process_videos()