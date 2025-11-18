import os
import json
import random
import sys
from datetime import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Load environment variables
load_dotenv()

# Initialize the Gemini client (uses GEMINI_API_KEY from .env)
try:
    client = genai.Client()
except Exception as e:
    print(f"❌ Error initializing Gemini Client: {e}")
    client = None

# Google Sheets configuration
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_ID")
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
CONVERSATION_SHEET = "Conversations"
PODCAST_SHEET = "Podcasts"

# ---- SHARED CONFIGURATION ----
MODEL_NAME_CONVERSATION = "gemini-2.5-pro"  # Robust for strict, complex output
MODEL_NAME_PODCAST = "gemini-2.5-pro"      # Good for instructional, fast output
NUM_CONVERSATION_IDEAS = 10
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
        "voice_id": "1SM7GgM6IMuvQlz2BwM3",
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

# --- GOOGLE SHEETS HELPERS ---

def get_sheets_service():
    """Initialize Google Sheets service for reading."""
    try:
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            print(f"⚠️ Service account file not found: {SERVICE_ACCOUNT_FILE}")
            return None
        
        creds = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        service = build("sheets", "v4", credentials=creds)
        return service
    except Exception as e:
        print(f"⚠️ Warning: Could not initialize Google Sheets service: {e}")
        return None

def get_existing_titles(sheet_name):
    """Get all existing titles from a Google Sheet to avoid duplicates."""
    if not SPREADSHEET_ID:
        print("⚠️ GOOGLE_SHEETS_ID not set in .env, skipping duplicate check")
        return []
    
    service = get_sheets_service()
    if not service:
        return []
    
    try:
        # Fetch Title and Description columns so we can avoid similar ideas
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=SPREADSHEET_ID, range=f"{sheet_name}!A2:B")
            .execute()
        )
        values = result.get("values", [])
        combined = []
        for row in values:
            title = row[0].strip() if len(row) > 0 and row[0] else ""
            desc = row[1].strip() if len(row) > 1 and row[1] else ""
            if title:
                if desc:
                    combined.append(f"{title} — {desc}")
                else:
                    combined.append(title)
        print(f"📊 Found {len(combined)} existing title+description rows in '{sheet_name}' sheet")
        return combined
    except Exception as e:
        print(f"⚠️ Warning: Could not fetch existing titles: {e}")
        return []

# --- VOICE ASSIGNMENT HELPERS ---

def assign_voice_ids(ideas_list, key="characters"):
    """
    Assigns a voice_id from the *full* VOICES pool based on gender and age.
    Ensures:
    1. Each character's voice matches their gender and age
    2. All characters in one conversation have different voice_ids
    Used for Conversation Ideas.
    """
    for idea in ideas_list:
        used_voice_ids = set()
        characters = idea.get(key, [])
        
        for char in characters:
            gender = char.get("gender", "unknown").lower()
            age = char.get("age", "").lower()
            
            # Prefer voices that match both gender and age, then gender only, then any voice
            matching = []
            if age:
                matching = [v for v in VOICES if v.get("gender", "").lower() == gender and v.get("age", "").lower() == age]
            if not matching:
                matching = [v for v in VOICES if v.get("gender", "").lower() == gender]
            if not matching:
                matching = VOICES
            
            # Filter out already used voice IDs in this conversation
            available_voices = [v for v in matching if v["voice_id"] not in used_voice_ids]
            
            # If all matching voices are used, fall back to any unused voice
            if not available_voices:
                available_voices = [v for v in VOICES if v["voice_id"] not in used_voice_ids]
            
            voice = random.choice(available_voices) if available_voices else random.choice(VOICES)
            char["voice_id"] = voice["voice_id"]
            used_voice_ids.add(voice["voice_id"])
    
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
                    "characters": types.Schema(
                        type="array",
                        min_items=2,
                        items=types.Schema(
                            type="object",
                            properties={
                                "name": types.Schema(type="string"),
                                "role": types.Schema(type="string", description="e.g., Speaker 1, Speaker 2, Customer, Shopkeeper"),
                                "gender": types.Schema(type="string"),
                                "age": types.Schema(type="string"),
                                "default_tone": types.Schema(type="string"),
                            },
                            required=["name", "role", "gender", "age", "default_tone"],
                        ),
                    ),
                },
                required=["title", "description", "characters"],
            ),
        ),
    },
    required=["metadata", "ideas"],
)

CONVERSATION_SYSTEM_PROMPT = """You are a creative idea generator for short Finnish conversations.
You must output STRICTLY in JSON format.

Rules:
- Each idea can have 2 or more characters.
- **CRITICAL:** Each character MUST have a distinct role (e.g., Speaker 1, Speaker 2, Customer, Shopkeeper, Friend, Parent, etc.) so that generate_scripts.py can identify who is speaking.
- One conversation must not have the same character with the same voice id more than once.
- The gender and age of each character must be specified and matched to a voice in the voice pool: {VOICES} 
- Dialogues must be suitable for beginners learning Finnish.
- Each idea must be creative, fun, and immediately useful for a beginner.
- Use realistic Finnish names and situations (e.g., cafés, trams, offices, home).
- Only fill in the string values.
"""

def generate_conversation_ideas(existing_titles=None):
    print(f"🪄 Generating {NUM_CONVERSATION_IDEAS} general conversation ideas...")
    if not client: return None
    
    if existing_titles is None:
        existing_titles = []

    config = types.GenerateContentConfig(
        system_instruction=CONVERSATION_SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=CONVERSATION_SCHEMA
    )

    existing_titles_str = "\n".join([f"- {title}" for title in existing_titles]) if existing_titles else "None"
    
    full_prompt = (
        f"Generate {NUM_CONVERSATION_IDEAS} unique ideas for short Finnish conversations, following the specified JSON structure exactly.\n\n"
        f"**IMPORTANT:** Do NOT create conversations with these titles or descriptions (already exist):\n{existing_titles_str}\n\n"
        f"Create ONLY NEW and DIFFERENT conversation ideas — avoid repeating or closely resembling existing titles or descriptions."
    )

    response = client.models.generate_content(
        model=MODEL_NAME_CONVERSATION,
        contents=[full_prompt],
        config=config,
    )

    data = json.loads(response.text)
    data["ideas"] = assign_voice_ids(data.get("ideas", []))
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

def generate_podcast_ideas(existing_titles=None):
    print(f"🪄 Generating {NUM_PODCAST_IDEAS} podcast lesson ideas...")
    if not client: return None
    
    if existing_titles is None:
        existing_titles = []

    config = types.GenerateContentConfig(
        system_instruction=PODCAST_SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=PODCAST_SCHEMA
    )

    existing_titles_str = "\n".join([f"- {title}" for title in existing_titles]) if existing_titles else "None"
    
    full_prompt = (
        f"Generate {NUM_PODCAST_IDEAS} unique, creative, and highly useful podcast ideas for Finnish beginners, following the specified JSON structure exactly. Remember to use only the allowed character names.\n\n"
        f"**IMPORTANT:** Do NOT create podcasts with these titles or descriptions (already exist):\n{existing_titles_str}\n\n"
        f"Create ONLY NEW and DIFFERENT podcast ideas — avoid repeating or closely resembling existing titles or descriptions."
    )

    response = client.models.generate_content(
        model=MODEL_NAME_PODCAST,
        contents=[full_prompt],
        config=config,
    )

    data = json.loads(response.text)
    # **MODIFICATION HERE**: Use the new specific voice assignment function
    data["podcast_ideas"] = assign_podcast_voice_ids(data.get("podcast_ideas", [])) 
    return data, "podcast_ideas.json"

# --- GOOGLE SHEETS SYNC FUNCTIONS ---

def format_characters(characters):
    """Format character list into a readable string."""
    return "; ".join([
        f"{char.get('name', 'Unknown')} ({char.get('role', 'N/A')})"
        for char in characters
    ])

def sync_conversation_ideas_to_sheets(service, ideas_data):
    """Append conversation ideas to Google Sheets with date added."""
    if not service or not ideas_data or not SPREADSHEET_ID:
        return False
    
    try:
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        metadata = ideas_data.get("metadata", {})
        ideas = ideas_data.get("ideas", [])
        
        for idea in ideas:
            row = [
                idea.get("title", ""),
                idea.get("description", ""),
                format_characters(idea.get("characters", [])),
                metadata.get("language", ""),
                metadata.get("tone", ""),
                metadata.get("length", ""),
                json.dumps(idea.get("characters", [])),
                current_date,
            ]
            
            body = {"values": [row]}
            service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{CONVERSATION_SHEET}!A2",
                valueInputOption="USER_ENTERED",
                body=body,
            ).execute()
        
        if ideas:
            print(f"✅ Synced {len(ideas)} conversation ideas to Google Sheets")
            return True
    except Exception as e:
        print(f"⚠️ Warning: Could not sync to Google Sheets: {e}")
        return False
    
    return False

def sync_podcast_ideas_to_sheets(service, ideas_data):
    """Append podcast ideas to Google Sheets with date added."""
    if not service or not ideas_data or not SPREADSHEET_ID:
        return False
    
    try:
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        metadata = ideas_data.get("metadata", {})
        ideas = ideas_data.get("podcast_ideas", [])
        
        for idea in ideas:
            row = [
                idea.get("title", ""),
                idea.get("concept", ""),
                format_characters(idea.get("characters", [])),
                metadata.get("target_audience", ""),
                metadata.get("duration", ""),
                metadata.get("format", ""),
                json.dumps(idea.get("characters", [])),
                current_date,
            ]
            
            body = {"values": [row]}
            service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{PODCAST_SHEET}!A2",
                valueInputOption="USER_ENTERED",
                body=body,
            ).execute()
        
        if ideas:
            print(f"✅ Synced {len(ideas)} podcast ideas to Google Sheets")
            return True
    except Exception as e:
        print(f"⚠️ Warning: Could not sync to Google Sheets: {e}")
        return False
    
    return False

# --- MAIN EXECUTION ---

def main():
    if not client:
        print("🛑 Cannot run generation. Please ensure 'google-genai' is installed and 'GEMINI_API_KEY' is set in your .env file.")
        return

    # Initialize Google Sheets service
    sheets_service = get_sheets_service()

    # Check for command-line argument
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'podcast':
        # Fetch existing podcast titles from Google Sheets
        existing_titles = get_existing_titles(PODCAST_SHEET)
        result, output_file = generate_podcast_ideas(existing_titles)
        idea_count = NUM_PODCAST_IDEAS
        sheet_type = "podcast"
    else:
        # Default behavior: generate conversations
        # Fetch existing conversation titles from Google Sheets
        existing_titles = get_existing_titles(CONVERSATION_SHEET)
        result, output_file = generate_conversation_ideas(existing_titles)
        idea_count = NUM_CONVERSATION_IDEAS
        sheet_type = "conversation"

    if result:
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"✅ {idea_count} ideas saved to **{output_file}**")
            
            # Sync to Google Sheets
            if sheets_service:
                if sheet_type == "podcast":
                    sync_podcast_ideas_to_sheets(sheets_service, result)
                else:
                    sync_conversation_ideas_to_sheets(sheets_service, result)
            else:
                print("⚠️ Google Sheets sync skipped (service not available)")
                
        except Exception as e:
            print(f"❌ An error occurred while saving the file: {e}")

if __name__ == "__main__":
    main()