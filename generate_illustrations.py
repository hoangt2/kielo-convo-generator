import os
import sys
import json
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types

# --- Load environment variables ---
load_dotenv()

# --- Gemini Client Initialization ---
# The client automatically looks for the GEMINI_API_KEY environment variable.
try:
    # Initialize client once
    client = genai.Client()
    print("✅ Gemini client initialized.")
except Exception as e:
    print(f"❌ Error initializing Gemini client: {e}")
    print("Please ensure you have set the GEMINI_API_KEY environment variable.")
    # Exit if the client cannot be initialized due to missing key or other error
    sys.exit(1)

# --- Configuration ---
INPUT_DIR = "scripts"
OUTPUT_DIR = "illustrations"
MODEL_NAME = "gemini-2.5-flash-image"

# --- Fixed illustration style description ---
ILLUSTRATION_STYLE = (
    "Illustration style: Playful, modern doodle style. "
    "Bold, thick black outlines with variable line weight. "
    "Use a vibrant and conventional color palette. "
    "Solid, warm off-white background. "
    "High contrast, clean, and quirky aesthetic. "
    "Animals and people should have natural faces. "
    "No face, no smiley, no anthropomorphism on inanimate objects. "
    "No text, no labels, no words, no letters. "
    "No extra decorations, no stars, no sparkles, no background doodles. "
    "Minimal detail, keep it clean and uncluttered."
)

## 🏗️ Core Functions

### 1. Prompt Generation

def create_generic_prompt(data: dict) -> str:
    """Create a general illustration prompt from conversation data."""

    metadata = data.get("metadata", {})
    idea = data.get("idea", {})
    dialogues = data.get("dialogue_list", [])

    title = idea.get("title", "Untitled Scene")
    description = idea.get("description", "")
    language = metadata.get("language", "Unknown language")
    tone = metadata.get("tone", "neutral")
    length = metadata.get("length", "short")

    characters = idea.get("characters", [])
    character_descriptions = []
    for c in characters:
        name = c.get("name", "Unnamed")
        gender = c.get("gender", "")
        age = c.get("age", "")
        tone = c.get("default_tone", "")
        character_descriptions.append(f"{name} ({gender}, {age}, {tone})")
    character_info = ", ".join(character_descriptions) if character_descriptions else "unspecified characters"

    # Sample dialogue preview
    all_lines = " ".join([d.get("text", "") for d in dialogues])
    sample_dialogue_words = all_lines.split()[:40]
    sample_dialogue = " ".join(sample_dialogue_words) + ("..." if len(all_lines.split()) > 40 else "")

    # Build generic illustration prompt
    prompt = (
        f"Create a single illustration that closely depicts the following conversation scenario. "
        f"{ILLUSTRATION_STYLE} "
        f"Do not include any text or captions in the image. "
        f"Scene: {description or 'No explicit description provided.'} "
        f"Characters: {character_info}. "
        f"Show the characters naturally interacting in a setting that fits this scenario. "
        f"The tone is {tone} and the mood should reflect this sample dialogue: '{sample_dialogue}'. "
    )

    return prompt

def generate_illustration_from_json(json_path: str, aspect_ratio: str = "9:16") -> bool:
    """
    Generate an illustration for one JSON script using Gemini.

    :param json_path: Path to the input JSON file.
    :param aspect_ratio: The desired aspect ratio for the generated image.
    :return: True if successful, False otherwise.
    """
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: File not found at {json_path}")
        return False
    except json.JSONDecodeError:
        print(f"❌ Error: Invalid JSON format in {json_path}")
        return False

    prompt = create_generic_prompt(data)
    print(f"\n🎨 Generating illustration for: {os.path.basename(json_path)}")

    # --- GenerateContentConfig ---
    # Configure the response to request an image modality and set the aspect ratio.
    config = types.GenerateContentConfig(
        response_modalities=[types.Modality.IMAGE],
        image_config=types.ImageConfig(
            aspect_ratio=aspect_ratio,
        ),
        safety_settings=[
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="BLOCK_NONE"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="BLOCK_NONE"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="BLOCK_NONE"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="BLOCK_NONE"
            ),
        ]
    )

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[prompt],
            config=config
        )
    except Exception as e:
        print(f"❌ API Error during generation for {os.path.basename(json_path)}: {e}")
        return False

    # Check 1: Ensure candidates were generated at all.
    if not response.candidates:
        print(f"⚠️ **Response failed to generate candidates** for {os.path.basename(json_path)}.")
        if response.prompt_feedback.block_reason:
            print(f"   Reason: Content was blocked due to {response.prompt_feedback.block_reason}.")
        else:
            print("   Reason: Unknown failure. Check prompt safety or API logs.")
        return False

    # Check 2 (The Fix): Ensure the content object exists to avoid AttributeError.
    first_candidate = response.candidates[0]
    if first_candidate.content is None:
        print(f"⚠️ **Candidate content is None** for {os.path.basename(json_path)}. Likely due to a safety block on the *output*.")
        finish_reason = first_candidate.finish_reason.name if first_candidate.finish_reason else 'Unknown'
        print(f"   Candidate Finish Reason: {finish_reason}.")
        print("   Try simplifying the scene description or checking API safety guidelines.")
        return False

    # Extract and save image(s)
    for part in first_candidate.content.parts:
        if part.inline_data is not None:
            image_data = part.inline_data.data

            try:
                image = Image.open(BytesIO(image_data))
            except Exception as e:
                print(f"❌ Error opening image data for {os.path.basename(json_path)}: {e}")
                return False

            os.makedirs(OUTPUT_DIR, exist_ok=True)
            # --- MODIFICATION START ---
            base_filename = os.path.splitext(os.path.basename(json_path))[0]
            output_filename = "conversation_" + base_filename + ".png"
            # --- MODIFICATION END ---
            output_path = os.path.join(OUTPUT_DIR, output_filename)

            image.save(output_path)
            print(f"✅ Image saved to {output_path}")
            return True # Assuming only one image is desired per script

    print(f"⚠️ No image data found in model response parts for {os.path.basename(json_path)}. Check API logs.")
    return False

def main():
    """Main function to process all JSON scripts and generate illustrations."""

    # Create the input directory if it doesn't exist for clarity
    os.makedirs(INPUT_DIR, exist_ok=True)

    # Process all JSON files in the scripts/ directory
    files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".json")]

    if not files:
        print(f"⚠️ No JSON files found in {INPUT_DIR}/. Create some script JSON files to begin.")
        return

    for file in files:
        json_path = os.path.join(INPUT_DIR, file)
        success = generate_illustration_from_json(json_path, aspect_ratio="9:16")
        if not success:
            print(f"\n❌ Stopping process due to error generating illustration for {file}.")
            sys.exit(1)


if __name__ == "__main__":
    main()