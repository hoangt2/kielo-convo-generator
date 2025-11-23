import json
import os
import re
import sys # Added for easier argument handling
from dotenv import load_dotenv
# --- Import the new Google GenAI SDK components ---
from google import genai
from google.genai import types 
from google.genai.errors import APIError

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
    """Convert a title into a safe filename."""
    return re.sub(r'[^a-z0-9äö]+', '-', title.lower()).strip('-')


# --- Core Logic: Updated to use Gemini API ---

def generate_conversation(idea, metadata):
    """Call Gemini to generate a conversation script in the required JSON array format."""
    
    # 1. Prepare the Character Map for the LLM (Unchanged)
    characters = idea.get("characters", [])
    if not characters:
        raise ValueError("Idea must contain a 'characters' list with 'name' and 'voice_id'.")
    
    # Create a simple map for the LLM to reference voice IDs
    char_map = {
        c['name']: {
            'voice_id': c.get('voice_id', f"VOICE_ID_PLACEHOLDER_{i}"), # Use real IDs if available
            'gender': c.get('gender', 'unknown'),
            'tone': c.get('default_tone', 'neutral')
        } for i, c in enumerate(characters)
    }
    
    char_info_text = "\n".join(
        [f"- {name} (Gender: {info['gender']}, Default Tone: {info['tone']}, Voice ID: {info['voice_id']})" for name, info in char_map.items()]
    )
    
    # 2. Build the detailed prompt instructing for JSON output (Unchanged)
    # The system instruction for strictly valid JSON is crucial for models that support it.
    prompt = f"""
        You are a Finnish dialogue writer. Your task is to generate a short (2–3 minutes) natural and realistic conversation 
        based on the provided idea.

        The output MUST be a single JSON object containing a key called 'dialogue_list'.
        The 'dialogue_list' must be a JSON array of objects, where each object represents a dialogue line 
        formatted exactly for the ElevenLabs text-to-dialogue API.

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
        - Keep the speech natural, expressive, and varied.
        - Match each character's tone and personality.

        Metadata:
        Language: {metadata.get('language', 'Finnish')}
        Tone: {metadata.get('tone', 'neutral')}
        Length: {metadata.get('length', '1-2 minutes')}

        Idea:
        Title: {idea['title']}
        Description: {idea['description']}

        Generate the full conversation in the specified JSON format.
    """
    
    # --- Gemini API Call Changes ---
    try:
        # Configuration for the API call
        config = types.GenerateContentConfig(
            # Set the generation temperature
            temperature=0.8,
            # Enforce JSON output!
            response_mime_type="application/json",
            # Pass the system instruction for model behavior
            system_instruction="You are a creative Finnish dialogue writer who writes expressive, natural speech, and you strictly output only valid JSON."
        )

        # Call the Gemini API. Use a model supporting JSON output, like gemini-2.5-flash.
        response = client.models.generate_content(
            model='gemini-2.5-flash', # A powerful model supporting JSON mode
            contents=prompt,
            config=config,
        )

    except APIError as e:
        print(f"❌ Error during Gemini API call: {e}")
        return {"dialogue_list": [], "error": f"API Error: {e}"}

    # The response content is a JSON string in a special 'text' field.
    json_string = response.text.strip()
    
    try:
        # Parse the JSON string and return
        json_output = json.loads(json_string)
        return json_output
    except json.JSONDecodeError:
        print("❌ Error: Gemini did not return valid JSON despite the configuration.")
        return {"dialogue_list": [], "error": json_string}

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
    
    # 2. Build the detailed prompt for a podcast script
    prompt = f"""
        You are an expert Finnish language podcast scriptwriter. Your task is to generate an engaging, 
        instructional podcast script based on the provided concept and characters.

        The output MUST be a single JSON object containing a key called 'dialogue_list'.
        The 'dialogue_list' must be a JSON array of objects, where each object represents a dialogue line 
        formatted exactly for the ElevenLabs text-to-dialogue API.

        The script should be a **language lesson** and must include clear explanations and examples based on the concept.
        The **main language** of the script must be **English**, with Finnish phrases and vocabulary introduced, 
        explained, and repeated for the lesson. This is crucial as the target is a Finnish '{metadata['target_audience']}' (Beginner).

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
        Format: {metadata['format']}

        Podcast Idea:
        Title: {idea['title']}
        Concept: {idea['concept']}

        Generate the full podcast script in the specified JSON format.
    """
    
    # --- Gemini API Call ---
    try:
        config = types.GenerateContentConfig(
            temperature=0.8,
            response_mime_type="application/json",
            system_instruction="You are an expert Finnish language podcast scriptwriter who writes instructional, engaging dialogue and strictly outputs only valid JSON."
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=config,
        )

    except APIError as e:
        print(f"❌ Error during Gemini API call: {e}")
        return {"dialogue_list": [], "error": f"API Error: {e}"}

    json_string = response.text.strip()
    
    try:
        json_output = json.loads(json_string)
        return json_output
    except json.JSONDecodeError:
        print("❌ Error: Gemini did not return valid JSON for the podcast script.")
        return {"dialogue_list": [], "error": json_string}


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