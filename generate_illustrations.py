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
    "A playful, modern doodle-style 2D illustration with bold, thick, uniform black outlines "
    "and flat, naturalistic colors. No gradients, no 3D, no complex shading. "
    "Characters have friendly, realistically proportioned bodies at a consistent scale "
    "relative to each other and the environment. "
    "Soft pastel-leaning color palette. High quality vector-art style. "
    "No text, labels, words, letters, speech bubbles, or thought bubbles anywhere in the image."
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
    names = []
    char_lines = []
    for c in characters:
        name = c.get("name", "Unnamed")
        names.append(name)
        gender = c.get("gender", "")
        age = c.get("age", "")
        appearance = c.get("appearance", "")
        line = f"  • {name}: {gender}, {age}"
        if appearance:
            line += f". {appearance}"
        char_lines.append(line)
    char_block = "\n".join(char_lines) if char_lines else "unspecified characters"

    n = len(names)

    # Use ONLY the scene narrative for the image — never the dialogue or any quoted phrases.
    # In series mode the description has extra blocks (target phrases, speech styles, direction)
    # appended after a blank line; those are for the scriptwriter, NOT the illustrator. Keeping
    # them would make the model render speech bubbles with that text, so we take the first block.
    scene = (description or "").split("\n\n")[0].strip()

    # Environment guidance
    setting_clause = (
        f"Setting: {ambient_setting}. " if ambient_setting else ""
    )

    # Build prompt — headcount is THE MOST IMPORTANT constraint, so it goes first and last.
    prompt = (
        f"STRICT HEADCOUNT: Draw EXACTLY {n} {'person' if n == 1 else 'people'} — "
        f"{', '.join(names)}. No more, no less. No extra people, no background crowd, "
        f"no duplicated characters.\n\n"
        f"{ILLUSTRATION_STYLE}\n\n"
        f"Scene: {scene or 'A simple moment between the characters.'}\n"
        f"{setting_clause}\n"
        f"Characters (each must look visually DISTINCT — different hair, clothing, build):\n"
        f"{char_block}\n\n"
        f"Draw a single illustration of one moment. Rich background with environmental details "
        f"(furniture, plants, props) in the same flat 2D style. Background contains OBJECTS ONLY, "
        f"no additional people. Convey interaction through gesture and expression. "
        f"Tone: {tone}.\n\n"
        f"REMINDER: The image must contain EXACTLY {n} {'person' if n == 1 else 'people'}, not one more."
    )

    return prompt

def _render_once(contents, config, label):
    """Run one image generation and return a PIL Image, or None on failure/block."""
    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=contents, config=config)
    except Exception as e:
        print(f"❌ API Error during generation for {label}: {e}")
        return None
    if not response.candidates:
        reason = getattr(getattr(response, "prompt_feedback", None), "block_reason", None)
        print(f"⚠️ No candidates for {label}" + (f" (blocked: {reason})" if reason else ""))
        return None
    cand = response.candidates[0]
    if cand.content is None:
        fr = cand.finish_reason.name if cand.finish_reason else "Unknown"
        print(f"⚠️ Candidate content is None for {label} (finish: {fr}).")
        return None
    for part in cand.content.parts:
        if part.inline_data is not None:
            try:
                return Image.open(BytesIO(part.inline_data.data))
            except Exception as e:
                print(f"❌ Error opening image data for {label}: {e}")
                return None
    return None


def count_people(image) -> int:
    """Ask a vision model how many human figures are in the image. Returns -1 on error.

    Duplicates of the same character count as separate figures — that's what lets us
    detect (and reject) an accidentally-duplicated character.
    """
    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                "Count the distinct human figures (people/characters) visible in this illustration. "
                "If the same person appears more than once, count each appearance separately. "
                "Reply with ONLY a single integer.",
                image,
            ],
        )
        import re
        m = re.search(r"\d+", resp.text or "")
        return int(m.group()) if m else -1
    except Exception as e:
        print(f"   ⚠️  headcount check failed: {e}")
        return -1


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
    # Keep (name, image) pairs so each reference can be labelled — this stops the model from
    # duplicating a character or inventing extra people.
    ref_pairs = []
    for c in data.get("idea", {}).get("characters", []):
        ref_path = c.get("reference_image")
        if ref_path and os.path.exists(ref_path):
            try:
                ref_pairs.append((c.get("name", "Character"), Image.open(ref_path)))
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

    # Build request contents — prepend LABELLED reference portraits as identity anchors.
    # Each portrait is one specific person; naming them and stating the exact count prevents
    # the model from duplicating a character or adding extra bystanders.
    if ref_pairs:
        n = len(ref_pairs)
        contents = [
            f"Below are {n} reference portrait(s), one per character. Each defines the EXACT "
            f"appearance (face, hair, clothing) of ONE person. Render each of these {n} people "
            f"EXACTLY ONCE in the scene and include NO other people — no duplicates, no extra "
            f"figures, no background crowd:",
        ]
        for name, img in ref_pairs:
            contents.append(f"This is {name}:")
            contents.append(img)
        contents.append(prompt)
    else:
        contents = [prompt]

    label = os.path.basename(json_path)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    base_filename = os.path.splitext(label)[0]
    output_path = os.path.join(OUTPUT_DIR, "conversation_" + base_filename + ".png")

    # Expected head-count = number of named characters. Generate, verify the count with a vision
    # check, and retry if the model duplicated a character or added extra people.
    expected = len(data.get("idea", {}).get("characters", []))
    MAX_ATTEMPTS = 6
    best_image, best_diff = None, None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        # On retries, prepend a correction hint to help the model self-correct
        if attempt > 1 and best_diff is not None:
            retry_hint = (
                f"IMPORTANT: Your previous illustration had the WRONG number of people. "
                f"Draw EXACTLY {expected} people, no more, no less. "
                f"Only these {expected} characters: {', '.join(n for n in [c.get('name','') for c in data.get('idea',{}).get('characters',[])] if n)}."
            )
            retry_contents = [retry_hint] + contents if not isinstance(contents[0], Image.Image) else contents[:1] + [retry_hint] + contents[1:]
        else:
            retry_contents = contents

        image = _render_once(retry_contents, config, label)
        if image is None:
            continue
        if expected <= 0:
            best_image = image
            break
        count = count_people(image)
        if count == expected:
            image.save(output_path)
            print(f"✅ Image saved to {output_path} (headcount {count} ✓, attempt {attempt})")
            return True
        diff = abs(count - expected) if count >= 0 else 99
        print(f"   🔁 attempt {attempt}/{MAX_ATTEMPTS}: found {count} people, expected {expected} — regenerating")
        if best_diff is None or diff < best_diff:
            best_image, best_diff = image, diff

    if best_image is not None:
        best_image.save(output_path)
        note = "" if expected <= 0 else f" (could not hit exactly {expected} people in {MAX_ATTEMPTS} tries — saved closest)"
        print(f"⚠️ Saved best-effort image to {output_path}{note}")
        return True

    print(f"⚠️ No image produced for {label}.")
    return False

def _normalize_slug(arg: str) -> str:
    """Accept a slug, a script filename, or an illustration name and return the script slug."""
    name = os.path.basename(arg)
    if name.endswith(".json"):
        name = name[:-5]
    if name.endswith(".png"):
        name = name[:-4]
    if name.startswith("conversation_"):
        name = name[len("conversation_"):]
    return name


def main():
    """Generate illustrations for scripts.

    Usage:
        python generate_illustrations.py                 # all scripts in scripts/
        python generate_illustrations.py mit-kello-on    # only this one (regenerate its image)
        python generate_illustrations.py a b c           # only these scripts
    """
    os.makedirs(INPUT_DIR, exist_ok=True)

    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if args:
        # Targeted mode — regenerate only the specified script(s).
        files = []
        for a in args:
            slug = _normalize_slug(a)
            path = os.path.join(INPUT_DIR, f"{slug}.json")
            if not os.path.exists(path):
                print(f"❌ Script not found: {path}")
                sys.exit(1)
            files.append(f"{slug}.json")
        print(f"🎯 Regenerating {len(files)} illustration(s): {', '.join(_normalize_slug(f) for f in files)}")
    else:
        # Default — all scripts.
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