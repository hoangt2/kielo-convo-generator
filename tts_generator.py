import os
import json
import sys # Added to handle command-line arguments
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

# --- Configuration (Modified) ---
CONVERSATION_SCRIPTS_DIR = "scripts"
PODCAST_SCRIPTS_DIR = "podcast_scripts"
OUTPUT_AUDIO_DIR = "mp3"


def load_dialogue_data(file_path):
    """Loads the dialogue list from a JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        dialogue_list = data.get("dialogue_list")
        if not dialogue_list:
            raise ValueError(f"Missing 'dialogue_list' key in {os.path.basename(file_path)}")

        # Filter out SFX entries — only keep dialogue entries for TTS
        dialogue_only = [item for item in dialogue_list if item.get("type") != "sfx"]
        
        if not dialogue_only:
            raise ValueError(f"No dialogue entries found in {os.path.basename(file_path)}")

        return dialogue_only

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        print(f"❌ Skipping {file_path}: {e}")
        return None


def generate_and_save_audio(elevenlabs_client, dialogue_list, output_filename, script_type):
    """Generates and saves the conversation or podcast audio for one script. Returns True on success."""
    try:
        print(f"⏳ Generating {script_type} audio for: {output_filename} ...")

        # Force Finnish for conversations so the model doesn't mis-detect short/ambiguous
        # words (e.g. the Finnish greeting "Moi" being read as French "moi"/moa).
        # Podcasts are English-led, so leave their language auto-detected.
        convert_kwargs = {"inputs": dialogue_list}
        if script_type == "conversation":
            convert_kwargs["language_code"] = "fi"

        # Generate audio using ElevenLabs
        # NOTE: elevenlabs_client.text_to_dialogue.convert is used for both
        # multi-character dialogue and solo/mixed scripts.
        audio_stream = elevenlabs_client.text_to_dialogue.convert(**convert_kwargs)
        audio_bytes = b"".join(audio_stream)

        # Save to file
        os.makedirs(OUTPUT_AUDIO_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_AUDIO_DIR, output_filename)

        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        print(f"✅ Saved: {output_path}")
        return True

    except Exception as e:
        print(f"❌ ElevenLabs API Error for {output_filename}: {e}")
        return False


def process_scripts_directory(elevenlabs_client, scripts_dir, script_type):
    """Helper function to process all JSON files in a given directory. Returns True if all succeeded."""
    
    if not os.path.isdir(scripts_dir):
        print(f"❌ Folder not found: {scripts_dir}")
        return False

    # Get all JSON files in the scripts folder
    script_files = [f for f in os.listdir(scripts_dir) if f.endswith(".json")]

    if not script_files:
        print(f"⚠️ No JSON files found in {scripts_dir}")
        return False

    print(f"🎬 Found {len(script_files)} {script_type} script(s) in '{scripts_dir}'. Starting generation...\n")

    had_errors = False
    for filename in script_files:
        file_path = os.path.join(scripts_dir, filename)
        base_name = os.path.splitext(filename)[0]
        # Prepend type to filename to avoid naming conflicts if titles are the same
        output_filename = f"{script_type}_{base_name}.mp3" 

        dialogue_list = load_dialogue_data(file_path)
        if dialogue_list:
            if not generate_and_save_audio(elevenlabs_client, dialogue_list, output_filename, script_type):
                had_errors = True

    if had_errors:
        print(f"\n❌ Finished processing {script_type} scripts with errors.")
    else:
        print(f"\n✅ Finished processing {script_type} scripts.")
    return not had_errors


def main():
    # Load environment variables (API key)
    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("❌ ELEVENLABS_API_KEY not found. Please add it to your .env file.")
        sys.exit(1)

    elevenlabs = ElevenLabs(api_key=api_key)

    # Determine which folder to process based on command-line argument
    all_succeeded = True
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'podcast':
        # Process podcast scripts only
        all_succeeded = process_scripts_directory(elevenlabs, PODCAST_SCRIPTS_DIR, "podcast")
    elif len(sys.argv) > 1 and sys.argv[1].lower() == 'all':
        # Process both folders
        print("Processing ALL scripts (Conversation and Podcast)...")
        conv_ok = process_scripts_directory(elevenlabs, CONVERSATION_SCRIPTS_DIR, "conversation")
        pod_ok = process_scripts_directory(elevenlabs, PODCAST_SCRIPTS_DIR, "podcast")
        all_succeeded = conv_ok and pod_ok
    else:
        # Default: Process conversation scripts only
        all_succeeded = process_scripts_directory(elevenlabs, CONVERSATION_SCRIPTS_DIR, "conversation")

    if not all_succeeded:
        print("\n❌ Audio generation failed with errors!")
        sys.exit(1)

    print("\n🏁 All specified audio generation complete!")


if __name__ == "__main__":
    main()