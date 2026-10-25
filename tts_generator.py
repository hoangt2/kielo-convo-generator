import os
import io
import re
import json
import time
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

# Guided lessons are for people who have never heard the language, and native-rate
# delivery is too fast to pick apart. Target-language lines are slowed to this factor;
# English narration keeps its natural pace, so the lesson does not drag.
#
# Done by time-stretching rather than the API's `speed`: on eleven_v3 that parameter is
# barely applied. Measured over 3 takes of the same line, speed=0.7 gave a median 1.36s
# against 1.20s native — ~13% where 0.7 implies ~43% — with the ranges overlapping.
# Stretching scales vowel and consonant alike, so quantity contrasts (tak/tack) survive.
GUIDED_TARGET_SPEED = 0.75

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


# eleven_v3 performs a clarity cue like [clearly] literally — as a throat-clear before the
# line — which grates when every few lines have one. The scriptwriter reaches for it because
# the CEFR prompts say "speak slowly and clearly". Pace is handled by the guided slow-down
# and [slowly]; the clarity word itself is dropped, and the rest of the tag is kept.
_CLARITY_RE = re.compile(r"^(?:(?:very|extra|more|so)\s+)?clear(?:ly)?$", re.IGNORECASE)
_TAG_PARTS_RE = re.compile(r"\s*(?:,|\band\b|&)\s*", re.IGNORECASE)


# Cues are one or two words of emotion, tone or pace. The script writer sometimes adds stage
# directions to them ("[quietly, to Alex]", "[to Alex, in English]", "[from a distance]"); a
# voice cannot perform those and may read them aloud, so they are dropped before voicing.
_DIRECTION_RE = re.compile(r"\b(?:to\s+\w+|in\s+(?:english|finnish|swedish)|from\s+a\s+distance|calling\s+out)\b", re.IGNORECASE)


def sanitize_cues(text):
    """Remove direction words from bracket cues, keeping the emotion/tone/pace part."""
    def fix(match):
        parts = [p.strip() for p in match.group(0)[1:-1].split(",") if p.strip()]
        kept = [p for p in parts if not _DIRECTION_RE.search(p)]
        return "[%s]" % ", ".join(kept) if kept else ""
    out = AUDIO_TAG_RE.sub(fix, text or "")
    return re.sub(r"[ \t]{2,}", " ", out).strip()


def strip_clarity_cues(text):
    """Remove 'clearly'/'clear' from audio tags: "[slowly, clearly]" -> "[slowly]", "[Clearly]" -> ""."""
    def fix(match):
        parts = [p for p in _TAG_PARTS_RE.split(match.group(0)[1:-1]) if p.strip()]
        kept = [p for p in parts if not _CLARITY_RE.match(p.strip())]
        if len(kept) == len(parts):
            return match.group(0)
        return "[%s]" % ", ".join(kept) if kept else ""
    out = AUDIO_TAG_RE.sub(fix, text or "")
    return re.sub(r"[ \t]{2,}", " ", out).strip()


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



# --- Series pronunciation overrides -----------------------------------------

def load_pronunciation_overrides():
    """Load series/<active>/pronunciation.json, if present.

    These live with the SERIES, not the script, because scripts are regenerated:
    a fix hand-applied to a script's "tts_text" is silently lost the next time the
    episode is rewritten. Anything a voice reliably mispronounces belongs here.

    Each rule is {"match": "...", "say": "...", "word": true|false}. "word" (the
    default for a single word) matches on word boundaries so "tack" does not also
    rewrite "tacksam"; set it false to replace a literal phrase anywhere.
    """
    try:
        from series_paths import get_active, SERIES_ROOT
        slug = get_active()
        path = (SERIES_ROOT / slug / "pronunciation.json") if slug else (SERIES_ROOT / "pronunciation.json")
        if not path.exists():
            return []
        rules = json.loads(path.read_text(encoding="utf-8")).get("rules", [])
        if rules:
            print(f"   🗣️  {len(rules)} pronunciation override(s) from {path.name}")
        return rules
    except Exception as e:
        print(f"   ⚠️  Could not load pronunciation overrides: {e}")
        return []


def apply_pronunciation_overrides(text, rules):
    """Rewrite what gets SENT to the model. The caller keeps the original for subtitles.

    Matching ignores case but preserves it, so one rule for "tack" also covers the
    sentence-initial "Tack" that opens half these lines.
    """
    out = text
    for rule in rules:
        match, say = rule.get("match"), rule.get("say")
        if not match or say is None:
            continue

        # "whole_line" fires only when the line says nothing but this, keeping any
        # audio tag. Needed because the same word can want different treatment by
        # position: a bare "Tack." needs the "!" that shortens its vowel, while the
        # "tack" inside "Ett kort a: tack." is already short and must be left alone.
        if rule.get("whole_line"):
            if spoken_text(out).strip().lower() == match.strip().lower():
                tag = AUDIO_TAG_RE.match(out.strip())
                out = (tag.group(0) + " " + say) if tag else say
            continue

        def repl(m, say=say):
            found = m.group(0)
            if found[:1].isupper() and say[:1].islower():
                return say[:1].upper() + say[1:]
            return say

        pattern = (r"(?<!\w)%s(?!\w)" if rule.get("word", " " not in match) else r"%s")
        out = re.sub(pattern % re.escape(match), repl, out, flags=re.IGNORECASE)

    # A rule ending in "!" or "?" absorbs whatever terminal punctuation follows, so
    # "tack" -> "tack!" yields "tack!" in both "Ett kort a: tack." and "Ja. Tack!",
    # rather than "tack!." or "Tack!!".
    return re.sub(r"([!?])[!?.]+", r"\1", out)


_SERIES_TTS_SETTINGS = None
_LAST_LINE_TIMINGS = []   # filled by _generate_conversation_audio, saved beside the mp3


def _series_tts_settings():
    """series/<active>/tts_settings.json, if present (cached).

    {"default_model": "eleven_turbo_v2_5"} voices EVERY line with that model, so one character
    keeps one voice (mixing models changes the voice). "max_attempts" raises the retry count and
    "level_lines_dbfs" levels each line to the same loudness before joining. The older
    {"word_models": {"Moi": "eleven_turbo_v2_5"}} voices only target-language lines that
    contain that word with the given model instead of eleven_v3. Needed for Finnish:
    eleven_v3 reads a bare "Moi" the French way ("mwa"), however it is spelled or
    punctuated, and the Scribe check cannot hear the difference. The turbo model, which the
    Kielo app uses for Finnish speech, says it right (chosen by ear, 2026-10-24), but it
    garbles a lone "Huomenta" that eleven_v3 handles, so it is used only where needed.
    Turbo has no audio tags, so they are stripped from those lines; every other line keeps
    eleven_v3 and its tags.
    """
    global _SERIES_TTS_SETTINGS
    if _SERIES_TTS_SETTINGS is None:
        _SERIES_TTS_SETTINGS = {}
        try:
            from series_paths import get_active, SERIES_ROOT
            slug = get_active()
            path = (SERIES_ROOT / slug / "tts_settings.json") if slug else (SERIES_ROOT / "tts_settings.json")
            if path.exists():
                _SERIES_TTS_SETTINGS = json.loads(path.read_text(encoding="utf-8"))
                print(f"   🎙️  Series voice settings from {path.name}: {_SERIES_TTS_SETTINGS}")
        except Exception as e:
            print(f"   ⚠️  Could not load series voice settings: {e}")
    return _SERIES_TTS_SETTINGS


# --- Gemini TTS provider ------------------------------------------------------
# {"provider": "gemini", "gemini_voices": {"<cast id>": "<Gemini voice>"}} in a series'
# tts_settings.json voices every line with Gemini 3.8 Flash TTS. Chosen for Finnish: on
# 2026-10-24 eleven_v3 and turbo both failed by ear ("Moi" read as "mwa"; turbo robotic),
# while Gemini's Sulafat voice said it right. The model is voice-dependent (Leda and Aoede
# said "Moa"), so every character's voice has to be listened to. The bracketed mood cues in
# the script become Gemini "style" directions; Finnish lines also get "speaking Finnish" to
# pin the language, and guided lines "speaking slowly" instead of being time-stretched.

GEMINI_TTS_MODEL = "gemini-3.8-flash-tts"
_LANGUAGE_NAMES = {"fi": "Finnish", "sv": "Swedish", "en": "English"}
_GEMINI_CLIENT = None
_GEMINI_VOICES = None


def _gemini_voice_for(voice_id):
    """Gemini voice for a line, found through the cast: ElevenLabs voice_id -> cast id -> voice."""
    global _GEMINI_VOICES
    settings = _series_tts_settings()
    if _GEMINI_VOICES is None:
        _GEMINI_VOICES = {}
        try:
            from series_paths import get_active, SERIES_ROOT
            slug = get_active()
            base = (SERIES_ROOT / slug) if slug else SERIES_ROOT
            cast = json.loads((base / "cast.json").read_text(encoding="utf-8"))["characters"]
            names = settings.get("gemini_voices", {})
            for cid, ch in cast.items():
                if cid in names:
                    _GEMINI_VOICES[ch.get("voice_id")] = names[cid]
        except Exception as e:
            print(f"   ⚠️  Could not map cast to Gemini voices: {e}")
    return _GEMINI_VOICES.get(voice_id) or settings.get("gemini_default_voice", "Kore")


def _gemini_pcm(text, voice, extra_style=()):
    """One line through Gemini TTS -> raw 16-bit mono PCM at PCM_SAMPLE_RATE."""
    import base64
    from pydub import AudioSegment
    global _GEMINI_CLIENT
    if _GEMINI_CLIENT is None:
        from google import genai
        _GEMINI_CLIENT = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    tags = [t[1:-1].strip().lower() for t in AUDIO_TAG_RE.findall(text)]
    plain = re.sub(r"[ \t]{2,}", " ", AUDIO_TAG_RE.sub(" ", text)).strip()
    style = ", ".join([t for t in tags if t] + list(extra_style))
    part = {"type": "text", "text": plain}
    if style:
        part["annotations"] = [{"type": "speech_metadata", "style": style}]
    model = _series_tts_settings().get("gemini_model", GEMINI_TTS_MODEL)
    last = None
    for attempt in range(4):
        try:
            r = _GEMINI_CLIENT.interactions.create(
                model=model, input=[{"type": "user_input", "content": [part]}],
                response_format={"type": "audio"},
                generation_config={"speech_config": [{"voice": voice}]},
            )
            wav = base64.b64decode(r.output_audio.data)
            seg = (AudioSegment.from_wav(io.BytesIO(wav)).set_frame_rate(PCM_SAMPLE_RATE)
                   .set_channels(PCM_CHANNELS).set_sample_width(PCM_SAMPLE_WIDTH))
            return seg.raw_data
        except Exception as e:                       # rate limits and blips: back off and retry
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


# --- Approved-line cache -------------------------------------------------------
# {"cache_lines": true} in a series' tts_settings.json keeps every line that passed the
# check in .tts_cache/, keyed by what is actually sent (provider/model, voice, language,
# final text). A rebuild then reuses the takes already accepted and only voices lines that
# are new or changed, so one bad line can be redone without touching the rest. To redo one
# line: python tts_generator.py --redo "Huomenta."  (drops its cached takes, then rebuild).

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tts_cache")


def _cache_key(model_id, voice_id, iso, text):
    import hashlib
    return hashlib.sha1("|".join([model_id, voice_id, iso, text]).encode("utf-8")).hexdigest()[:16]


def _cache_get(key):
    path = os.path.join(CACHE_DIR, key + ".pcm")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    return None


def _cache_put(key, pcm, text, voice_id):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(os.path.join(CACHE_DIR, key + ".pcm"), "wb") as f:
        f.write(pcm)
    idx_path = os.path.join(CACHE_DIR, "index.json")
    try:
        idx = json.load(open(idx_path, encoding="utf-8"))
    except Exception:
        idx = {}
    idx[key] = {"text": text, "voice_id": voice_id, "seconds": round(len(pcm) / (PCM_SAMPLE_RATE * PCM_SAMPLE_WIDTH * PCM_CHANNELS), 2)}
    json.dump(idx, open(idx_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def redo_cached_line(fragment):
    """Drop cached takes whose text contains `fragment` (case-insensitive). Returns how many."""
    idx_path = os.path.join(CACHE_DIR, "index.json")
    try:
        idx = json.load(open(idx_path, encoding="utf-8"))
    except Exception:
        return 0
    gone = [k for k, v in idx.items() if fragment.lower() in v.get("text", "").lower()]
    for k in gone:
        try:
            os.remove(os.path.join(CACHE_DIR, k + ".pcm"))
        except OSError:
            pass
        idx.pop(k)
    json.dump(idx, open(idx_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return len(gone)


# A spoken word needs a minimum length: a take clipped to half a word still transcribes as
# the whole word often enough to pass the check, so very short audio is retried too.
MIN_SECONDS_PER_LETTER = 0.045

# eleven_v3 sometimes returns a take cut off in the middle of the last sound ("Mä opiskelen"
# ended at 0.64 s on "-ske", still at full loudness). Such a take still transcribes as the full
# line, so the end itself is checked: a finished take fades out (median last 20 ms around 40 dB
# under the line), a cut one ends at least as loud as the line's average. Applies to every
# line, English included (15 of 357 lines in Everyday Finnish A1 episodes 1-9 were cut).
CLIPPED_TAIL_MS = 20
CLIPPED_TAIL_DB = 0.0


def _ends_mid_sound(pcm_bytes):
    """True when a take's last few milliseconds are nearly as loud as the line: it was cut off."""
    from pydub import AudioSegment
    if not pcm_bytes:
        return False
    seg = AudioSegment(data=pcm_bytes, sample_width=PCM_SAMPLE_WIDTH, frame_rate=PCM_SAMPLE_RATE,
                       channels=PCM_CHANNELS)
    if len(seg) <= CLIPPED_TAIL_MS * 2 or seg.dBFS == float("-inf"):
        return False
    return seg[-CLIPPED_TAIL_MS:].dBFS - seg.dBFS > CLIPPED_TAIL_DB


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


def synthesize_line(elevenlabs_client, item, target_iso, locator, index, total, overrides=()):
    """Synthesize one line, verifying target-language lines and retrying a misread.

    Returns (pcm_bytes, warning_or_None).
    """
    # "tts_text" is what gets SENT to the model; "text" stays the true wording for
    # subtitles and for the verification comparison below. Needed because a voice may
    # refuse a contrast as spelled — Sten renders "Tak" as /tak/ — and a respelling
    # like "Taak" is the only lever that reaches the acoustics.
    expected = item.get("text", "")
    text = sanitize_cues(strip_clarity_cues(item.get("tts_text") or expected))
    voice_id = item.get("voice_id", "")
    iso = _line_language(item, target_iso)
    # Series overrides apply only to target-language lines, and never override an
    # explicit per-line tts_text.
    if overrides and iso == target_iso and not item.get("tts_text"):
        text = apply_pronunciation_overrides(text, overrides)
    # A line may opt out with "verify": false. Needed for lines that are correct but
    # untranscribable as written — e.g. reciting "Å, Ä, Ö", where Å is genuinely
    # voiced [oː] and Scribe duly returns "O", which no string comparison can accept.
    should_verify = (
        VERIFY_PRONUNCIATION
        and item.get("verify", True)
        and iso == target_iso
        and spoken_text(expected)
    )

    settings = _series_tts_settings()
    model_id = settings.get("default_model") or MODEL_ID
    if iso == target_iso:
        for word, word_model in (_series_tts_settings().get("word_models") or {}).items():
            if re.search(r"(?<!\w)%s(?!\w)" % re.escape(word), spoken_text(text), re.IGNORECASE):
                model_id = word_model
                break
    use_gemini = settings.get("provider") == "gemini"
    if not use_gemini and not model_id.startswith("eleven_v3"):   # no audio tags outside v3
        text = re.sub(r"[ \t]{2,}", " ", AUDIO_TAG_RE.sub(" ", text)).strip()
    gemini_voice = _gemini_voice_for(voice_id) if use_gemini else None
    gemini_extra = []
    if use_gemini and iso == target_iso:
        gemini_extra.append("speaking " + _LANGUAGE_NAMES.get(iso, iso))
        if item.get("_slow_style"):
            gemini_extra.append("slowly and clearly")

    kwargs = {
        "voice_id": voice_id,
        "text": text,
        "model_id": model_id,
        "language_code": iso,
        "output_format": LINE_OUTPUT_FORMAT,
    }
    if locator:
        kwargs["pronunciation_dictionary_locators"] = [locator]

    best_audio, best_ratio, best_heard = None, -1.0, ""

    cache_key = None
    if settings.get("cache_lines"):
        cache_key = _cache_key(
            "gemini:" + settings.get("gemini_model", GEMINI_TTS_MODEL) if use_gemini else model_id,
            (gemini_voice if use_gemini else voice_id) or "", iso, text + "|" + "|".join(gemini_extra),
        )
        cached = _cache_get(cache_key)
        if cached is not None and not _ends_mid_sound(cached):
            return cached, None

    max_attempts = int(settings.get("max_attempts", MAX_ATTEMPTS))
    for attempt in range(1, max_attempts + 1):
        if use_gemini:
            audio = _gemini_pcm(text, gemini_voice, gemini_extra)
        else:
            audio = b"".join(elevenlabs_client.text_to_speech.convert(**kwargs))

        clipped = _ends_mid_sound(audio)
        if not should_verify:
            if clipped:
                if best_audio is None:
                    best_audio, best_heard = audio, "(ends mid-sound: clipped?)"
                print(f"   ↻ [{index}/{total}] Attempt {attempt}: the take ends mid-sound (clipped?): "
                      f"{spoken_text(expected)!r}")
                continue
            if cache_key:
                _cache_put(cache_key, audio, text, voice_id)
            return audio, None

        try:
            heard = transcribe(elevenlabs_client, audio, iso)
        except Exception as e:
            # Verification is a safety net, not a gate — never lose good audio to it.
            print(f"   ⚠️  [{index}/{total}] Could not verify: {e}")
            return audio, None

        ok, ratio = pronunciation_matches(expected, heard)
        letters = sum(ch.isalpha() for ch in spoken_text(expected))
        seconds = len(audio) / (PCM_SAMPLE_RATE * PCM_SAMPLE_WIDTH * PCM_CHANNELS)
        if ok and seconds < letters * MIN_SECONDS_PER_LETTER:
            ok = False
            heard = f"{heard} (only {seconds:.2f}s: clipped?)"
        elif ok and clipped:
            ok = False
            heard = f"{heard} (ends mid-sound: clipped?)"
        if ok:
            if cache_key:
                _cache_put(cache_key, audio, text, voice_id)
            if attempt > 1:
                print(f"   ✓ [{index}/{total}] Correct on attempt {attempt}: {spoken_text(expected)!r}")
            return audio, None

        if ratio > best_ratio:
            best_audio, best_ratio, best_heard = audio, ratio, heard
        print(f"   ↻ [{index}/{total}] Attempt {attempt}: expected {spoken_text(expected)!r}, heard {heard!r}")

    warning = (
        f"line {index}: expected {spoken_text(expected)!r}, heard {best_heard!r} "
        f"after {max_attempts} attempts"
    )
    return best_audio, warning


def _stretch(pcm_bytes, factor):
    """Slow raw PCM by `factor` via ffmpeg's atempo, preserving pitch."""
    if not pcm_bytes or factor == 1.0:
        return pcm_bytes
    import subprocess
    cmd = [
        "ffmpeg", "-v", "error",
        "-f", "s16le", "-ar", str(PCM_SAMPLE_RATE), "-ac", str(PCM_CHANNELS), "-i", "pipe:0",
        "-filter:a", "atempo=%s" % factor,
        "-f", "s16le", "-ar", str(PCM_SAMPLE_RATE), "-ac", str(PCM_CHANNELS), "pipe:1",
    ]
    try:
        proc = subprocess.run(cmd, input=pcm_bytes, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=True)
        return proc.stdout or pcm_bytes
    except Exception as e:
        print(f"   ⚠️  Could not slow line ({e}); using it at full speed.")
        return pcm_bytes


def _silence(ms):
    n_samples = int(PCM_SAMPLE_RATE * ms / 1000.0)
    return b"\x00" * (n_samples * PCM_SAMPLE_WIDTH * PCM_CHANNELS)


def _generate_conversation_audio(elevenlabs_client, dialogue_list, language, locator,
                                 fmt="conversation"):
    """Synthesize a conversation one line at a time and concatenate.

    Returns (mp3_bytes, warnings). See the note by MODEL_ID for why this does not
    use text_to_dialogue.
    """
    from pydub import AudioSegment
    from language_config import get_iso_code

    target_iso = get_iso_code(language)
    overrides = load_pronunciation_overrides()
    total = len(dialogue_list)
    use_gemini = _series_tts_settings().get("provider") == "gemini"
    if use_gemini and fmt == "guided":
        dialogue_list = [
            ({**d, "_slow_style": True} if _line_language(d, target_iso) == target_iso else d)
            for d in dialogue_list
        ]

    def task(i):
        return synthesize_line(
            elevenlabs_client, dialogue_list[i], target_iso, locator, i + 1, total,
            overrides=overrides,
        )

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = list(pool.map(task, range(total)))

    slow = GUIDED_TARGET_SPEED if fmt == "guided" else 1.0
    if use_gemini:
        slow = 1.0          # Gemini is asked to speak slowly; no time-stretching
    if slow != 1.0:
        print(f"   🐢 Slowing {language} lines to {slow}x for beginners")

    pcm_parts, warnings = [], []
    # Exact start/end of every line in the joined audio. sfx_mixer uses these instead of
    # re-transcribing: Whisper merges and splits neighbouring lines in English-led episodes,
    # which breaks the one-segment-per-line assumption (and the sound effects with it).
    global _LAST_LINE_TIMINGS
    _LAST_LINE_TIMINGS = []
    bytes_per_ms = PCM_SAMPLE_RATE * PCM_SAMPLE_WIDTH * PCM_CHANNELS / 1000.0
    cursor_ms = 0.0
    for i, (audio, warning) in enumerate(results):
        if warning:
            warnings.append(warning)
        if audio is None:
            continue
        if slow != 1.0 and _line_language(dialogue_list[i], target_iso) == target_iso:
            audio = _stretch(audio, slow)
        level = _series_tts_settings().get("level_lines_dbfs")
        if level is not None:
            seg = AudioSegment(data=audio, sample_width=PCM_SAMPLE_WIDTH, frame_rate=PCM_SAMPLE_RATE, channels=PCM_CHANNELS)
            if seg.dBFS != float("-inf"):
                audio = seg.apply_gain(level - seg.dBFS).raw_data
        if pcm_parts:
            same_speaker = (
                dialogue_list[i].get("voice_id") == dialogue_list[i - 1].get("voice_id")
            )
            gap_ms = GAP_SAME_SPEAKER_MS if same_speaker else GAP_SPEAKER_CHANGE_MS
            pcm_parts.append(_silence(gap_ms))
            cursor_ms += gap_ms
        start_ms = cursor_ms
        cursor_ms += len(audio) / bytes_per_ms
        _LAST_LINE_TIMINGS.append({
            "start": round(start_ms / 1000, 3), "end": round(cursor_ms / 1000, 3),
            "text": spoken_text(dialogue_list[i].get("text", "")),
        })
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
        {"text": strip_clarity_cues(d.get("text", "")), "voice_id": d.get("voice_id", "")}
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
                elevenlabs_client, dialogue_list, language, locator, fmt=fmt,
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
        timings_path = os.path.splitext(output_path)[0] + ".timings.json"
        if script_type == "conversation" and len(_LAST_LINE_TIMINGS) == len(dialogue_list):
            with open(timings_path, "w", encoding="utf-8") as f:
                json.dump(_LAST_LINE_TIMINGS, f, ensure_ascii=False, indent=1)
            print(f"   ⏱️  Saved exact line timings: {os.path.basename(timings_path)}")
        elif os.path.exists(timings_path):
            os.remove(timings_path)
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
    if len(sys.argv) >= 3 and sys.argv[1] == "--redo":
        n = redo_cached_line(sys.argv[2])
        print(f"Dropped {n} cached take(s) containing {sys.argv[2]!r}. Rebuild to voice them again.")
        return
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