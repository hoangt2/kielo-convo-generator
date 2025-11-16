# Convo Generator

A Python tool for generating Finnish conversation scripts and podcast episodes using Google Gemini AI, with support for TTS, video generation, and subtitle embedding.

## Setup

1. **Create a virtual environment and install dependencies (if any):**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   # If you have a requirements.txt, run:
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   - Create a `.env` file in the project root
   - Add your API keys (example):
     ```
     GEMINI_API_KEY=your_gemini_api_key
     ELEVENLABS_API_KEY=your_elevenlabs_api_key
     ```

## Quick Start

### 1. Generate Ideas
```bash
python generate_ideas_json.py                # Conversation ideas
python generate_ideas_json.py podcast        # Podcast ideas
```
Output: `ideas.json` or `podcast_ideas.json`

### 2. Generate Scripts
```bash
python generate_scripts.py                   # Conversation scripts
python generate_scripts.py podcast           # Podcast scripts
```
Output: JSON dialogue files in `scripts/` or `podcast_scripts/`

### 3. Generate Illustrations
```bash
python generate_illustrations.py              # Generate visual assets for videos
```
Output: Illustration files in `illustrations/`

### 4. Generate Audio
```bash
python tts_generator.py                      # Convert scripts to MP3
```
Output: Audio files in `mp3/`

### 5. Generate Videos
```bash
python generate_videos.py                    # Create video from audio + illustrations
```
Output: Videos in `output_videos/`

### 5. Add Music & Subtitles
```powershell
# Add background music to videos
python music_mixer.py

# Auto-generate and embed subtitles
python generate_subtitled_videos.py
```
These steps typically:
- Add background music to videos in `output_videos/`
- Auto-generate subtitles (e.g. Whisper) and optionally translate them
- Embed subtitles into videos and archive subtitle files

Output: Final videos in `final_subtitled_videos/`

## Full Pipeline

For complete automation from ideas to final videos (example):
```powershell
python generate_ideas_json.py
python generate_scripts.py
python tts_generator.py
python generate_videos.py
python music_mixer.py
python generate_subtitled_videos.py
```

## Project Structure

- `generate_ideas_json.py` - Generate conversation/podcast ideas via Gemini
- `generate_scripts.py` - Convert ideas into dialogue scripts
- `tts_generator.py` - Generate audio from scripts (ElevenLabs TTS)
- `generate_videos.py` - Create videos from audio + illustrations
- `generate_illustrations.py` - Generate visual assets
-- `subtitle_generator.py` - Auto-generate subtitles (helper functions)
-- `music_mixer.py` - Add background music to videos
-- `generate_subtitled_videos.py` - Create subtitled/final videos

## Output Folders

- `scripts/` - Conversation dialogue files
- `podcast_scripts/` - Podcast script files
- `mp3/` - Generated audio files
- `output_videos/` - Raw generated videos
- `final_subtitled_videos/` - Finished videos with music and subtitles
- `illustrations/` - Generated visual assets
-- `subtitles/` - Subtitle files (current)
-- `subtitles_archived/` - Archived subtitle files

## Requirements

- Python 3.8+
- Google Gemini API key
- ElevenLabs API key (for TTS)
- FFmpeg (for video/audio processing)
