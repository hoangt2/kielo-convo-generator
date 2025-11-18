import os
import shutil
import glob

# Define directories and files to clean up
CLEANUP_PATHS = {
    "directories": [
        "scripts",
        "mp3",
        "output",
        "output_videos",
        "illustrations",
        "final_subtitled_videos",
        "subtitles",
        "podcast_scripts",
    ],
    "files": [
        "ideas.json",
        "podcast_ideas.json",
    ]
}

def cleanup():
    """Remove all generated files and directories."""
    print("🧹 Starting cleanup...")
    
    # Remove directories
    for directory in CLEANUP_PATHS["directories"]:
        if os.path.exists(directory):
            try:
                shutil.rmtree(directory)
                print(f"✅ Removed directory: {directory}")
            except Exception as e:
                print(f"❌ Error removing directory '{directory}': {e}")
        else:
            print(f"⚠️ Directory not found: {directory}")
    
    # Remove files
    for file in CLEANUP_PATHS["files"]:
        if os.path.exists(file):
            try:
                os.remove(file)
                print(f"✅ Removed file: {file}")
            except Exception as e:
                print(f"❌ Error removing file '{file}': {e}")
        else:
            print(f"⚠️ File not found: {file}")
    
    print("🎉 Cleanup completed!")

if __name__ == "__main__":
    confirmation = input("⚠️ This will delete all generated files. Continue? (yes/no): ").strip().lower()
    if confirmation == "yes":
        cleanup()
    else:
        print("❌ Cleanup cancelled.")
