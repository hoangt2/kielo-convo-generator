#!/usr/bin/env python3
"""
Finnish Grammar and Naturalness Checker

This script checks and fixes Finnish grammar and naturalness in generated 
conversation scripts, ensuring the Finnish sounds like natural spoken language.
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError

# --- Load environment variables ---
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("❌ GEMINI_API_KEY not found. Please add it to your .env file.")

# Initialize Gemini client
client = genai.Client(api_key=api_key)


def check_and_fix_finnish(dialogue_list: list) -> tuple[list, bool]:
    """
    Check Finnish grammar and naturalness, fix issues if found.
    Returns (fixed_dialogue_list, was_modified).
    """
    
    # Extract just the text for checking
    dialogue_texts = [item.get("text", "") for item in dialogue_list]
    dialogue_json = json.dumps(dialogue_texts, ensure_ascii=False, indent=2)
    
    prompt = f"""
You are an expert Finnish language reviewer specializing in natural spoken Finnish (puhekieli).

Review the following Finnish dialogue lines and check for:
1. **Grammar errors** - incorrect verb conjugations, case endings, word order
2. **Unnatural phrasing** - text that sounds too formal/written rather than spoken
3. **Missing colloquialisms** - spoken Finnish often contracts words (e.g., "minä" → "mä", "sinä" → "sä")
4. **Stiff expressions** - phrases that would sound unnatural in casual conversation

For each line, if there are issues:
- Fix the Finnish to sound more natural and conversational
- Keep the emotion tags in brackets at the start (e.g., [excited], [calm])
- Preserve the meaning but make it sound like real spoken Finnish

Return a JSON object with:
{{
    "has_issues": true/false,
    "fixed_lines": ["line1", "line2", ...],  // Same order as input, with fixes applied
    "changes_made": [  // List of changes, empty if no issues
        {{"original": "...", "fixed": "...", "reason": "..."}}
    ]
}}

Dialogue lines to review:
{dialogue_json}

Important: 
- If the Finnish is already natural and correct, set "has_issues" to false and return the original lines unchanged.
- The "fixed_lines" array MUST have the same number of elements as the input.
- Focus on making the dialogue sound like real Finnish people actually speak.
"""
    
    try:
        config = types.GenerateContentConfig(
            temperature=0.3,  # Lower temperature for more consistent corrections
            response_mime_type="application/json",
            system_instruction="You are an expert Finnish linguist who specializes in natural spoken Finnish. You strictly output valid JSON."
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=config,
        )
        
        result = json.loads(response.text.strip())
        
        if result.get("has_issues", False):
            fixed_lines = result.get("fixed_lines", [])
            changes = result.get("changes_made", [])
            
            # Apply fixes to the original dialogue list
            if len(fixed_lines) == len(dialogue_list):
                for i, item in enumerate(dialogue_list):
                    item["text"] = fixed_lines[i]
                
                # Print changes
                if changes:
                    print("   📝 Changes made:")
                    for change in changes[:5]:  # Show max 5 changes
                        print(f"      • \"{change.get('original', '')[:40]}...\"")
                        print(f"        → \"{change.get('fixed', '')[:40]}...\"")
                        print(f"        Reason: {change.get('reason', 'N/A')}")
                
                return dialogue_list, True
            else:
                print("   ⚠️  Warning: Fixed lines count mismatch, keeping original")
                return dialogue_list, False
        else:
            return dialogue_list, False
            
    except APIError as e:
        print(f"   ❌ API Error during grammar check: {e}")
        return dialogue_list, False
    except json.JSONDecodeError as e:
        print(f"   ❌ JSON decode error: {e}")
        return dialogue_list, False


def process_script_file(file_path: Path) -> bool:
    """Process a single script file, checking and fixing Finnish."""
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"   ❌ Error reading {file_path.name}: {e}")
        return False
    
    dialogue_list = data.get("dialogue_list", [])
    if not dialogue_list:
        print(f"   ⚠️  No dialogue found in {file_path.name}")
        return False
    
    # Check and fix
    fixed_dialogue, was_modified = check_and_fix_finnish(dialogue_list)
    
    if was_modified:
        # Save the fixed version
        data["dialogue_list"] = fixed_dialogue
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"   ✅ Fixed and saved: {file_path.name}")
        return True
    else:
        print(f"   ✓ Finnish looks natural: {file_path.name}")
        return False


def main():
    """Process all script files in scripts/ folder."""
    
    print("\n" + "="*60)
    print("🇫🇮 FINNISH GRAMMAR & NATURALNESS CHECKER")
    print("="*60)
    
    # Determine which folder to check
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'podcast':
        scripts_folder = Path("podcast_scripts")
    else:
        scripts_folder = Path("scripts")
    
    if not scripts_folder.exists():
        print(f"❌ Folder '{scripts_folder}' not found. Run generate_scripts.py first.")
        sys.exit(1)
    
    # Get all JSON files
    script_files = list(scripts_folder.glob("*.json"))
    
    if not script_files:
        print(f"❌ No script files found in '{scripts_folder}/'")
        sys.exit(1)
    
    print(f"\n📂 Found {len(script_files)} script(s) in '{scripts_folder}/'")
    
    fixed_count = 0
    for script_file in script_files:
        print(f"\n🔍 Checking: {script_file.name}")
        if process_script_file(script_file):
            fixed_count += 1
    
    print("\n" + "="*60)
    if fixed_count > 0:
        print(f"🎉 Done! Fixed {fixed_count}/{len(script_files)} script(s)")
    else:
        print("✅ All scripts already have natural Finnish!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
