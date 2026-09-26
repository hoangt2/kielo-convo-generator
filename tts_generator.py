import os
import io
import re
import json
import sys # Added to handle command-line arguments
import difflib
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

# --- Configuration (Modified) ---
CONVERSATION_SCRIPTS_DIR = "scripts"
PODCAST_SCRIPTS_DIR = "podcast_scripts"
OUTPUT_AUDIO_DIR = "mp3"

# ElevenLabs model — v3 is required for audio tags and non-English IPA rules.
MODEL_ID = "eleven_v3"

# Conversation audio is synthesized ONE LINE AT A TIME via text_to_speech, then
# concatenated — not in a single text_to_dialogue call.
#
# Why: text_to_dialogue collapses minimal pairs. Measured on "Å, Ä, Ö och ett tak",
# transcribing the output back with Scribe to judge it:
#
#   text_to_dialogue, sv, stability 0.7      -> Tack Tack Tack Tack Tack
#   text_to_dialogue, sv, stability 1.0      -> Tack Tack Tack Tack Tack
#   text_to_dialogue, no language_code       -> Tack Tack Tack Tack Tack
#   text_to_dialogue, normalization off      -> Tack Tack Tack Tack Tack
#   text_to_speech, per line, sv             -> Tak Tak Tack Tak Tack   (correct)
#
# Ground truth was Tak/Tak/Tack/Tak/Tack. No text_to_dialogue setting fixes it;
# per-line text_to_speech gets it right. Podcasts still use text_to_dialogue —
# they are English and have no pronunciation-contrast requirement.
#
# Deliberately NO voice_settings on the per-line calls: the measurement above that
# scored 5/5 was made with the model's defaults, so we don't perturb them.
#
# The cost of per-line synthesis is that each line is voiced without knowing its
# neighbours, so turn-to-turn prosody is flatter than text_to_dialogue's. v3 rejects
# previous_text/next_text ("not yet supported with the 'eleven_v3' model"), so that
# cannot currently be compensated for; the gap constants below carry the pacing.

# Silence inserted between consecutive lines when concatenating (milliseconds).
# Kept at/above sfx_mixer.PAUSE_MIN_MS so its Whisper pass still finds gaps wide
# enough to overlay SFX into.
GAP_SAME_SPEAKER_MS = 350
GAP_SPEAKER_CHANGE_MS = 550

# Raw PCM is requested per line so concatenation is a plain byte join — no MP3
# frame-boundary artifacts — with a single encode at the end.
LINE_OUTPUT_FORMAT = "pcm_44100"
PCM_SAMPLE_RATE = 44100
PCM_SAMPLE_WIDTH = 2
PCM_CHANNELS = 1

# How many lines to synthesize concurrently.
MAX_WORKERS = 4

# Pronunciation verification: each target-language line is transcribed back and
# compared to its source text; a mismatch is re-synthesized.
#
# SCOPE — this catches gross misreads ("Tak" read as "Talk"), NOT the quantity
# contrast it was built for. Scribe passed Sten's /tak/ as "Tak" when he was in
# fact saying "tack"; a listener caught what the check did not. Treat a clean run
# as "nothing obviously broken", never as "pronunciation is correct" — the
# minimal-pair lines still need an ear. Whether a given voice renders the contrast
# at all is a property of the voice: Leo does, Sten does not.
VERIFY_PRONUNCIATION = True
STT_MODEL_ID = "scribe_v1"
MAX_ATTEMPTS = 3
# Similarity below which a line is considered misread. 0.9 is deliberately strict:
# "tak" vs "tack" scores 0.857, and catching exactly that is the point.
MIN_SIMILARITY = 0.9


def load_dialogue_data(file_path):
    """Loads the dialogue list, language, format, and pronunciation rules from a
    JSON file.  Returns (dialogue_list, language, fmt, pronunciation_rules) or
    (None, …) on error."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        dialogue_list = data.get("dialogue_list")
        if not dialogue_list:
            raise ValueError(f"Missing 'dialogue_list' key in {os.path.basename(file_path)}")

        # Filter out SFX entries — only keep dialogue entries for TTS
        dialogue_only = [item for item in dialogue_list if item.get("type") != "sfx"]

        if not dialogue_only:
            raise ValueError(f"No dialogue entries found in {os.path.basename(file_path)}")

        language = data.get("metadata", {}).get("language", "Finnish")
        # Guided lessons are English-led (the teaching happens in English), so their
        # audio must NOT be forced to the target language's pronunciation.
        fmt = data.get("idea", {}).get("format", "conversation")

        # Optional pronunciation rules for fine-grained phonetic control.
        # Each rule is either:
        #   {"string_to_replace": "tak", "type": "phoneme", "phoneme": "tɑːk", "alphabet": "ipa"}
        #   {"string_to_replace": "colour", "type": "alias", "alias": "color"}
        pronunciation_rules = data.get("pronunciation_rules", [])

        return dialogue_only, language, fmt, pronunciation_rules

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        print(f"❌ Skipping {file_path}: {e}")
        return None, None, None, None


def _create_pronunciation_dictionary(elevenlabs_client, rules, script_name):
    """Creates an ElevenLabs pronunciation dictionary from a list of rules.
    Returns a PronunciationDictionaryVersionLocator or None."""
    if not rules:
        return None, None

    try:
        from elevenlabs.types import PronunciationDictionaryVersionLocator

        dict_name = f"kielo-{script_name}-{os.getpid()}"
        print(f"   📖 Creating pronunciation dictionary ({len(rules)} rule(s))...")

        result = elevenlabs_client.pronunciation_dictionaries.create_from_rules(
            rules=rules,
            name=dict_name,
            description=f"Auto-generated pronunciation rules for {script_name}",
        )
        dict_id = result.id
        version_id = result.version_id
        print(f"   📖 Dictionary created: {dict_id} (v{version_id})")

        return PronunciationDictionaryVersionLocator(
            pronunciation_dictionary_id=dict_id,
            version_id=version_id,
        ), dict_id
    except Exception as e:
        print(f"   ⚠️  Could not create pronunciation dictionary: {e}")
        return None, None


def _cleanup_pronunciation_dictionary(elevenlabs_client, dict_id):
    """Best-effort cleanup of a temporary pronunciation dictionary."""
    if not dict_id:
        return
    # The SDK doesn't expose a delete method for pronunciation dictionaries,
    # so we just log and move on.  The dictionaries are small and inexpensive.
    pass



# --- Pronunciation verification helpers -------------------------------------

AUDIO_TAG_RE = re.compile(r"\[[^\]]*\]")

# Scribe occasionally returns a Swedish word in Cyrillic ("Так" for "Tak").
# That is a transcription-script artifact, not a mispronunciation, so fold it
# away before comparing rather than burning a retry on it.
_CYRILLIC_FOLD = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "и": "i",
    "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "c",
})


def spoken_text(text):
    """The words actually voiced: audio tags like [very clear] are direction, not speech."""
    return AUDIO_TAG_RE.sub(" ", text or "").strip()


def _normalize_for_compare(text):
    text = unicodedata.normalize("NFC", spoken_text(text)).lower()
    text = text.translate(_CYRILLIC_FOLD)
    text = re.sub(r"[^\w\sáàâäåéèêëíìîïóòôöúùûüøæœç]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def pronunciation_matches(expected, heard):
    """True if `heard` is a plausible transcription of `expected`.

    Short lines must match exactly — a lesson line is often a single word whose
    whole purpose is a minimal contrast ("Tak" vs "Tack"), and a ratio-based
    check scores that pair 0.857 and waves it through.
    """
    exp = _normalize_for_compare(expected)
    got = _normalize_for_compare(heard)
    if not exp:
        return True, 1.0
    if exp == got:
        return True, 1.0
    if len(exp.split()) <= 3:
        return False, difflib.SequenceMatcher(None, exp, got).ratio()
    ratio = difflib.SequenceMatcher(None, exp, got).ratio()
    return ratio >= MIN_SIMILARITY, ratio


def transcribe(elevenlabs_client, pcm_bytes, iso_code):
    """Transcribe raw PCM back to text so we can check what was actually said."""
    from pydub import AudioSegment

    seg = AudioSegment(
        data=pcm_bytes, sample_width=PCM_SAMPLE_WIDTH,
        frame_rate=PCM_SAMPLE_RATE, channels=PCM_CHANNELS,
    )
    buf = io.BytesIO()
    seg.export(buf, format="mp3")
    buf.name = "line.mp3"
    buf.seek(0)
    result = elevenlabs_client.speech_to_text.convert(
        file=buf, model_id=STT_MODEL_ID, language_code=iso_code,
    )
    return result.text


# --- Per-line synthesis ------------------------------------------------------

def _line_language(item, target_iso):
    """The language to synthesize one line in.

    Guided lessons tag each line `en` or the target code. Per-line synthesis lets
    us honour that tag, which a single text_to_dialogue call could not: it had to
    force the target language for the whole episode so the target-language words
    would not be read as English.
    """
    lang = (item.get("lang") or "").strip().lower()
    return lang if lang else target_iso


def synthesize_line(elevenlabs_client, item, target_iso, locator, index, total):
    """Synthesize one line, verifying target-language lines and retrying a misread.

    Returns (pcm_bytes, warning_or_None).
    """
    # "tts_text" is what gets SENT to the model; "text" stays the true wording for
    # subtitles and for the verification comparison below. Needed because a voice may
    # refuse a contrast as spelled — Sten renders "Tak" as /tak/ — and a respelling
    # like "Taak" is the only lever that reaches the acoustics.
    text = item.get("tts_text") or item.get("text", "")
    expected = item.get("text", "")
    voice_id = item.get("voice_id", "")
    iso = _line_language(item, target_iso)
    # A line may opt out with "verify": false. Needed for lines that are correct but
    # untranscribable as written — e.g. reciting "Å, Ä, Ö", where Å is genuinely
    # voiced [oː] and Scribe duly returns "O", which no string comparison can accept.
    should_verify = (
        VERIFY_PRONUNCIATION
        and item.get("verify", True)
        and iso == target_iso
        and spoken_text(expected)
    )

    kwargs = {
        "voice_id": voice_id,
        "text": text,
        "model_id": MODEL_ID,
        "language_code": iso,
        "output_format": LINE_OUTPUT_FORMAT,
    }
    if locator:
        kwargs["pronunciation_dictionary_locators"] = [locator]

    best_audio, best_ratio, best_heard = None, -1.0, ""

    for attempt in range(1, MAX_ATTEMPTS + 1):
        audio = b"".join(elevenlabs_client.text_to_speech.convert(**kwargs))

        if not should_verify:
            return audio, None

        try:
            heard = transcribe(elevenlabs_client, audio, iso)
        except Exception as e:
            # Verification is a safety net, not a gate — never lose good audio to it.
            print(f"   ⚠️  [{index}/{total}] Could not verify: {e}")
            return audio, None

        ok, ratio = pronunciation_matches(expected, heard)
        if ok:
            if attempt > 1:
                print(f"   ✓ [{index}/{total}] Correct on attempt {attempt}: {spoken_text(expected)!r}")
            return audio, None

        if ratio > best_ratio:
            best_audio, best_ratio, best_heard = audio, ratio, heard
        print(f"   ↻ [{index}/{total}] Attempt {attempt}: expected {spoken_text(expected)!r}, heard {heard!r}")

    warning = (
        f"line {index}: expected {spoken_text(expected)!r}, heard {best_heard!r} "
        f"after {MAX_ATTEMPTS} attempts"
    )
    return best_audio, warning


def _silence(ms):
    n_samples = int(PCM_SAMPLE_RATE * ms / 1000.0)
    return b"\x00" * (n_samples * PCM_SAMPLE_WIDTH * PCM_CHANNELS)


def _generate_conversation_audio(elevenlabs_client, dialogue_list, language, locator):
    """Synthesize a conversation one line at a time and concatenate.

    Returns (mp3_bytes, warnings). See the note by MODEL_ID for why this does not
    use text_to_dialogue.
    """
    from pydub import AudioSegment
    from language_config import get_iso_code

    target_iso = get_iso_code(language)
    total = len(dialogue_list)

    def task(i):
        return synthesize_line(
            elevenlabs_client, dialogue_list[i], target_iso, locator, i + 1, total,
        )

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = list(pool.map(task, range(total)))

    pcm_parts, warnings = [], []
    for i, (audio, warning) in enumerate(results):
        if warning:
            warnings.append(warning)
        if audio is None:
            continue
        if pcm_parts:
            same_speaker = (
                dialogue_list[i].get("voice_id") == dialogue_list[i - 1].get("voice_id")
            )
            pcm_parts.append(_silence(
                GAP_SAME_SPEAKER_MS if same_speaker else GAP_SPEAKER_CHANGE_MS
            ))
        pcm_parts.append(audio)

    combined = AudioSegment(
        data=b"".join(pcm_parts), sample_width=PCM_SAMPLE_WIDTH,
        frame_rate=PCM_SAMPLE_RATE, channels=PCM_CHANNELS,
    )
    buf = io.BytesIO()
    combined.export(buf, format="mp3", bitrate="192k")
    return buf.getvalue(), warnings


def _generate_podcast_audio(elevenlabs_client, dialogue_list, locator):
    """Podcasts stay on text_to_dialogue — English, and no minimal pairs to protect."""
    clean_inputs = [
        {"text": d.get("text", ""), "voice_id": d.get("voice_id", "")}
        for d in dialogue_list
    ]
    convert_kwargs = {"inputs": clean_inputs, "model_id": MODEL_ID}
    if locator:
        convert_kwargs["pronunciation_dictionary_locators"] = [locator]
    return b"".join(elevenlabs_client.text_to_dialogue.convert(**convert_kwargs)), []


def generate_and_save_audio(elevenlabs_client, dialogue_list, output_filename,
                            script_type, language="Finnish", fmt="conversation",
                            pronunciation_rules=None):
    """Generates and saves the conversation or podcast audio for one script. Returns True on success."""
    dict_id = None
    try:
        print(f"⏳ Generating {script_type} audio for: {output_filename} ...")

        locator = None
        if pronunciation_rules:
            script_name = os.path.splitext(output_filename)[0]
            locator, dict_id = _create_pronunciation_dictionary(
                elevenlabs_client, pronunciation_rules, script_name,
            )

        if script_type == "conversation":
            print(f"   🎚️  Synthesizing {len(dialogue_list)} line(s) individually...")
            audio_bytes, warnings = _generate_conversation_audio(
                elevenlabs_client, dialogue_list, language, locator,
            )
        else:
            audio_bytes, warnings = _generate_podcast_audio(
                elevenlabs_client, dialogue_list, locator,
            )

        os.makedirs(OUTPUT_AUDIO_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_AUDIO_DIR, output_filename)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        print(f"✅ Saved: {output_path}")
        if warnings:
            print(f"   ⚠️  {len(warnings)} line(s) still sound wrong — check these by ear:")
            for w in warnings:
                print(f"      • {w}")
        return True

    except Exception as e:
        print(f"❌ ElevenLabs API Error for {output_filename}: {e}")
        return False

    finally:
        _cleanup_pronunciation_dictionary(elevenlabs_client, dict_id)


def process_scripts_directory(elevenlabs_client, scripts_dir, script_type):
    """Helper function to process all JSON files in a given directory. Returns True if all succeeded."""
    
    if not os.path.isdir(scripts_dir):
        print(f"❌ Folder not found: {scripts_dir}")
        return False

    # Get all JSON files in the scripts folder
    script_files = [f for f in os.listdir(scripts_dir) if f.endswith(".json")]

    if not script_files:
        print(f"⚠️ No JSON files found in {scripts_dir}")
        return False

    print(f"🎬 Found {len(script_files)} {script_type} script(s) in '{scripts_dir}'. Starting generation...\n")

    had_errors = False
    for filename in script_files:
        file_path = os.path.join(scripts_dir, filename)
        base_name = os.path.splitext(filename)[0]
        # Prepend type to filename to avoid naming conflicts if titles are the same
        output_filename = f"{script_type}_{base_name}.mp3" 

        dialogue_list, language, fmt, pronunciation_rules = load_dialogue_data(file_path)
        if dialogue_list:
            if not generate_and_save_audio(
                elevenlabs_client, dialogue_list, output_filename,
                script_type, language, fmt,
                pronunciation_rules=pronunciation_rules,
            ):
                had_errors = True

    if had_errors:
        print(f"\n❌ Finished processing {script_type} scripts with errors.")
    else:
        print(f"\n✅ Finished processing {script_type} scripts.")
    return not had_errors


def main():
    # Load environment variables (API key)
    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("❌ ELEVENLABS_API_KEY not found. Please add it to your .env file.")
        sys.exit(1)

    # Guided lessons can be several minutes of dialogue in one text_to_dialogue call, which
    # takes a while to generate — the SDK's default read timeout is too short and errors with
    # "The read operation timed out". Give it plenty of headroom.
    elevenlabs = ElevenLabs(api_key=api_key, timeout=600)

    # Determine which folder to process based on command-line argument
    all_succeeded = True
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'podcast':
        # Process podcast scripts only
        all_succeeded = process_scripts_directory(elevenlabs, PODCAST_SCRIPTS_DIR, "podcast")
    elif len(sys.argv) > 1 and sys.argv[1].lower() == 'all':
        # Process both folders
        print("Processing ALL scripts (Conversation and Podcast)...")
        conv_ok = process_scripts_directory(elevenlabs, CONVERSATION_SCRIPTS_DIR, "conversation")
        pod_ok = process_scripts_directory(elevenlabs, PODCAST_SCRIPTS_DIR, "podcast")
        all_succeeded = conv_ok and pod_ok
    else:
        # Default: Process conversation scripts only
        all_succeeded = process_scripts_directory(elevenlabs, CONVERSATION_SCRIPTS_DIR, "conversation")

    if not all_succeeded:
        print("\n❌ Audio generation failed with errors!")
        sys.exit(1)

    print("\n🏁 All specified audio generation complete!")


if __name__ == "__main__":
    main()