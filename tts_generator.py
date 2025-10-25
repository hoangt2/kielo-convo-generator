import os
import json
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

# --- Configuration ---
SCRIPTS_DIR = "scripts"
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


def generate_and_save_audio(elevenlabs_client, dialogue_list, output_filename):
    """Generates and saves the conversation audio for one script."""
    try:
        print(f"⏳ Generating audio for: {output_filename} ...")

        # Generate audio using ElevenLabs
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


def main():
    # Load environment variables (API key)
    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("❌ ELEVENLABS_API_KEY not found. Please add it to your .env file.")
        return

    elevenlabs = ElevenLabs(api_key=api_key)

    # Ensure the scripts folder exists
    if not os.path.isdir(SCRIPTS_DIR):
        print(f"❌ Folder not found: {SCRIPTS_DIR}")
        return

    # Get all JSON files in the scripts folder
    script_files = [f for f in os.listdir(SCRIPTS_DIR) if f.endswith(".json")]

    if not script_files:
        print(f"⚠️ No JSON files found in {SCRIPTS_DIR}")
        return

    print(f"🎬 Found {len(script_files)} script(s) in '{SCRIPTS_DIR}'. Starting generation...\n")

    for filename in script_files:
        file_path = os.path.join(SCRIPTS_DIR, filename)
        base_name = os.path.splitext(filename)[0]
        output_filename = f"{base_name}.mp3"

        dialogue_list = load_dialogue_data(file_path)
        if dialogue_list:
            generate_and_save_audio(elevenlabs, dialogue_list, output_filename)

    print("\n🏁 All done!")


if __name__ == "__main__":
    main()
