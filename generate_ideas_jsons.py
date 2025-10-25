import os
import json
import random
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---- CONFIG ----
OUTPUT_FILE = "ideas.json"
NUM_IDEAS = 3  # how many conversation ideas to generate

# Voice pool
VOICES = [
    {"name": "Aurora Voice", "gender": "female", "description": "Young Finnish friendly and professional voice. Perfect for conversations and narration.", "voice_id": "YSabzCJMvEHDduIDMdwV"},
    {"name": "Jussi - Strong finnish Accent", "gender": "male", "description": "Finnish young male voice with a hilariously strong accent! This simple Finnish man delivers lines in classic rally English, blending a thick Finnish accent with a silly, light-hearted tone. Perfect for projects needing a hilarious, over-the-top voice packed with charm and character. Ideal for memes, gaming, ads, or any content that thrives on a hilariously strong Finnish vibe!", "voice_id": "dlbXHgJnwobU5JdZ8F5M"},
    {"name": "Mark - ConvoAI", "gender": "male", "description": "soft and calm", "voice_id": "1SM7GgM6IMuvQlz2BwM3"},
    {"name": "ScheilaSMTy", "gender": "female", "description": "Middle aged Brazilian female. Crisp, carefully articulated, flowing with a smooth, engaging cadence that envelops listeners in its enchanting melody.", "voice_id": "cyD08lEy76q03ER1jZ7y"},
    {"name": "Rahul Bharadwaj - Highly Energetic Voice", "gender": "male", "description": "Rahul is a pen name of a middle-aged Indian with a velvety, laid-back, late-night talk show host timbre. His voice is brimming with energy, making it ideal for an engaging social media presence, ads, and chatbots.", "voice_id": "u7bRcYbD7visSINTyAT8"},
    {"name": "Grandpa Spuds Oxley", "gender": "male", "description": "A friendly grandpa who knows how to enthrall his audience with tall tales and fun adventures.", "voice_id": "NOpBlnGInO9m6vDvFkFC"},
    {"name": "Hope - Smooth talker", "gender": "female", "description": "A conversational, soft-spoken, sultry, and romantic voice with a vocal fry. Ideal for emotional characters, ASMR, self-help, reflective social media content, virtual companions, and luxury products.", "voice_id": "1SM7GgM6IMuvQlz2BwM3"},
    {"name": "CarterMotivational", "gender": "male", "description": "A young American male. Tone is a feeling when something special is about to happen. Works well for conversational purpose.", "voice_id": "6O8E1UOlJbvkhJDpV0aB"},
]

# ---- PROMPT ----
SYSTEM_PROMPT = """You are a creative idea generator for short Finnish conversations.
You must output STRICTLY in this JSON format:

{
  "metadata": {
    "language": "Finnish",
    "tone": "casual",
    "length": "short"
  },
  "ideas": [
    {
      "title": "Example Title",
      "description": "Brief summary of what the two people are talking about.",
      "characters": [
        {
          "name": "Character1",
          "gender": "female",
          "default_tone": "calm"
        },
        {
          "name": "Character2",
          "gender": "male",
          "default_tone": "excited"
        }
      ]
    }
  ]
}

Rules:
- Always output the full JSON structure exactly as shown.
- Do NOT add explanations or text outside JSON.
- Each idea must have exactly 2 characters.
- Use realistic Finnish names and situations (e.g., cafés, trams, offices, home).
- Only fill in the string values.
"""

def generate_ideas():
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Generate {NUM_IDEAS} unique ideas."}
        ],
        response_format={"type": "json_object"}
    )

    raw_json = response.choices[0].message.content
    data = json.loads(raw_json)

    # Assign voice IDs to characters
    for idea in data.get("ideas", []):
        for char in idea["characters"]:
            possible_voices = [v for v in VOICES if v["gender"].lower() == char["gender"].lower()]
            voice = random.choice(possible_voices) if possible_voices else random.choice(VOICES)
            char["voice_id"] = voice["voice_id"]

    # Ensure exact metadata keys
    final_json = {
        "metadata": {
            "language": "Finnish",
            "tone": "casual",
            "length": "short"
        },
        "ideas": data["ideas"]
    }

    return final_json

if __name__ == "__main__":
    print("🪄 Generating conversation ideas...")
    result = generate_ideas()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ {NUM_IDEAS} ideas saved to {OUTPUT_FILE}")
