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
from language_config import get_language_config, get_iso_code

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


def _repair_voice_ids(dialogue_list, characters):
    """Fix voice_ids that the LLM may have subtly altered (e.g. changed casing).

    Builds a case-insensitive lookup from the authoritative character list and
    replaces every voice_id in the dialogue with the exact original value.
    Entries without a voice_id (e.g. SFX) are left untouched.
    """
    # Map lowercased voice_id → exact voice_id from the character definitions
    canonical = {
        c.get("voice_id", "").lower(): c["voice_id"]
        for c in characters
        if c.get("voice_id")
    }
    for entry in dialogue_list:
        vid = entry.get("voice_id")
        if vid and vid.lower() in canonical:
            entry["voice_id"] = canonical[vid.lower()]
    return dialogue_list


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
                _repair_voice_ids(json_output["dialogue_list"], characters)
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

# --- Guided-lesson generation (true-beginner, bilingual gloss-once) ---

# Role keywords used to tell the learner apart from the guide in a guided lesson.
_LEARNER_HINTS = ("learn", "student", "beginner", "expat", "new to", "newcomer")

# The guide must be a PERSONAL COMPANION who knows the learner — a friend, neighbour,
# colleague or family member. Someone like that teaching a beginner their first words
# is believable. A transactional service worker (barista, cashier, clerk, librarian…)
# doing it is NOT — it breaks the scene ("the barista started the lesson"). So the guide
# is chosen ONLY from companions; service/stranger roles are never made the tutor.
_COMPANION_HINTS = (
    "friend", "befriend", "buddy", "pal", "neighbor", "neighbour", "colleague",
    "classmate", "coworker", "co-worker", "roommate", "flatmate", "host", "tutor",
    "mentor", "family", "sister", "brother", "mother", "father", "parent", "cousin",
    "partner", "spouse", "husband", "wife", "girlfriend", "boyfriend",
)


def _identify_guided_roles(characters):
    """Pick (learner, guide, extras) for a guided lesson from character role text.

    The learner is whoever is described as new to the language. The guide is a personal
    COMPANION of the learner (friend/neighbour/colleague/family) — never a transactional
    service worker, whose teaching a beginner would break the scene. Returns guide=None
    when no companion is present (the caller then generates a normal conversation instead
    of forcing a stranger to tutor). Any remaining characters play small background parts.
    """
    learner = next(
        (c for c in characters
         if any(k in (c.get("role") or "").lower() for k in _LEARNER_HINTS)),
        None,
    )
    if learner is None:
        learner = characters[0]

    others = [c for c in characters if c is not learner]
    guide = next(
        (c for c in others
         if any(k in (c.get("role") or "").lower() for k in _COMPANION_HINTS)),
        None,
    )

    extras = [c for c in others if c is not guide]
    return learner, guide, extras


def generate_guided_lesson(idea, metadata):
    """Call Gemini to generate a GUIDED, bilingual teacher/learner lesson scene.

    Same output schema as generate_conversation (a 'dialogue_list' of dialogue +
    sfx entries) so the rest of the pipeline is unchanged — but the scene is
    scaffolded for someone who has never spoken the language: the guide introduces
    each new target-language chunk, glosses its meaning in English exactly ONCE,
    and the learner repeats it. Each dialogue entry is tagged with "lang" ("sv"/"en"
    for the target language vs. the English bridge) so downstream steps (e.g. the
    grammar checker) can treat the English glosses correctly.
    """
    characters = idea.get("characters", [])
    if not characters:
        raise ValueError("Idea must contain a 'characters' list with 'name' and 'voice_id'.")

    language = metadata.get("language", "Finnish")
    lang_cfg = get_language_config(language)
    spoken_label = lang_cfg["spoken_label"]
    lang_code = get_iso_code(language)

    learner, guide, extras = _identify_guided_roles(characters)
    if guide is None:
        # No personal companion in the scene to guide the learner (only the learner, or
        # only service workers/strangers). Forcing a stranger to tutor breaks the scene,
        # so generate a normal conversation instead of a guided lesson.
        return generate_conversation(idea, metadata)

    char_info_text = "\n".join(
        f"- {c['name']} (Gender: {c.get('gender','unknown')}, "
        f"Default Tone: {c.get('default_tone','neutral')}, Voice ID: {c.get('voice_id','')})"
        for c in characters
    )
    extras_note = ""
    if extras:
        extra_names = ", ".join(c["name"] for c in extras)
        extras_note = (
            f"\n        Other characters ({extra_names}) may appear only briefly in small "
            f"background parts; they must NOT take over the lesson."
        )

    ambient_setting = idea.get('ambient_setting', '')
    ambient_note = ""
    if ambient_setting:
        ambient_note = (
            f"\n        Ambient Setting: {ambient_setting} (use it to inspire a few "
            f"contextually appropriate sound effects)."
        )

    level_block = conversation_level_block(metadata.get('language_level'), language)

    # The lesson's phrases are the REQUIRED curriculum for a guided episode — every one must be
    # taught, not a "pick a few" suggestion. Build an explicit checklist from the episode so the
    # model covers the whole lesson (the scene simply gets longer to fit them all).
    lessons_covered = idea.get("lessons_covered", []) or []
    key_phrases = idea.get("key_phrases", []) or []
    lessons_line = ""
    if lessons_covered:
        lessons_line = "\n        Lessons this episode must cover: " + "; ".join(lessons_covered)
    if key_phrases:
        phrase_lines = "\n".join(f"          {i}. {p}" for i, p in enumerate(key_phrases, 1))
        curriculum_block = (
            f"\n\n        REQUIRED CURRICULUM — teach EVERY one of these target phrases (this is a "
            f"checklist, NOT optional):{lessons_line}\n{phrase_lines}\n"
            f"        Adapt wording/inflection to fit the scene naturally, but do not skip any phrase. "
            f"If two phrases pair up (a prompt and its reply, e.g. a thank-you and 'you're welcome'), "
            f"teach them together. Ignore any 'optional / not a checklist' framing in the scenario "
            f"description below — for a guided lesson these phrases ARE the lesson."
        )
    else:
        curriculum_block = ""

    prompt = f"""
        You are writing a GUIDED beginner {language} lesson as a scene for someone who has NEVER
        spoken a word of {language} and understands almost NONE of it yet. It must feel like a warm,
        real moment between people — a patient guide gently teaching a friend — NOT a dry classroom
        drill. Take as long as the lesson needs (a few minutes is fine): it is more important to
        cover every target phrase clearly, with repetition, than to keep it short.

        THE TWO KEY ROLES:
        - GUIDE = {guide['name']}: a warm local who is TEACHING {learner['name']} their first words.
        - LEARNER = {learner['name']}: brand new to {language}. Listens, asks, repeats, tries.{extras_note}

        THE #1 RULE — ENGLISH IS THE TEACHING LANGUAGE:
        The guide talks to the learner in ENGLISH. All instructions, encouragement, reactions, and
        scene talk ("Here, hold the bowl", "Great, now try this", "Don't worry") are in ENGLISH.
        {language} is NOT used for conversation or glue — a total beginner cannot decode it yet.

        {language} appears ONLY as the small, deliberate phrases being TAUGHT. Every single piece of
        {language} the learner hears MUST be one the guide is explicitly teaching in that moment.
        There must be ZERO untranslated {language}. If a {language} phrase is spoken, it is ALWAYS:
          1. Framed first in English  — e.g. 'In {language}, "thank you" is...'
          2. Said slowly in {language} — the short target phrase only.
          3. Glossed/confirmed in English right away — e.g. 'That means "thank you".'
          4. Repeated by the learner in {language}, and the guide reacts in English ('Perfect!').
        Never let a {language} phrase go by without its English meaning attached.

        ACCURACY — GET THE TEACHING FACTS RIGHT (these mistakes ruin the lesson):
        - The {language} line and its English framing/gloss MUST match EXACTLY. If you frame a line as
          'the formal way, "Minä olen Alex"', the {language} line that follows must be spelled/spoken
          as "Minä olen Alex" — never model a different form (e.g. the casual "Mä oon Alex") under that
          label. If the learner is asked to repeat a specific form, they repeat THAT form, not another.
        - Label register CORRECTLY. Spoken/casual forms are NOT the "standard", "formal", "textbook" or
          "by the book" forms, and vice-versa. In {language}, the written/standard pronouns and endings
          (e.g. Finnish 'minä', 'sinä', 'olen', 'sanomme') are the formal ones; the shortened spoken
          forms (e.g. 'mä', 'sä', 'oon', 'sanotaan') are the casual ones. Never call a casual form the
          formal/standard one, or a formal form the casual one.
        - HONOUR EACH SPEAKER'S REGISTER from the Character speech styles / direction below. If the
          learner is described as speaking careful standard {language} (e.g. 'minä/sinä'), keep them in
          that register — do NOT have them suddenly switch to casual forms unless adopting that new form
          is the EXPLICIT point/payoff of this lesson, and only at the moment the scene earns it.
        - When the lesson itself is a CONTRAST between two forms (e.g. formal vs spoken pronouns), show
          BOTH forms, label each one correctly, let the contrast surface naturally from the two speakers'
          registers, and only then explain the difference. Do not blur the two together.

        COVERAGE & PACING (cover the whole lesson, but never overwhelm):
        - Teach EVERY target phrase in the REQUIRED CURRICULUM below — do not drop any. The scene can
          be as long as it needs to be to fit them all naturally.
        - Introduce ONE phrase at a time: teach it, have the learner repeat it, react, then move on.
          Don't dump several new phrases at once — a beginner still needs each one handled slowly.
        - Reuse phrases: bring earlier phrases back later in the scene (e.g. in a short recap or a
          natural callback) so they stick, not just taught once and forgotten.
        - Each {language} phrase is short and clear. The MAJORITY of the words are still ENGLISH (the
          teaching/glue); {language} is the precious part being learned.
        - Keep every {language} phrase within the CEFR level below; use the simpler in-level form if
          natural phrasing would exceed it.

        Give the scene a natural arc: a reason it starts, the guide teaching the phrases one at a time
        (grouping ones that pair up), with repetition and a brief recap, and a warm close where the
        learner uses several of the phrases they just learned.{curriculum_block}

        Characters:
        {char_info_text}

        OUTPUT FORMAT — a single JSON object with a key 'dialogue_list', a JSON array of objects.
        There are TWO entry types:

        1. Dialogue entry (a spoken line):
        {{
            "text": "[emotion] the spoken line, with sound cues like [laugh] if natural.",
            "voice_id": "the exact voice_id for the speaker from the list above.",
            "lang": "{lang_code}" for a {language} line, or "en" for an English bridge line.
        }}

        2. Sound-effect entry (environmental/action sound between lines):
        {{ "type": "sfx", "text": "short sound description", "duration": 2.0, "timing": "before" }}

        Dialogue rules:
        - Use the EXACT voice_id for each speaker.
        - EVERY dialogue entry MUST include the "lang" field ("{lang_code}" or "en"). This is mandatory.
        - Lines that are purely {language} → "lang": "{lang_code}". Lines that are the English meaning/
          encouragement → "lang": "en". Do NOT mix both languages inside one entry — split them into
          two entries so each has a single clear "lang".
        - The 'text' field must start with an emotion/tone in brackets (e.g., [warm], [encouraging]).
        - Keep the guide encouraging and the learner earnest. Match each character's tone.

        Sound effects: add 2–4 at natural action moments (see the setting). "timing" is "before" or
        "after" the adjacent dialogue line. Don't add one for every line.

        Metadata:
        Language: {language} ({spoken_label})
        Tone: {metadata.get('tone', 'warm, encouraging')}
        Length: as long as needed to teach every phrase in the curriculum clearly, with repetition
        (do NOT cut the lesson short to save time).{ambient_note}{level_block}

        Lesson idea:
        Title: {idea['title']}
        Description: {idea['description']}

        Generate the full guided lesson scene now.
    """

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            config = types.GenerateContentConfig(
                temperature=0.7,
                response_mime_type="application/json",
                system_instruction=(
                    f"You are a patient {language} teacher who writes warm, realistic guided lesson "
                    f"scenes for absolute beginners. You scaffold with English glosses used sparingly "
                    f"(gloss-once), keep the {language} short and in-level, and have the learner repeat "
                    f"each new chunk. You strictly output only valid JSON."
                ),
            )

            response = client.models.generate_content(
                model='gemini-2.5-pro',
                contents=prompt,
                config=config,
            )

            json_output = json.loads(response.text.strip())

            dialogue = json_output.get("dialogue_list")
            if dialogue and len(dialogue) > 0:
                # Fix voice_ids the LLM may have subtly altered (casing)
                _repair_voice_ids(dialogue, characters)
                # Guarantee every spoken entry carries a lang tag (default to target language)
                # so downstream steps never have to guess.
                for entry in dialogue:
                    if entry.get("type") != "sfx" and not entry.get("lang"):
                        entry["lang"] = lang_code
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

    print("❌ Error: Failed to generate guided lesson after all retries.")
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
                _repair_voice_ids(json_output["dialogue_list"], characters)
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

    for idea in ideas:
        # Within the conversation type, an idea can opt into the GUIDED (bilingual,
        # teacher-led) format for true beginners via its "format" field. Everything
        # else keeps the existing behavior untouched.
        if script_type == 'conversation' and idea.get("format") == "guided":
            generator_func = generate_guided_lesson
            print(f"🪄 Generating GUIDED lesson for: {idea['title']} ...")
        elif script_type == 'conversation':
            generator_func = generate_conversation
            print(f"🪄 Generating {script_type} for: {idea['title']} ...")
        else:
            generator_func = generate_podcast_script
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