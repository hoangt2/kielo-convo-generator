import os
import shutil
from pathlib import Path

def cleanup():
    """Removes generated files and cleans specific directories."""
    print(f"\n{'='*60}")
    print("🧹 CLEANUP IN PROGRESS")
    print(f"{'='*60}")

    # Directories to clean (remove contents, keep directory)
    directories_to_clean = [
        "illustrations",
        "mp3",
        "output_videos",
        "scripts",
        "sfx"
    ]

    # Files to remove
    files_to_remove = [
        "ideas.json",
        "podcast_ideas.json"
    ]

    base_dir = Path(__file__).parent

    # Clean directories
    for dir_name in directories_to_clean:
        dir_path = base_dir / dir_name
        if dir_path.exists():
            print(f"📂 Cleaning directory: {dir_name}/...")
            for item in dir_path.iterdir():
                if item.name == ".gitkeep": # Optional: preserve .gitkeep if it exists
                    continue
                if dir_name == "output_videos" and item.name == "prod":
                    print(f"   📁 Preserving: {dir_name}/prod/")
                    continue
                try:
                    if item.is_file() or item.is_symlink():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                except Exception as e:
                    print(f"   ❌ Failed to delete {item.name}: {e}")
        else:
            print(f"   (Directory {dir_name} not found, skipping)")

    # Remove files
    for file_name in files_to_remove:
        file_path = base_dir / file_name
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"🗑️  Deleted file: {file_name}")
            except Exception as e:
                print(f"   ❌ Failed to delete {file_name}: {e}")
        else:
            print(f"   (File {file_name} not found, skipping)")

    print(f"\n{'='*60}")
    print("✨ CLEANUP COMPLETE")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    cleanup()
