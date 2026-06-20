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
    "A playful, modern doodle-style 2D illustration. "
    "The image must feature bold, thick, uniform black outlines with flat, naturalistic colors. "
    "Do not use gradients, 3D rendering, or complex shading. "
    "Characters should have friendly, exaggerated proportions with simple, clean features. "
    "Any inanimate objects in the scene must remain strictly as normal objects without any faces, "
    "smiles, or anthropomorphic details. "
    "Use a soft, cohesive pastel-leaning color palette. "
    "High quality vector-art style. "
    "No text, no labels, no words, no letters."
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
    ambient_setting = idea.get("ambient_setting", "")
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

    # Use ONLY the scene narrative for the image — never the dialogue or any quoted phrases.
    # In series mode the description has extra blocks (target phrases, speech styles, direction)
    # appended after a blank line; those are for the scriptwriter, NOT the illustrator. Keeping
    # them would make the model render speech bubbles with that text, so we take the first block.
    scene = (description or "").split("\n\n")[0].strip()

    # Environment guidance — give the model a real location to build, not an empty backdrop.
    setting_clause = (
        f"Setting: a detailed {ambient_setting} environment. " if ambient_setting else ""
    )

    # Build generic illustration prompt
    prompt = (
        f"Create a single, wordless illustration of the following scene. "
        f"{ILLUSTRATION_STYLE} "
        f"CRITICAL — this must be a TEXT-FREE image: do NOT draw any text, letters, words, "
        f"numbers, captions, signs, or labels of any kind. Do NOT draw speech bubbles, dialogue "
        f"balloons, or thought bubbles. Do NOT make a comic strip or multiple panels — produce ONE "
        f"single illustration of one moment. "
        f"Scene: {scene or 'No explicit description provided.'} "
        f"Characters: {character_info}. "
        f"Convey the interaction through facial expression, gesture, and body language. "
        f"{setting_clause}"
        f"Render a rich, fully-illustrated background that clearly establishes the location: include "
        f"contextual environmental elements — furniture, décor, windows, plants, and props that fit "
        f"the setting — drawn in the same flat 2D doodle style. Place the characters within this "
        f"environment so it feels like a real place, not a blank backdrop. Keep the composition "
        f"visually balanced and readable, not cluttered. The overall tone is {tone}. "
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

    # Collect character reference portraits (series mode) so faces/clothing stay consistent
    # across episodes. Characters carry `reference_image` paths via series_compile.py.
    ref_images = []
    for c in data.get("idea", {}).get("characters", []):
        ref_path = c.get("reference_image")
        if ref_path and os.path.exists(ref_path):
            try:
                ref_images.append(Image.open(ref_path))
                print(f"   🧍 Using reference: {ref_path}")
            except Exception as e:
                print(f"   ⚠️  Could not open reference {ref_path}: {e}")

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

    # Build request contents — prepend reference portraits as identity anchors when present.
    if ref_images:
        contents = [
            "Use the following reference portrait(s) for the characters' appearance — keep each "
            "character's face, hair, and clothing consistent with them:",
            *ref_images,
            prompt,
        ]
    else:
        contents = [prompt]

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
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