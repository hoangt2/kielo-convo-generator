import os
import json
import random
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize the Gemini client (uses GEMINI_API_KEY from .env)
# Note: You may need to replace 'genai.Client()' with 'google.genai.Client()' depending on your exact library version.
try:
    client = genai.Client()
except AttributeError:
    print("Warning: Could not initialize genai.Client. Check your library installation.")
    client = None # Handle case where client initialization fails

# ---- CONFIG ----
OUTPUT_FILE = "podcast_ideas.json"
NUM_IDEAS = 3  # how many podcast ideas to generate
MODEL_NAME = "gemini-2.5-flash"  # A robust model for strict JSON output

# Voice pool (Keeping the original for character assignment)
VOICES = [
    {
        "name": "Aurora Voice",
        "gender": "female",
        "description": "Young Finnish friendly and professional voice. Perfect for conversations and narration.",
        "voice_id": "YSabzCJMvEHDduIDMdwV",
    },
    {
        "name": "Jussi - Strong finnish Accent",
        "gender": "male",
        "description": "Finnish young male voice with a hilariously strong accent! This simple Finnish man delivers lines in classic rally English, blending a thick Finnish accent with a silly, light-hearted tone. Perfect for projects needing a hilarious, over-the-top voice packed with charm and character. Ideal for memes, gaming, ads, or any content that thrives on a hilariously strong Finnish vibe!",
        "voice_id": "dlbXHgJnwobU5JdZ8F5M",
    },
    {
        "name": "Mark - ConvoAI",
        "gender": "male",
        "description": "soft and calm",
        "voice_id": "1SM7GgM6IMuvQlz2BwM3",
    },
]

# ---- PROMPT MODIFICATIONS ----
SYSTEM_PROMPT = """You are a highly creative script idea generator for short (3-5 minute) educational podcasts aimed at absolute beginners learning Finnish.
The ideas must focus on either a single, highly useful beginner Finnish tip (e.g., a grammar shortcut, a cultural concept, or a pronunciation trick) OR a small set of immediately useful phrases for a specific situation.
The podcast can be a 'Solo Host' (1 character) or 'Host and Guest' (2 characters).
You must output STRICTLY in JSON format.

Rules:
- Each idea must be creative, fun, and immediately useful for a beginner.
- Use realistic Finnish names and describe the character roles (Host, Guest, or Solo Presenter).
- The 'title' should be catchy and podcast-friendly.
- Only fill in the string values.
"""

# Define the JSON schema for strict output enforcement (Modified to allow 1 or 2 characters and different metadata)
response_schema = types.Schema(
    type="object",
    properties={
        "metadata": types.Schema(
            type="object",
            properties={
                "target_audience": types.Schema(type="string", description="e.g., Absolute Beginner"),
                "duration": types.Schema(type="string", description="e.g., 3-5 minutes"),
                "format": types.Schema(type="string", description="e.g., Solo or Host/Guest"),
            },
            required=["target_audience", "duration", "format"],
        ),
        "podcast_ideas": types.Schema( # Renamed 'ideas' to 'podcast_ideas' for clarity
            type="array",
            items=types.Schema(
                type="object",
                properties={
                    "title": types.Schema(type="string", description="Catchy episode title."),
                    "concept": types.Schema(type="string", description="Brief summary of the tip or phrases taught."),
                    "characters": types.Schema(
                        type="array",
                        min_items=1, # Allow 1 or 2 characters
                        max_items=2,
                        items=types.Schema(
                            type="object",
                            properties={
                                "name": types.Schema(type="string"),
                                "role": types.Schema(type="string", description="Host, Guest, or Solo Presenter"),
                                "gender": types.Schema(type="string"),
                                "default_tone": types.Schema(type="string"),
                            },
                            required=["name", "role", "gender", "default_tone"],
                        ),
                    ),
                },
                required=["title", "concept", "characters"],
            ),
        ),
    },
    required=["metadata", "podcast_ideas"],
)


# Example JSON structure for the model to follow (Updated for the new schema)
JSON_EXAMPLE = """
{
  "metadata": {
    "target_audience": "Absolute Beginner",
    "duration": "3-5 minutes",
    "format": "Mixed (Solo or Host/Guest)"
  },
  "podcast_ideas": [
    {
      "title": "Sisu, Sauna, and Saying 'Kiitos'!",
      "concept": "Teaches the basic phrase 'Kiitos' (Thank You) and culturally relevant situations to use it, emphasizing that Finns are generally reserved but appreciate politeness.",
      "characters": [
        {
          "name": "Aino",
          "role": "Solo Presenter",
          "gender": "female",
          "default_tone": "friendly and instructional"
        }
      ]
    },
    {
      "title": "The Magic of 'Moi'",
      "concept": "Host and Guest discuss the all-purpose greeting 'Moi' and 'Moi Moi', explaining how it's used for both 'Hi' and 'Bye' in casual settings.",
      "characters": [
        {
          "name": "Leo",
          "role": "Host",
          "gender": "male",
          "default_tone": "energetic"
        },
        {
          "name": "Elina",
          "role": "Guest",
          "gender": "female",
          "default_tone": "calm and informative"
        }
      ]
    }
  ]
}
"""

def generate_ideas():
    if not client:
        print("Cannot run generation without a valid Gemini Client.")
        return None

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=response_schema
    )

    full_prompt = (
        f"Generate {NUM_IDEAS} unique, creative, and highly useful podcast ideas for Finnish beginners, following the new schema exactly:\n"
        f"{JSON_EXAMPLE}"
    )

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[full_prompt],
        config=config,
    )

    raw_json = response.text
    data = json.loads(raw_json)

    # Assign voice IDs to characters
    for idea in data.get("podcast_ideas", []): # Changed key to 'podcast_ideas'
        for char in idea["characters"]:
            # Logic to select a voice based on gender
            possible_voices = [v for v in VOICES if v["gender"].lower() == char["gender"].lower()]
            voice = random.choice(possible_voices) if possible_voices else random.choice(VOICES)
            char["voice_id"] = voice["voice_id"]

    return data

if __name__ == "__main__":
    print("🪄 Generating creative Finnish beginner podcast ideas using Gemini...")
    try:
        result = generate_ideas()
        if result:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"✅ {NUM_IDEAS} podcast ideas saved to {OUTPUT_FILE}")
    except Exception as e:
        print(f"❌ An error occurred during generation: {e}")
        print("Please ensure the 'google-genai' library is installed and 'GEMINI_API_KEY' is set.")