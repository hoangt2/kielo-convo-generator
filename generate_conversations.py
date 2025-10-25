import json
import os
import re
from dotenv import load_dotenv
from openai import OpenAI

# --- Load environment variables ---
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("❌ OPENAI_API_KEY not found. Please add it to your .env file.")

# Initialize OpenAI client
client = OpenAI(api_key=api_key)


def slugify(title):
    """Convert a title into a safe filename."""
    return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')


def generate_conversation(idea, metadata):
    """Call GPT to generate a conversation script in the required JSON array format."""
    
    # 1. Prepare the Character Map for the LLM
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
    
    # 2. Build the detailed prompt instructing for JSON output
    prompt = f"""
You are a Finnish dialogue writer. Your task is to generate a short (1–2 minutes) natural and realistic conversation 
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
Language: {metadata['language']}
Tone: {metadata['tone']}
Length: {metadata['length']}

Idea:
Title: {idea['title']}
Description: {idea['description']}

Generate the full conversation in the specified JSON format.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a creative Finnish dialogue writer who writes expressive, natural speech, and you strictly output only valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.8,
        # Enforce JSON output!
        response_format={"type": "json_object"}
    )
    
    # The response content will be a JSON string, which we parse and return
    try:
        json_output = json.loads(response.choices[0].message.content.strip())
        return json_output
    except json.JSONDecodeError:
        print("❌ Error: GPT did not return valid JSON.")
        return {"dialogue_list": [], "error": response.choices[0].message.content.strip()}


def save_scripts(idea, metadata, conversation_data):
    """Save scripts only to the structured JSON file."""
    os.makedirs("scripts", exist_ok=True)

    slug = slugify(idea["title"])
    json_path = os.path.join("scripts", f"{slug}.json")

    # The conversation_data is now already in a structured JSON format from generate_conversation
    dialogue_list = conversation_data.get('dialogue_list', [])

    # The full JSON script (structured data)
    full_json_data = {
        "metadata": metadata,
        "idea": idea,
        "dialogue_list": dialogue_list,
        # Optionally add other keys from the GPT output if needed
    }

    # Save to JSON
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(full_json_data, jf, ensure_ascii=False, indent=2)

    # Note: TXT file creation removed here.

    # Returning only the JSON path since the TXT path is no longer relevant
    return json_path


def main():
    # Load ideas JSON
    try:
        with open("ideas.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("❌ Error: ideas.json not found. Please create it.")
        return

    metadata = data["metadata"]
    ideas = data["ideas"]

    # Loop through ideas and generate conversations
    for idea in ideas:
        print(f"🪄 Generating conversation for: {idea['title']} ...")

        conversation_data = generate_conversation(idea, metadata) 
        
        # save_scripts now returns only the json_path
        json_path = save_scripts(idea, metadata, conversation_data)

        print(f"✅ Saved JSON: {json_path}\n")

    print("🎉 All conversations generated successfully!")


if __name__ == "__main__":
    main()