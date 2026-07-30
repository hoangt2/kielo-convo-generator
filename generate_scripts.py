import json
import os
import re
import sys
import time
from dotenv import load_dotenv
# --- Import the new Google GenAI SDK components ---
from google import genai
from google.genai import types
from google.genai.errors import APIError
from cefr_levels import conversation_level_block, podcast_level_block
from language_config import get_language_config

# --- Load environment variables ---
load_dotenv()
# Change to GEMINI_API_KEY
api_key = os.getenv("GEMINI_API_KEY") 

if not api_key:
    # Update error message and variable check
    raise ValueError("❌ GEMINI_API_KEY not found. Please add it to your .env file.")

# Initialize Gemini client
# The Client constructor takes the API key directly.
client = genai.Client(api_key=api_key) 

# --- Helper Functions (unchanged) ---

def slugify(title):
    """Convert a title into a safe ASCII filename.

    Finnish/accented letters are transliterated (ä->a, ö->o, å->a, ...) so words are
    preserved instead of dropped ("Mitä kello on?" -> "mita-kello-on", not "mit-kello-on").
    """
    text = title.lower().translate(str.maketrans({
        "ä": "a", "ö": "o", "å": "a", "š": "s", "ž": "z",
        "ü": "u", "é": "e", "è": "e", "ê": "e", "á": "a", "à": "a", "â": "a",
        "í": "i", "ì": "i", "ó": "o", "ò": "o", "ô": "o", "ú": "u", "ù": "u",
        "ñ": "n", "ç": "c",
    }))
    return re.sub(r'[^a-z0-9]+', '-', text).strip('-')


# --- Core Logic: Updated to use Gemini API ---

def generate_conversation(idea, metadata):
    """Call Gemini to generate a conversation script in the required JSON array format."""
    
    # 1. Prepare the Character Map for the LLM
    characters = idea.get("characters", [])
    if not characters:
        raise ValueError("Idea must contain a 'characters' list with 'name' and 'voice_id'.")
    
    # Create a simple map for the LLM to reference voice IDs
    char_map = {
        c['name']: {
            'voice_id': c.get('voice_id', f"VOICE_ID_PLACEHOLDER_{i}"),
            'gender': c.get('gender', 'unknown'),
            'tone': c.get('default_tone', 'neutral')
        } for i, c in enumerate(characters)
    }
    
    char_info_text = "\n".join(
        [f"- {name} (Gender: {info['gender']}, Default Tone: {info['tone']}, Voice ID: {info['voice_id']})" for name, info in char_map.items()]
    )
    
    # 2. Language-aware prompt building
    language = metadata.get("language", "Finnish")
    lang_cfg = get_language_config(language)
    spoken_label = lang_cfg["spoken_label"]
    formal_label = lang_cfg["formal_label"]
    spoken_features = lang_cfg["spoken_features"]
    casual_particles = lang_cfg["casual_particles"]
    generic_address = lang_cfg["generic_address"]

    ambient_setting = idea.get('ambient_setting', '')
    ambient_note = ""
    if ambient_setting:
        ambient_note = f"\n        Ambient Setting: {ambient_setting} (This describes the environment — use it to inspire contextually appropriate sound effects.)"

    level_block = conversation_level_block(metadata.get('language_level'), language)

    prompt = f"""
        You are a {language} dialogue writer specializing in NATURAL {spoken_label.upper()}.
        Your task is to generate a short (1–2 minutes) realistic conversation based on the provided idea.

        #1 PRIORITY — A LOGICAL, ENGAGING, REALISTIC CONVERSATION.
        This is a real scene between people, NOT a vocabulary drill. A coherent, believable, engaging
        exchange matters far MORE than covering teaching phrases or vocab. Specifically:
        - Internal consistency is mandatory. Track the facts: if they agree on a day/time/place,
          every later line must match it (don't agree on Wednesday then say "see you Thursday").
          Don't contradict what was just said (don't claim "I have a meeting" then "no hurry").
        - Every line must logically follow from the previous one — real cause and effect, real
          reactions. People respond to what was actually said.
        - Characters say only what's natural in the moment; they don't recite. It's fine to leave a
          teaching phrase out. Quality and realism beat completeness, always.
        - Give it a natural arc: a reason the conversation starts, a little middle, and a natural
          close once the goal is met. Don't pad.
        - Keep each speaker in character (their tone, register and personality).
        - Stay within the CEFR level given below — that limit is also mandatory. If natural or
          polite phrasing would exceed it, use the simpler in-level form (it's fine to sound plainer).

        CRITICAL: Write in {spoken_label}, NOT {formal_label}. Use:
        - {spoken_features}
        - Casual expressions: {casual_particles}
        - Natural filler words and interjections

        The output MUST be a single JSON object containing a key called 'dialogue_list'.
        The 'dialogue_list' must be a JSON array of objects. There are TWO types of entries:

        1. **Dialogue entries** (spoken lines):
        {{
            "text": "[emotion] Dialogue line in {spoken_label}, including sound cues like [sigh] or [laugh].",
            "voice_id": "The specific voice_id for this character from the list above."
        }}

        2. **Sound effect entries** (environmental/action sounds placed between dialogue lines):
        {{
            "type": "sfx",
            "text": "Short description of the sound effect, e.g. 'door opening and closing', 'phone ringing', 'bag zipper opening'",
            "duration": 2.0,
            "timing": "before"
        }}

        Characters:
        {char_info_text}

        Sound Effects Instructions:
        - Add 2–5 sound effect entries at NATURAL moments in the conversation.
        - Place SFX entries BETWEEN dialogue lines, at points where an action or event happens.
        - You can also place SFX at the very START (before any dialogue) or END (after last dialogue) of the conversation.
        - SFX descriptions should be short (3-8 words) and specific for audio generation.
        - Duration should be 0.5–5.0 seconds, appropriate for the sound.
        - The "timing" field controls WHEN the sound plays relative to dialogue:
          * "before" = sound plays BEFORE the next dialogue line (e.g., phone rings → person answers)
          * "after" = sound plays AFTER the previous dialogue line (e.g., person hangs up → click sound)
        - Choose timing carefully based on what makes sense narratively:
          * Door opening/bell ringing/phone ringing → "before" (sound triggers the reaction)
          * Hanging up phone/putting down cup/walking away → "after" (sound follows the action)
          * At conversation start (scene-setting sounds) → "before"
          * At conversation end (closing sounds) → "after"
        - Examples of good SFX: "coffee cup placed on table", "bus doors opening with hiss", "phone notification sound", "keys jingling", "footsteps on pavement".
        - Do NOT add SFX for every line — only at key action moments.

        Dialogue Instructions:
        - Use the **exact** 'voice_id' provided in the Characters list for each dialogue line.
        - The 'text' field must start with an emotion/tone in brackets (e.g., [calm], [excited]).
        - Write ONLY in natural {spoken_label} — avoid formal/written language!
        - Keep the speech natural, expressive, and varied.
        - Match each character's tone and personality.
        - If the Description lists "Teaching ideas"/example phrases, treat them as OPTIONAL inspiration
          only — weave in just the few that fit naturally, adapt them, and DROP the rest. A coherent
          scene always wins over using more phrases. Never include a phrase if it breaks the logic.
        - **IMPORTANT — Name usage:** Determine whether the characters know each other based on the scenario description. If they are strangers (e.g., customer and clerk, patient and receptionist, passenger and driver, someone asking directions from a passerby), they must NOT call each other by name. Use generic forms of address instead (e.g., {generic_address}). Only use character names in dialogue if the scenario clearly implies a personal relationship (e.g., friends, family, colleagues who know each other).

        Metadata:
        Language: {language} ({spoken_label})
        Tone: {metadata.get('tone', 'neutral')}
        Length: {metadata.get('length', '1-2 minutes')}{ambient_note}{level_block}

        Idea:
        Title: {idea['title']}
        Description: {idea['description']}

        Generate the full conversation in natural {spoken_label} with sound effects at appropriate moments.
    """
    
    # --- Gemini API Call with Retry Logic ---
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            # Configuration for the API call
            config = types.GenerateContentConfig(
                temperature=0.8,
                response_mime_type="application/json",
                system_instruction=(
                    f"You are a creative {language} dialogue writer who writes natural "
                    f"{spoken_label}, not {formal_label}. "
                    f"Above all, write a LOGICAL, internally consistent, engaging conversation "
                    f"— a real scene, never a vocabulary list; coherence beats covering teaching "
                    f"phrases. You strictly output only valid JSON."
                )
            )

            # Use the pro model — better at keeping the conversation logical and internally
            # consistent (flash tended to cram in phrases and contradict itself).
            response = client.models.generate_content(
                model='gemini-2.5-pro',
                contents=prompt,
                config=config,
            )
            
            # The response content is a JSON string in a special 'text' field.
            json_string = response.text.strip()
            
            # Parse the JSON string
            json_output = json.loads(json_string)
            
            # Validate that dialogue_list is not empty
            if json_output.get("dialogue_list") and len(json_output["dialogue_list"]) > 0:
                return json_output
            else:
                print(f"   ⚠️  Empty dialogue received, retrying... ({attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay * (attempt + 1))
                continue

        except APIError as e:
            print(f"   ⚠️  API error: {e}, retrying... ({attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                import time
                time.sleep(retry_delay * (attempt + 1))
            continue
        except json.JSONDecodeError:
            print(f"   ⚠️  Invalid JSON response, retrying... ({attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                import time
                time.sleep(retry_delay * (attempt + 1))
            continue
    
    print("❌ Error: Failed to generate dialogue after all retries.")
    return {"dialogue_list": [], "error": "Failed after retries"}

# --- NEW Function for Podcast Script Generation ---

def generate_podcast_script(idea, metadata):
    """Call Gemini to generate a podcast script for a language lesson, using the provided concept."""
    
    # 1. Prepare Character Map (Updated to include Role and Concept)
    characters = idea.get("characters", [])
    if not characters:
        raise ValueError("Podcast idea must contain a 'characters' list with 'name' and 'voice_id'.")
    
    char_info_text = "\n".join(
        [f"- {c['name']} (Role: {c['role']}, Tone: {c['default_tone']}, Voice ID: {c['voice_id']})" for c in characters]
    )

    level_block = podcast_level_block(metadata.get('language_level'))

    # 2. Build the detailed prompt for a podcast script
    prompt = f"""
        You are an expert {language} language podcast scriptwriter. Your task is to generate an engaging, 
        instructional podcast script based on the provided concept and characters.

        The output MUST be a single JSON object containing a key called 'dialogue_list'.
        The 'dialogue_list' must be a JSON array of objects, where each object represents a dialogue line 
        formatted exactly for the ElevenLabs text-to-dialogue API.

        The script should be a **language lesson** and must include clear explanations and examples based on the concept.
        The **main language** of the script must be **English**, with {language} phrases and vocabulary introduced, 
        explained, and repeated for the lesson. This is crucial as the target is a {language} '{metadata['target_audience']}' (Beginner).

        Characters:
        {char_info_text}

        JSON Output Format Specification:
        The final output must be a JSON object like this:
        {{
        "dialogue_list": [
            {{
            "text": "[emotion] Dialogue line, including sound cues like [sigh] or [laugh].",
            "voice_id": "The specific voice_id for this character from the list above."
            }},
            // ... more dialogue objects
        ]
        }}

        Instructions:
        - Use the **exact** 'voice_id' provided in the Characters list for each line.
        - The 'text' field must start with an emotion/tone in brackets (e.g., [calm], [excited]).
        - The script must clearly deliver the lesson outlined in the concept.
        - **STRICTLY:** The vast majority (85%+) of the dialogue should be in English. Introduce and explain Finnish words/phrases clearly.
        - Ensure the total duration aligns with the metadata length.

        Metadata:
        Target Audience: {metadata['target_audience']}
        Duration: {metadata['duration']}
        Format: {metadata['format']}{level_block}

        Podcast Idea:
        Title: {idea['title']}
        Concept: {idea['concept']}

        Generate the full podcast script in the specified JSON format.
    """
    
    # --- Gemini API Call with Retry Logic ---
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            config = types.GenerateContentConfig(
                temperature=0.8,
                response_mime_type="application/json",
                system_instruction=f"You are an expert {language} language podcast scriptwriter who writes instructional, engaging dialogue and strictly outputs only valid JSON."
            )

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=config,
            )
            
            json_string = response.text.strip()
            json_output = json.loads(json_string)
            
            # Validate that dialogue_list is not empty
            if json_output.get("dialogue_list") and len(json_output["dialogue_list"]) > 0:
                return json_output
            else:
                print(f"   ⚠️  Empty dialogue received, retrying... ({attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                continue

        except APIError as e:
            print(f"   ⚠️  API error: {e}, retrying... ({attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
            continue
        except json.JSONDecodeError:
            print(f"   ⚠️  Invalid JSON response, retrying... ({attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
            continue
    
    print("❌ Error: Failed to generate podcast script after all retries.")
    return {"dialogue_list": [], "error": "Failed after retries"}


# --- Remaining Functions (Modified for flexibility) ---

def save_scripts(title, script_type, idea, metadata, conversation_data):
    """Save scripts to a structured JSON file in a dedicated subfolder."""
    
    # Determine the subdirectory based on script_type
    if script_type == 'podcast':
        folder = "podcast_scripts"
    elif script_type == 'conversation':
        folder = "scripts"
    else:
        raise ValueError("Invalid script_type provided.")
        
    os.makedirs(folder, exist_ok=True)

    slug = slugify(title)
    json_path = os.path.join(folder, f"{slug}.json")

    dialogue_list = conversation_data.get('dialogue_list', [])

    # The full JSON script (structured data)
    full_json_data = {
        "metadata": metadata,
        "idea": idea,
        "dialogue_list": dialogue_list,
    }

    # Save to JSON
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(full_json_data, jf, ensure_ascii=False, indent=2)

    return json_path

def process_ideas_file(filename, script_type, idea_key):
    """Generic function to load ideas and process them."""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {filename} not found. Please create it.")
        return
    except json.JSONDecodeError:
        print(f"❌ Error: Could not decode JSON from {filename}.")
        return

    metadata = data["metadata"]
    ideas = data[idea_key]

    generator_func = generate_conversation if script_type == 'conversation' else generate_podcast_script

    for idea in ideas:
        print(f"🪄 Generating {script_type} for: {idea['title']} ...")

        conversation_data = generator_func(idea, metadata) 
        
        json_path = save_scripts(idea['title'], script_type, idea, metadata, conversation_data)

        print(f"✅ Saved JSON: {json_path}\n")

    print(f"🎉 All {script_type} scripts generated successfully!")


def main():
    # Allow a command-line argument to specify which file to use
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'podcast':
        # New mode: Generate podcast scripts
        process_ideas_file("podcast_ideas.json", "podcast", "podcast_ideas")
    else:
        # Default mode: Generate standard conversations
        process_ideas_file("ideas.json", "conversation", "ideas")


if __name__ == "__main__":
    main()