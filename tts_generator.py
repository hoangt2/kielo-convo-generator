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

        return dialogue_list

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        print(f"❌ Skipping {file_path}: {e}")
        return None


def generate_and_save_audio(elevenlabs_client, dialogue_list, output_filename, script_type):
    """Generates and saves the conversation or podcast audio for one script."""
    try:
        print(f"⏳ Generating {script_type} audio for: {output_filename} ...")

        # Generate audio using ElevenLabs
        # NOTE: elevenlabs_client.text_to_dialogue.convert is used for both
        # multi-character dialogue and solo/mixed scripts.
        audio_stream = elevenlabs_client.text_to_dialogue.convert(inputs=dialogue_list)
        audio_bytes = b"".join(audio_stream)

        # Save to file
        os.makedirs(OUTPUT_AUDIO_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_AUDIO_DIR, output_filename)

        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        print(f"✅ Saved: {output_path}")

    except Exception as e:
        print(f"❌ ElevenLabs API Error for {output_filename}: {e}")


def process_scripts_directory(elevenlabs_client, scripts_dir, script_type):
    """Helper function to process all JSON files in a given directory."""
    
    if not os.path.isdir(scripts_dir):
        print(f"❌ Folder not found: {scripts_dir}")
        return

    # Get all JSON files in the scripts folder
    script_files = [f for f in os.listdir(scripts_dir) if f.endswith(".json")]

    if not script_files:
        print(f"⚠️ No JSON files found in {scripts_dir}")
        return

    print(f"🎬 Found {len(script_files)} {script_type} script(s) in '{scripts_dir}'. Starting generation...\n")

    for filename in script_files:
        file_path = os.path.join(scripts_dir, filename)
        base_name = os.path.splitext(filename)[0]
        # Prepend type to filename to avoid naming conflicts if titles are the same
        output_filename = f"{script_type}_{base_name}.mp3" 

        dialogue_list = load_dialogue_data(file_path)
        if dialogue_list:
            generate_and_save_audio(elevenlabs_client, dialogue_list, output_filename, script_type)

    print(f"\n✅ Finished processing {script_type} scripts.")


def main():
    # Load environment variables (API key)
    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("❌ ELEVENLABS_API_KEY not found. Please add it to your .env file.")
        return

    elevenlabs = ElevenLabs(api_key=api_key)
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

        return dialogue_list

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        print(f"❌ Skipping {file_path}: {e}")
        return None


def generate_and_save_audio(elevenlabs_client, dialogue_list, output_filename, script_type):
    """Generates and saves the conversation or podcast audio for one script."""
    try:
        print(f"⏳ Generating {script_type} audio for: {output_filename} ...")

        # Generate audio using ElevenLabs
        # NOTE: elevenlabs_client.text_to_dialogue.convert is used for both
        # multi-character dialogue and solo/mixed scripts.
        audio_stream = elevenlabs_client.text_to_dialogue.convert(inputs=dialogue_list)
        audio_bytes = b"".join(audio_stream)

        # Save to file
        os.makedirs(OUTPUT_AUDIO_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_AUDIO_DIR, output_filename)

        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        print(f"✅ Saved: {output_path}")

    except Exception as e:
        print(f"❌ ElevenLabs API Error for {output_filename}: {e}")


def process_scripts_directory(elevenlabs_client, scripts_dir, script_type):
    """Helper function to process all JSON files in a given directory."""
    
    if not os.path.isdir(scripts_dir):
        print(f"❌ Folder not found: {scripts_dir}")
        return

    # Get all JSON files in the scripts folder
    script_files = [f for f in os.listdir(scripts_dir) if f.endswith(".json")]

    if not script_files:
        print(f"⚠️ No JSON files found in {scripts_dir}")
        return

    print(f"🎬 Found {len(script_files)} {script_type} script(s) in '{scripts_dir}'. Starting generation...\n")

    for filename in script_files:
        file_path = os.path.join(scripts_dir, filename)
        base_name = os.path.splitext(filename)[0]
        # Prepend type to filename to avoid naming conflicts if titles are the same
        output_filename = f"{script_type}_{base_name}.mp3" 

        dialogue_list = load_dialogue_data(file_path)
        if dialogue_list:
            generate_and_save_audio(elevenlabs_client, dialogue_list, output_filename, script_type)

    print(f"\n✅ Finished processing {script_type} scripts.")


def main():
    # Load environment variables (API key)
    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("❌ ELEVENLABS_API_KEY not found. Please add it to your .env file.")
        return

    elevenlabs = ElevenLabs(api_key=api_key)

    # Determine which folder to process based on command-line argument
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'podcast':
        # Process podcast scripts only
        process_scripts_directory(elevenlabs, PODCAST_SCRIPTS_DIR, "podcast")
    elif len(sys.argv) > 1 and sys.argv[1].lower() == 'all':
        # Process both folders
        print("Processing ALL scripts (Conversation and Podcast)...")
        process_scripts_directory(elevenlabs, CONVERSATION_SCRIPTS_DIR, "convo_fi")
        process_scripts_directory(elevenlabs, PODCAST_SCRIPTS_DIR, "podcast")
    else:
        # Default: Process conversation scripts only
        process_scripts_directory(elevenlabs, CONVERSATION_SCRIPTS_DIR, "convo_fi")

    print("\n🏁 All specified audio generation complete!")


if __name__ == "__main__":
    main()