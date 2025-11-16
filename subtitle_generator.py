import os
import time
import datetime
import re
import ffmpeg
from pathlib import Path
from typing import List, Tuple
from faster_whisper import WhisperModel

from dotenv import load_dotenv
load_dotenv()


try:
    from google import genai
    from google.genai.errors import APIError
    # Initialize a global Gemini client using GEMINI_API_KEY from the environment
    try:
        client = genai.Client()
    except Exception:
        client = None
except Exception:
    genai = None
    APIError = Exception
    client = None

# ... (ASS_HEADER, format_time_ass, extract_audio, transcribe_finnish, 
# _get_openai_client, translate_texts_fi_to_en, generate_ass_file, 
# embed_subtitles, cleanup_temp_file remain the same) ...

ASS_HEADER = """
[Script Info]
Title: Auto-generated Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Finnish,Roboto,12,&H00ea72ac,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,15,1
Style: English,Roboto,12,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,15,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def format_time_ass(seconds: float) -> str:
    delta = datetime.timedelta(seconds=seconds)
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds_val = divmod(remainder, 60)
    centiseconds = delta.microseconds // 10000
    return f"{hours:d}:{minutes:02d}:{seconds_val:02d}.{centiseconds:02d}"


def extract_audio(video_file: Path) -> Path:
    audio_file = video_file.with_suffix(".wav")
    ffmpeg.input(str(video_file)).output(
        str(audio_file), acodec="pcm_s16le", ac=1, ar="16000"
    ).run(overwrite_output=True, quiet=True)
    return audio_file


def transcribe_finnish(audio_file: Path, model_name: str = "large-v3"):
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    finnish_segments, info = model.transcribe(str(audio_file), language="fi", beam_size=5)
    return list(finnish_segments), info


def _get_gemini_client():
    if client is None:
        raise RuntimeError(
            "Gemini client is not initialized. Check 'google-genai' installation and GEMINI_API_KEY environment variable."
        )
    return client


def translate_texts_fi_to_en(texts: List[str], model: str = "gemini-2.5-flash") -> List[str]:
    """Translate a list of Finnish strings to English using Google Gemini.

    Args:
        texts: list of Finnish strings.
        model: Gemini model name suitable for translation.

    Returns:
        List of translated English strings in the same order.
    """
    client = _get_gemini_client()

    batch_size = 32
    outputs: List[str] = []

    system_instruction = (
        "You are a professional translator. Translate from Finnish to English. "
        "Preserve meaning, tone, and proper names. Return only the translated text."
    )

    # Configure model for deterministic output
    config = genai.types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.0,
    )

    for i in range(0, len(texts), batch_size):
        chunk = texts[i : i + batch_size]
        numbered = "\n\n".join(f"{idx+1}. {t}" for idx, t in enumerate(chunk))
        user_prompt = (
            "Translate each numbered Finnish line to English. "
            "Respond with the translations only, one per line, in the same numbering order, without extra commentary.\n\n"
            f"{numbered}"
        )

        try:
            response = client.models.generate_content(
                model=model,
                contents=user_prompt,
                config=config,
            )
            text = response.text or ""
        except APIError as e:
            print(f"Gemini API Error: {e}")
            text = ""
        except Exception as e:
            print(f"Unexpected error calling Gemini: {e}")
            text = ""

        # Split by lines and clean numbering
        lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
        cleaned: List[str] = []
        for ln in lines:
            cleaned.append(re.sub(r'^\d+[\.)]\s*', '', ln).strip())

        if len(cleaned) != len(chunk):
            print(f"Warning: Translation response line count ({len(cleaned)}) does not match input chunk size ({len(chunk)}). Padding/truncating.")
            cleaned = (cleaned + [""] * len(chunk))[: len(chunk)]

        outputs.extend(cleaned)

    return outputs


def generate_ass_file(subtitle_file: Path, finnish_segments, english_texts: List[str]):
    with open(subtitle_file, "w", encoding="utf-8") as f:
        f.write(ASS_HEADER)
        for fin_seg, eng_text in zip(finnish_segments, english_texts):
            start = format_time_ass(fin_seg.start)
            end = format_time_ass(fin_seg.end)
            fi_line = fin_seg.text.strip().replace("\n", " ")
            en_line = eng_text.strip().replace("\n", " ")
            f.write(f"Dialogue: 0,{start},{end},Finnish,,0,0,0,,{fi_line}\n")
            f.write(f"Dialogue: 0,{start},{end},English,,0,0,0,,{en_line}\n")


def embed_subtitles(video_file: Path, subtitle_file: Path, output_file: Path):
    input_video = ffmpeg.input(str(video_file))
    input_audio = input_video.audio
    subtitled_video = ffmpeg.filter(
        input_video.video, "subtitles", str(subtitle_file.as_posix())
    )
    ffmpeg.output(
        subtitled_video,
        input_audio,
        str(output_file), # Writes to the path specified by the caller
        vcodec="libx264",
        acodec="aac",
        strict="experimental",
    ).run(overwrite_output=True, quiet=True)


def cleanup_temp_file(file_path: Path):
    if file_path and file_path.exists():
        try:
            os.remove(file_path)
        except Exception:
            pass


def generate_subtitles(
    video_path: str, 
    output_video_path: str, # NEW REQUIRED ARGUMENT
    translation_model: str = "gpt-4o-mini", 
    subtitle_folder: str = None
):
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

    video_file = Path(video_path)
    output_video_file = Path(output_video_path) # USE THIS FOR FINAL OUTPUT
    
    if not video_file.is_file():
        print(f"Error: Video file not found at '{video_path}'")
        return

    print(f"Processing video: {video_file.name}")
    start_time = time.time()

    audio_file = video_file.with_suffix(".wav")
    
    # Determine the location of the ASS file to CHECK for existence
    if subtitle_folder:
        subtitle_check_file = Path(subtitle_folder) / video_file.with_suffix(".ass").name
    else:
        subtitle_check_file = video_file.with_suffix(".ass")
        
    # Determine the location of the ASS file to CREATE (always next to the video for process_batch.py to move)
    subtitle_create_file = video_file.with_suffix(".ass")
    
    # --- Check for existing subtitle file ---
    subtitles_exist = subtitle_check_file.is_file()
    
    if subtitles_exist:
        choice = input(
            f"Subtitle file '{subtitle_check_file.name}' already exists in '{subtitle_check_file.parent.name}/'. "
            "Do you want to re-transcribe/translate (r), or skip to embedding the existing file (e)? "
            "Enter 'r' or 'e': "
        ).lower()
        
        if choice == 'e':
            print("Skipping transcription and translation. Embedding existing subtitle file...")
            try:
                print(f"Step 5: Embedding subtitles into video, writing to: {output_video_file.name}")
                
                # IMPORTANT: Use the check path for embedding and the final output path
                embed_subtitles(video_file, subtitle_check_file, output_video_file) 
                print(f"Subtitled video created: '{output_video_file.name}'")
            except ffmpeg.Error as e:
                print("FFmpeg Error:", e.stderr.decode() if e.stderr else str(e))
            except Exception as e:
                print("Unexpected error:", e)
            finally:
                pass
            print(f"Finished in {time.time() - start_time:.2f} seconds.")
            return

        print("Proceeding with full transcription, translation, and embedding process.")
    # -------------------------------------------------------------------------

    try:
        # Steps 1-4 (Audio, Transcribe, Translate, Write ASS) remain the same...
        print("Step 1: Extracting audio...")
        audio_file = extract_audio(video_file)
        print("Audio extracted.")

        print("Step 2: Transcribing to Finnish with Whisper...")
        finnish_segments, info = transcribe_finnish(audio_file)
        print(f"Detected language '{info.language}' ({info.language_probability:.2f}).")

        print("Step 3: Translating Finnish → English with Gemini...")
        fi_texts = [s.text.strip().replace("\n", " ") for s in finnish_segments]
        en_texts = translate_texts_fi_to_en(fi_texts, model=translation_model)
        print("Translation complete.")

        print("Step 4: Writing ASS subtitle file...")
        generate_ass_file(subtitle_create_file, finnish_segments, en_texts)
        print(f"ASS file '{subtitle_create_file.name}' created.")

        print("Step 5: Embedding subtitles into video...")
        # IMPORTANT: Use subtitle_create_file and the new output_video_file path
        embed_subtitles(video_file, subtitle_create_file, output_video_file)
        print(f"Subtitled video created: '{output_video_file.name}'")

    except ffmpeg.Error as e:
        print("FFmpeg Error:", e.stderr.decode() if e.stderr else str(e))
    except Exception as e:
        print("Unexpected error:", e)
    finally:
        print("Cleaning up temporary files...")
        cleanup_temp_file(audio_file)

    print(f"Finished in {time.time() - start_time:.2f} seconds.")


if __name__ == "__main__":
    # Example usage for single video testing/re-embedding:
    SOURCE_DIR = "source"
    SUBTITLES_DIR = "subtitles"
    OUTPUT_DIR = "output" # Define output dir for testing
    
    video_filename = "tilata.mp4"
    
    input_video_path = Path(SOURCE_DIR) / video_filename
    final_output_path = Path(OUTPUT_DIR) / video_filename # Target name in output folder

    if not input_video_path.exists():
        print(f"Video '{input_video_path}' not found.")
        print(f"Please ensure the video is in the '{SOURCE_DIR}' folder.")
    else:
        print(f"Attempting to process video from: {input_video_path}")
        generate_subtitles(
            str(input_video_path), 
            str(final_output_path), 
            subtitle_folder=SUBTITLES_DIR
        )
