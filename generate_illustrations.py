import os
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
    exit()

# --- Configuration ---
INPUT_DIR = "scripts"
OUTPUT_DIR = "illustrations"
MODEL_NAME = "gemini-2.5-flash-image"

# --- Fixed illustration style description ---
ILLUSTRATION_STYLE = (
    "Illustration style: Modern flat illustration with clean lines and a soft, muted color palette. "
    "The characters have a friendly, approachable appearance with rounded features and simple, expressive faces. "
    "Details are minimal but effective, focusing on essential elements like clothing textures, subtle shadows for depth, and distinct objects. "
    "The overall aesthetic is warm, inviting, and slightly whimsical, reminiscent of casual lifestyle or explainer video graphics. "
    "The style avoids harsh outlines or heavy shading, opting for a light and airy feel. "
    "Backgrounds are simplified, using color blocks and minimal object representation to provide context without distraction."
)

## 🏗️ Core Functions

### 1. Prompt Generation

def create_generic_prompt(data: dict) -> str:
    """Create a general illustration prompt from conversation data, including character details."""

    metadata = data.get("metadata", {})
    idea = data.get("idea", {})
    dialogues = data.get("dialogue_list", [])

    title = idea.get("title", "Untitled Scene")
    description = idea.get("description", "")
    language = metadata.get("language", "Unknown language")
    tone = metadata.get("tone", "neutral")
    length = metadata.get("length", "short")

    characters = idea.get("characters", [])
    
    # --- MODIFICATION START: Extract and format detailed character descriptions ---
    character_descriptions = []
    for char in characters:
        name = char.get("name", "Unnamed")
        gender = char.get("gender", "unspecified gender")
        age = char.get("age", "unspecified age")
        character_descriptions.append(f"{name} ({gender}, {age})")
    
    detailed_characters_list = "; ".join(character_descriptions)
    # --- MODIFICATION END ---

    # Sample dialogue preview
    all_lines = " ".join([d.get("text", "") for d in dialogues])
    sample_dialogue_words = all_lines.split()[:40]
    sample_dialogue = " ".join(sample_dialogue_words) + ("..." if len(all_lines.split()) > 40 else "")

    # Build generic illustration prompt
    prompt = (
        f"Create a visually engaging digital illustration. "
        f"{ILLUSTRATION_STYLE} "
        f"Do not include any text or captions in the image. Ensure the image is a single, clear illustration. "
        f"The language of the script is {language}, and the tone is {tone}. "
        f"Scene description: {description or 'No explicit description provided.'} "
        f"The characters involved are: {detailed_characters_list or 'unspecified characters'}. " # Updated line
        f"Depict them naturally in a setting that fits the tone and context. "
        f"The mood and expressions should reflect the feel of this sample dialogue: '{sample_dialogue}'. "
    )

    return prompt

def generate_illustration_from_json(json_path: str, aspect_ratio: str = "9:16"):
    """
    Generate an illustration for one JSON script using Gemini.

    :param json_path: Path to the input JSON file.
    :param aspect_ratio: The desired aspect ratio for the generated image.
    """
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: File not found at {json_path}")
        return
    except json.JSONDecodeError:
        print(f"❌ Error: Invalid JSON format in {json_path}")
        return

    prompt = create_generic_prompt(data)
    print(f"\n🎨 Generating illustration for: {os.path.basename(json_path)}")
    print(f"➡️ Prompt for image generation:\n{prompt[:250]}...\n") # Print a snippet of the new prompt

    # --- GenerateContentConfig ---
    # Configure the response to request an image modality and set the aspect ratio.
    # We request 1:1 to get a square image, which we will then place on a 9:16 canvas.
    config = types.GenerateContentConfig(
        response_modalities=[types.Modality.IMAGE],
        image_config=types.ImageConfig(
            aspect_ratio="1:1",
        )
    )

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[prompt],
            config=config
        )
    except Exception as e:
        print(f"❌ API Error during generation for {os.path.basename(json_path)}: {e}")
        return

    # Check 1: Ensure candidates were generated at all.
    if not response.candidates:
        print(f"⚠️ **Response failed to generate candidates** for {os.path.basename(json_path)}.")
        if response.prompt_feedback.block_reason:
            print(f"   Reason: Content was blocked due to {response.prompt_feedback.block_reason}.")
import os
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
    exit()

# --- Configuration ---
INPUT_DIR = "scripts"
OUTPUT_DIR = "illustrations"
MODEL_NAME = "gemini-2.5-flash-image"

# --- Fixed illustration style description ---
ILLUSTRATION_STYLE = (
    "Illustration style: Modern flat illustration with clean lines and a soft, muted color palette. "
    "The characters have a friendly, approachable appearance with rounded features and simple, expressive faces. "
    "Details are minimal but effective, focusing on essential elements like clothing textures, subtle shadows for depth, and distinct objects. "
    "The overall aesthetic is warm, inviting, and slightly whimsical, reminiscent of casual lifestyle or explainer video graphics. "
    "The style avoids harsh outlines or heavy shading, opting for a light and airy feel. "
    "Backgrounds are simplified, using color blocks and minimal object representation to provide context without distraction."
)

## 🏗️ Core Functions

### 1. Prompt Generation

def create_generic_prompt(data: dict) -> str:
    """Create a general illustration prompt from conversation data, including character details."""

    metadata = data.get("metadata", {})
    idea = data.get("idea", {})
    dialogues = data.get("dialogue_list", [])

    title = idea.get("title", "Untitled Scene")
    description = idea.get("description", "")
    language = metadata.get("language", "Unknown language")
    tone = metadata.get("tone", "neutral")
    length = metadata.get("length", "short")

    characters = idea.get("characters", [])
    
    # --- MODIFICATION START: Extract and format detailed character descriptions ---
    character_descriptions = []
    for char in characters:
        name = char.get("name", "Unnamed")
        gender = char.get("gender", "unspecified gender")
        age = char.get("age", "unspecified age")
        character_descriptions.append(f"{name} ({gender}, {age})")
    
    detailed_characters_list = "; ".join(character_descriptions)
    # --- MODIFICATION END ---

    # Sample dialogue preview
    all_lines = " ".join([d.get("text", "") for d in dialogues])
    sample_dialogue_words = all_lines.split()[:40]
    sample_dialogue = " ".join(sample_dialogue_words) + ("..." if len(all_lines.split()) > 40 else "")

    # Build generic illustration prompt
    prompt = (
        f"Create a visually engaging digital illustration. "
        f"{ILLUSTRATION_STYLE} "
        f"Do not include any text or captions in the image. Ensure the image is a single, clear illustration. "
        f"The language of the script is {language}, and the tone is {tone}. "
        f"Scene description: {description or 'No explicit description provided.'} "
        f"The characters involved are: {detailed_characters_list or 'unspecified characters'}. " # Updated line
        f"Depict them naturally in a setting that fits the tone and context. "
        f"The mood and expressions should reflect the feel of this sample dialogue: '{sample_dialogue}'. "
    )

    return prompt

def generate_illustration_from_json(json_path: str, aspect_ratio: str = "9:16"):
    """
    Generate an illustration for one JSON script using Gemini.

    :param json_path: Path to the input JSON file.
    :param aspect_ratio: The desired aspect ratio for the generated image.
    """
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: File not found at {json_path}")
        return
    except json.JSONDecodeError:
        print(f"❌ Error: Invalid JSON format in {json_path}")
        return

    prompt = create_generic_prompt(data)
    print(f"\n🎨 Generating illustration for: {os.path.basename(json_path)}")
    print(f"➡️ Prompt for image generation:\n{prompt[:250]}...\n") # Print a snippet of the new prompt

    # --- GenerateContentConfig ---
    # Configure the response to request an image modality and set the aspect ratio.
    # We request 1:1 to get a square image, which we will then place on a 9:16 canvas.
    config = types.GenerateContentConfig(
        response_modalities=[types.Modality.IMAGE],
        image_config=types.ImageConfig(
            aspect_ratio="1:1",
        )
    )

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[prompt],
            config=config
        )
    except Exception as e:
        print(f"❌ API Error during generation for {os.path.basename(json_path)}: {e}")
        return

    # Check 1: Ensure candidates were generated at all.
    if not response.candidates:
        print(f"⚠️ **Response failed to generate candidates** for {os.path.basename(json_path)}.")
        if response.prompt_feedback.block_reason:
            print(f"   Reason: Content was blocked due to {response.prompt_feedback.block_reason}.")
        else:
            print("   Reason: Unknown failure. Check prompt safety or API logs.")
        return

    # Check 2 (The Fix): Ensure the content object exists to avoid AttributeError.
    first_candidate = response.candidates[0]
    if first_candidate.content is None:
        print(f"⚠️ **Candidate content is None** for {os.path.basename(json_path)}. Likely due to a safety block on the *output*.")
        finish_reason = first_candidate.finish_reason.name if first_candidate.finish_reason else 'Unknown'
        print(f"   Candidate Finish Reason: {finish_reason}.")
        print("   Try simplifying the scene description or checking API safety guidelines.")
        return

    # Extract and save image(s)
    for part in first_candidate.content.parts:
        if part.inline_data is not None:
            image_data = part.inline_data.data

            try:
                image = Image.open(BytesIO(image_data))
            except Exception as e:
                print(f"❌ Error opening image data for {os.path.basename(json_path)}: {e}")
                continue

            # --- Post-processing for 9:16 layout ---
            # 1. Calculate dimensions
            width, height = image.size
            # We want a 9:16 final image. Since the input is square (1:1), the width is the reference.
            # target_height = width * (16 / 9)
            target_height = int(width * (16 / 9))
            
            # 2. Create new white background image
            final_image = Image.new("RGB", (width, target_height), "white")
            
            # 3. Paste the square illustration at the top
            final_image.paste(image, (0, 0))
            
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            base_filename = os.path.splitext(os.path.basename(json_path))[0]
            output_filename = "convo_fi_" + base_filename + ".png"
            output_path = os.path.join(OUTPUT_DIR, output_filename)

            final_image.save(output_path)
            print(f"✅ Image saved to {output_path}")
            return # Assuming only one image is desired per script
        else:
            print(f"⚠️ Part has no inline_data. Text content: {part.text}")

    print(f"⚠️ No image data found in model response parts for {os.path.basename(json_path)}. Check API logs.")

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
        generate_illustration_from_json(json_path)


if __name__ == "__main__":
    main()