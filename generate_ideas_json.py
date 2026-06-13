import os
import json
import random
import sys
from google import genai
from google.genai import types
from dotenv import load_dotenv
from cefr_levels import is_cefr_level, normalize_level

# Load environment variables
load_dotenv()

# Initialize the Gemini client (uses GEMINI_API_KEY from .env)
try:
    client = genai.Client()
except Exception as e:
    print(f"❌ Error initializing Gemini Client: {e}")
    client = None

# ---- SHARED CONFIGURATION ----
MODEL_NAME_CONVERSATION = "gemini-2.5-pro"  # Robust for strict, complex output
MODEL_NAME_PODCAST = "gemini-2.5-pro"      # Good for instructional, fast output
NUM_CONVERSATION_IDEAS = 1
NUM_PODCAST_IDEAS = 3

# Consolidated Voice Pool (Used for CONVERSATIONS only)
VOICES = [
    {
        "name": "Aurora Voice",
        "gender": "female",
        "age": "young adult",
        "description": "Young Finnish friendly and professional voice. Perfect for conversations and narration.",
        "voice_id": "YSabzCJMvEHDduIDMdwV",
    },
    {
        "name": "Jussi - Strong finnish Accent",
        "gender": "male",
        "age": "young adult",
        "description": "Finnish young male voice with a hilariously strong accent! This simple Finnish man delivers lines in classic rally English, blending a thick Finnish accent with a silly, light-hearted tone.",
        "voice_id": "dlbXHgJnwobU5JdZ8F5M",
    },
    {
        "name": "Mark - ConvoAI",
        "gender": "male",
        "age": "adult",
        "description": "soft and calm",
        "voice_id": "1SM7GgM6IMuvQlz2BwM3",
    },
    {
        "name": "ScheilaSMTy",
        "gender": "female",
        "description": "Middle aged Brazilian female. Crisp, carefully articulated, flowing with a smooth, engaging cadence.",
        "voice_id": "cyD08lEy76q03ER1jZ7y",
    },
    {
        "name": "Rahul Bharadwaj - Highly Energetic Voice",
        "gender": "male",
        "age": "middle-aged",
        "description": "Middle-aged Indian with a velvety, laid-back timbre, brimming with energy.",
        "voice_id": "u7bRcYbD7visSINTyAT8",
    },
    {
        "name": "Grandpa Spuds Oxley",
        "gender": "male",
        "age": "senior",
        "description": "A friendly grandpa who knows how to enthrall his audience with tall tales and fun adventures.",
        "voice_id": "NOpBlnGInO9m6vDvFkFC",
    },
    {
        "name": "Hope - Smooth talker",
        "gender": "female",
        "age": "adult",
        "description": "A conversational, soft-spoken, sultry, and romantic voice with a vocal fry.",
        "voice_id": "OYTbf65OHHFELVut7v2H",
    },
    {
        "name": "Grandma Rachel",
        "gender": "female",
        "age": "senior",
        "description": "A friendly grandma who knows how to enthrall her audience with tall tales and fun adventures.",
        "voice_id": "0rEo3eAjssGDUCXHYENf",
    },
    {
        "name": "Gretchen - Valley Girl & Ditzy",
        "gender": "female",
        "age": "kid",
        "description": "Your favorite valley & ditzy girl is perfect for social media, commercials, get ready with me, outfit of the day, narration, character, talking with friends, and Gen Z.",
        "voice_id": "JVVJ6VsnUPJAdfGmEBGP",
    },
    {
        "name": "Brayden - Conversational Older Teen",
        "gender": "male",
        "age": "teenager",
        "description": "A deep-voiced male teenager. Perfect for conversations.",
        "voice_id": "3XOBzXhnDY98yeWQ3GdM",
    },
]

# --- PODCAST-SPECIFIC VOICE LIST ---
ALLOWED_PODCAST_CHARACTERS = [
    {
        "name": "Aurora",
        "gender": "female",
        "age": "young adult",
        "voice_id": "YSabzCJMvEHDduIDMdwV",
    },
    {
        "name": "Jussi",
        "gender": "male",
        "age": "young adult",
        "voice_id": "dlbXHgJnwobU5JdZ8F5M",
    },
]

# --- VOICE ASSIGNMENT HELPERS ---

def normalize_age(age_str):
    """Normalize age strings to match VOICES age categories."""
    age = age_str.lower().strip()
    
    # Check broader categories FIRST (decades/descriptive) before single digits
    # to prevent "70s" matching "7" in kids, etc.
    
    # Senior/elderly patterns (check FIRST — most specific decade matches)
    if any(term in age for term in ["senior", "elderly", "old", "grandma", "grandpa", "retired", "eläkeläinen",
                                     "50s", "60s", "70s", "80s", "90s"]):
        return "senior"
    
    # Adult/middle-aged patterns
    if any(term in age for term in ["middle-aged", "middle aged", "30s", "40s"]):
        return "adult"
    
    # Young adult patterns
    if any(term in age for term in ["young adult", "20s"]):
        return "young adult"
    
    # Teenager patterns
    if any(term in age for term in ["teen", "teens"]):
        return "teenager"
    
    # Now try specific number matching (extract numeric age)
    import re
    numbers = re.findall(r'\d+', age)
    if numbers:
        num_age = int(numbers[0])
        if num_age <= 12:
            return "kid"
        elif num_age <= 19:
            return "teenager"
        elif num_age <= 29:
            return "young adult"
        elif num_age <= 49:
            return "adult"
        else:
            return "senior"
    
    # Descriptive fallbacks
    if any(term in age for term in ["kid", "child", "boy", "girl"]):
        return "kid"
    if "young" in age:
        return "young adult"
    if "adult" in age:
        return "adult"
    
    return age  # Return as-is if no match

def assign_voice_ids(ideas_list, key="characters"):
    """
    Assigns a voice_id from the *full* VOICES pool based on gender and age.
    Used for Conversation Ideas.
    """
    for idea in ideas_list:
        for char in idea.get(key, []):
            gender = char.get("gender", "unknown").lower()
            age = normalize_age(char.get("age", ""))
            
            # Prefer voices that match both gender and age
            matching = [v for v in VOICES if v.get("gender", "").lower() == gender and normalize_age(v.get("age", "")) == age]
            
            # Fallback to gender only
            if not matching:
                matching = [v for v in VOICES if v.get("gender", "").lower() == gender]
            
            # Fallback to any voice
            voice = random.choice(matching) if matching else random.choice(VOICES)
            char["voice_id"] = voice["voice_id"]
    return ideas_list

# **NEW FUNCTION FOR PODCAST VOICES**
def assign_podcast_voice_ids(ideas_list, key="characters"):
    """
    Assigns voice_id ONLY from the ALLOWED_PODCAST_CHARACTERS list.
    It matches the character's *name* generated by the LLM to the voice_id.
    """
    # Create a mapping for quick lookup: Name -> voice_id
    voice_map = {v["name"].lower(): v["voice_id"] for v in ALLOWED_PODCAST_CHARACTERS}
    
    for idea in ideas_list:
        for char in idea.get(key, []):
            char_name = char.get("name", "").lower()
            
            # Find the voice ID based on the character's name generated by the model
            voice_id = voice_map.get(char_name)
            
            # Assign the voice_id if a match is found
            if voice_id:
                char["voice_id"] = voice_id
            else:
                # Fallback: If the model uses a name not in the list (violating the prompt), 
                # assign a random voice from the *allowed* list to ensure a voice_id is present.
                # This helps prevent runtime errors, but the prompt should ideally prevent this.
                print(f"⚠️ Warning: Character name '{char_name}' not found in allowed podcast voices. Assigning random allowed voice.")
                char["voice_id"] = random.choice(ALLOWED_PODCAST_CHARACTERS)["voice_id"]
                
    return ideas_list

# --- 1. CONVERSATION IDEAS LOGIC (No Change) ---

# Schema for Conversations (2 characters strictly)
CONVERSATION_SCHEMA = types.Schema(
    type="object",
    properties={
        "metadata": types.Schema(
            type="object",
            properties={
                "language": types.Schema(type="string"),
                "tone": types.Schema(type="string"),
                "length": types.Schema(type="string"),
            },
            required=["language", "tone", "length"],
        ),
        "ideas": types.Schema( # Key: 'ideas'
            type="array",
            items=types.Schema(
                type="object",
                properties={
                    "title": types.Schema(type="string"),
                    "description": types.Schema(type="string"),
                    "ambient_setting": types.Schema(type="string", enum=[
                        "bus", "cafe", "street", "park", "office", "supermarket",
                        "train", "restaurant", "home_kitchen", "school",
                        "gym", "library", "hospital", "airport", "beach",
                        "quiet"
                    ], description="The ambient sound category for the conversation setting. Use 'quiet' for neutral/silent settings."),
                    "characters": types.Schema(
                        type="array",
                        min_items=2,
                        max_items=2,
                        items=types.Schema(
                            type="object",
                            properties={
                                "name": types.Schema(type="string"),
                                "gender": types.Schema(type="string"),
                                "age": types.Schema(type="string"),
                                "default_tone": types.Schema(type="string"),
                            },
                            required=["name", "gender", "age", "default_tone"],
                        ),
                    ),
                },
                required=["title", "description", "ambient_setting", "characters"],
            ),
        ),
    },
    required=["metadata", "ideas"],
)

CONVERSATION_SYSTEM_PROMPT = """You are a creative idea generator for short Finnish conversations.
You must output STRICTLY in JSON format.

Rules:
- Each idea can have 2 or more characters.
- One conversation must not have the same character more than once.
- Dialogues must be suitable for beginners learning Finnish.
- Each idea must be creative, fun, and immediately useful for a beginner.
- Use realistic Finnish names and situations (e.g., cafés, trams, offices, home).
- The gender and age of each character must be specified and matched to a voice.
- **CRITICAL — Choosing the right character relationship for the topic:**
  Think carefully about WHO would realistically have this conversation. Match the character relationship to the topic:
  * For SERVICE or INSTITUTIONAL topics (e.g., enrolling in a course, getting a driver's license, buying a ticket, visiting a doctor, checking into a hotel, opening a bank account, returning an item, asking for directions), the characters MUST be strangers in a professional context — such as a customer and a clerk, a student and an advisor, a patient and a receptionist, a passenger and a driver. Do NOT use friends or family for these topics.
  * For SOCIAL or EVERYDAY topics (e.g., weekend plans, hobbies, cooking, complaining about weather, catching up), use friends, colleagues, classmates, or family members.
  * For MIXED topics, use your best judgment — but always prefer the most realistic and natural pairing.
- In the 'description' field, clearly indicate the relationship between characters (e.g., "asiakas ja postivirkailija" for strangers, or "kaksi ystävää" for friends). This helps the dialogue writer know whether characters should use each other's names.
- For 'ambient_setting': choose the most appropriate ambient sound category for where the conversation takes place. Available categories:
  * "bus" — city bus interior (engine, announcements, passengers)
  * "cafe" — café/coffee shop (clinking cups, espresso machine, soft chatter)
  * "street" — city street (traffic, pedestrians, urban sounds)
  * "park" — outdoor park (birds, wind, nature)
  * "office" — office environment (keyboard typing, printer, muffled conversations)
  * "supermarket" — grocery store (carts, beeping, announcements)
  * "train" — train/metro (rails, announcements, doors)
  * "restaurant" — restaurant (dishes, conversation buzz, cutlery)
  * "home_kitchen" — home kitchen (cooking sounds, fridge, water)
  * "school" — school/classroom (hallway noise, bell)
  * "gym" — gym/sports (equipment, sneakers, music)
  * "library" — quiet library (pages turning, whispers)
  * "hospital" — hospital/clinic (beeping, footsteps, PA system)
  * "airport" — airport (announcements, rolling luggage, crowd)
  * "beach" — beach/waterfront (waves, seagulls, wind)
  * "quiet" — for phone calls, quiet rooms, or settings with no distinct ambient sound
- Only fill in the string values.
"""

def generate_conversation_ideas(num_ideas=NUM_CONVERSATION_IDEAS, topic=None, level=None):
    if topic:
        print(f"🪄 Generating {num_ideas} general conversation ideas about '{topic}'...")
    else:
        print(f"🪄 Generating {num_ideas} general conversation ideas...")
    if not client: return None

    config = types.GenerateContentConfig(
        system_instruction=CONVERSATION_SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=CONVERSATION_SCHEMA
    )

    prompt_text = f"Generate {num_ideas} unique ideas for short Finnish conversations"
    if topic:
        prompt_text += f" about the topic '{topic}'"
    if level:
        prompt_text += (
            f". The conversations are for CEFR level {level} learners — choose scenarios "
            f"whose vocabulary and situations suit that level"
        )
    prompt_text += ", following the specified JSON structure exactly."

    full_prompt = (
        prompt_text
    )

    response = client.models.generate_content(
        model=MODEL_NAME_CONVERSATION,
        contents=[full_prompt],
        config=config,
    )

    data = json.loads(response.text)
    data["ideas"] = assign_voice_ids(data.get("ideas", []))
    if level:
        data.setdefault("metadata", {})["language_level"] = level
    return data, "ideas.json"

# --- 2. PODCAST IDEAS LOGIC (Minor Changes to System Prompt and Function) ---

# Schema for Podcast Ideas (1 or 2 characters, different metadata keys)
PODCAST_SCHEMA = types.Schema(
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
        "podcast_ideas": types.Schema( # Key: 'podcast_ideas'
            type="array",
            items=types.Schema(
                type="object",
                properties={
                    "title": types.Schema(type="string", description="Catchy episode title."),
                    "concept": types.Schema(type="string", description="Brief summary of the tip or phrases taught."),
                    "characters": types.Schema(
                        type="array",
                        min_items=1, # Min 1 character
                        max_items=2, # Max 2 characters
                        items=types.Schema(
                            type="object",
                            properties={
                                "name": types.Schema(type="string"),
                                "role": types.Schema(type="string", description="Host, Guest, or Solo Presenter"),
                                "gender": types.Schema(type="string"),
                                "age": types.Schema(type="string"),
                                "default_tone": types.Schema(type="string"),
                            },
                            required=["name", "role", "gender", "age", "default_tone"],
                        ),
                    ),
                },
                required=["title", "concept", "characters"],
            ),
        ),
    },
    required=["metadata", "podcast_ideas"],
)

# Updated System Prompt to explicitly mention allowed characters to guide the LLM
PODCAST_SYSTEM_PROMPT = f"""You are a highly creative script idea generator for short (3-5 minute) educational podcasts aimed at absolute beginners learning Finnish.
The ideas must focus on either a single, highly useful beginner Finnish tip (e.g., a grammar shortcut, a cultural concept, or a pronunciation trick) OR a small set of immediately useful phrases for a specific situation.
The podcast can be a 'Solo Host' (1 character) or 'Host and Guest' (2 characters).
You must output STRICTLY in JSON format.

Rules:
- Each idea must be creative, fun, and immediately useful for a beginner.
- Use realistic Finnish names and describe the character roles (Host, Guest, or Solo Presenter).
-- The gender and age of each character must be specified and matched to a voice.
- **CRITICAL:** The character names in the 'characters' array MUST be chosen ONLY from this approved list of names: {', '.join([c['name'] for c in ALLOWED_PODCAST_CHARACTERS])}.
- The 'title' should be catchy and podcast-friendly.
- Only fill in the string values.
"""

def generate_podcast_ideas(num_ideas=NUM_PODCAST_IDEAS, topic=None, level=None):
    if topic:
        print(f"🪄 Generating {num_ideas} podcast lesson ideas about '{topic}'...")
    else:
        print(f"🪄 Generating {num_ideas} podcast lesson ideas...")
    if not client: return None

    config = types.GenerateContentConfig(
        system_instruction=PODCAST_SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=PODCAST_SCHEMA
    )

    prompt_text = f"Generate {num_ideas} unique, creative, and highly useful podcast ideas for Finnish beginners"
    if topic:
        prompt_text += f" about the topic '{topic}'"
    if level:
        prompt_text += (
            f". The lessons target CEFR level {level} learners — pick tips and phrases "
            f"whose Finnish content suits that level"
        )
    prompt_text += ", following the specified JSON structure exactly. Remember to use only the allowed character names."

    full_prompt = (
        prompt_text
    )

    response = client.models.generate_content(
        model=MODEL_NAME_PODCAST,
        contents=[full_prompt],
        config=config,
    )

    data = json.loads(response.text)
    # **MODIFICATION HERE**: Use the new specific voice assignment function
    data["podcast_ideas"] = assign_podcast_voice_ids(data.get("podcast_ideas", []))
    if level:
        data.setdefault("metadata", {})["language_level"] = level
    return data, "podcast_ideas.json"

# --- MAIN EXECUTION (No Change) ---

def main():
    if not client:
        print("🛑 Cannot run generation. Please ensure 'google-genai' is installed and 'GEMINI_API_KEY' is set in your .env file.")
        return

    # Check for command-line arguments
    # Usage: python generate_ideas_json.py [podcast|conversation] [number_of_ideas] [CEFR level] [topic]

    mode = 'conversation'
    num_ideas = None
    topic = None
    level = None

    # Simple argument parsing
    for arg in sys.argv[1:]:
        if arg.lower() == 'podcast':
            mode = 'podcast'
        elif arg.isdigit():
            num_ideas = int(arg)
        elif is_cefr_level(arg):
            level = normalize_level(arg)
        else:
            topic = arg

    if level:
        print(f"ℹ️  Targeting CEFR level: {level}")

    if mode == 'podcast':
        count = num_ideas if num_ideas else NUM_PODCAST_IDEAS
        result, output_file = generate_podcast_ideas(count, topic, level)
        idea_count = count
    else:
        # Default behavior: generate conversations
        count = num_ideas if num_ideas else NUM_CONVERSATION_IDEAS
        result, output_file = generate_conversation_ideas(count, topic, level)
        idea_count = count

    if result:
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"✅ {idea_count} ideas saved to **{output_file}**")
        except Exception as e:
            print(f"❌ An error occurred while saving the file: {e}")

if __name__ == "__main__":
    main()