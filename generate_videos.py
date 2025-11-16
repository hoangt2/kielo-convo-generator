import os
from pathlib import Path
from PIL import Image
import subprocess

# --- Configuration ---
ILLUSTRATION_FOLDER = Path("illustrations")
MP3_FOLDER = Path("mp3")
OUTPUT_FOLDER = Path("output_videos")
VIDEO_RESOLUTION = (720, 1280) 

OUTPUT_FOLDER.mkdir(exist_ok=True)

def prepare_image(image_path, target_size, temp_dir=Path("temp")):
    temp_dir.mkdir(exist_ok=True)
    
    img = Image.open(image_path).convert("RGB")
    img = img.resize(target_size)
    temp_path = temp_dir / f"{Path(image_path).stem}_resized.png"
    img.save(temp_path)
    return temp_path

# --- Main Loop ---
illustration_files = {f.stem: f for f in ILLUSTRATION_FOLDER.iterdir() if f.is_file()}
mp3_files = {f.stem: f for f in MP3_FOLDER.iterdir() if f.is_file() and f.suffix.lower() == ".mp3"}
common_names = set(illustration_files.keys()) & set(mp3_files.keys())

if not common_names:
    print("No matching illustration and MP3 files found.")
else:
    print(f"Found {len(common_names)} matching pairs.")

    temp_folder = Path("temp")
    temp_folder.mkdir(exist_ok=True)

    for name in sorted(common_names):
        image_path = illustration_files[name]
        audio_path = mp3_files[name]
        output_path = OUTPUT_FOLDER / f"{name}.mp4"

        try:
            print(f"Processing: {name}")

            # Prepare the image
            temp_image = prepare_image(image_path, VIDEO_RESOLUTION, temp_folder)

            # Build FFmpeg command
            cmd = [
                "ffmpeg",
                "-y",  # overwrite output
                "-loop", "1",
                "-i", str(temp_image),
                "-i", str(audio_path),
                "-c:v", "libx264",
                "-tune", "stillimage",
                "-c:a", "aac",
                "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-shortest",
                str(output_path)
            ]

            subprocess.run(cmd, check=True)
            print(f"✅ Video saved: {output_path.name}")

        except Exception as e:
            print(f"❌ Error processing {name}: {e}")

    # Cleanup temp images
    for f in temp_folder.glob("*"):
        f.unlink()
    temp_folder.rmdir()

print("All videos generated!")
