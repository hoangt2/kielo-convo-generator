#!/usr/bin/env python3
"""
Grammar and Naturalness Checker

This script checks and fixes grammar and naturalness in generated
conversation scripts, ensuring the target language sounds like natural
spoken language. Language-specific anti-patterns are applied when available
(currently Finnish has detailed rules; other languages use generic checking).
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


# --- Detailed system instruction for grammar checking ---
def _system_instruction(language):
    return f"""You are a native {language} speaker and expert linguist who reviews spoken {language} dialogue.

CRITICAL RULE: You must think and reason ONLY in {language}. Never translate from English.
Every sentence must pass this test: "Would a native {language} speaker actually say this in a casual phone call or face-to-face conversation?"

You are extremely strict and critical. You MUST flag any line that sounds even slightly unnatural."""

# --- Specific anti-patterns to check for ---
ANTI_PATTERNS_PROMPT = """
## SPECIFIC ERROR PATTERNS TO CHECK FOR

You MUST check every line against ALL of the following common AI-generated Finnish mistakes:

### 1. Wrong conditional vs. indicative mood
- ❌ "Oisitpa sä ihana!" (conditional = "I wish you were wonderful" — WRONG meaning)
- ✅ "Ootpa sä ihana!" (indicative = "You ARE so wonderful!" — CORRECT meaning)
- The conditional "-isi-" form changes meaning completely. Flag ANY misuse.

### 2. English-influenced sentence structure (thinking in English, writing in Finnish)
- ❌ "mä aattelin et jos mä voisin tulla töitten jälkeen tuomaan sulle vähän kukkia" 
  (= direct translation of "I thought that if I could come after work to bring you some flowers")
- ✅ "aattelin kysyä, sopisko jos tulisin töitten jälkeen käymään ja toisin samalla vähän kukkia"
  (= natural Finnish way to express the same idea)
- Flag sentences where the thought process follows English word order or English idioms.

### 3. Wrong infinitive constructions
- ❌ "Soitin vaan toivottaa hyvää naistenpäivää" (basic infinitive after verb of purpose — awkward)
- ✅ "Soitin vaan toivottaakseni hyvää naistenpäivää" (translative infinitive = "in order to wish")

### 4. Over-literal translations of common expressions
- ❌ "Totta kai sä voit!" (= "Of course you CAN!" — too literal, permission-focused)
- ✅ "Totta kai käy!" or "Totta kai sopii!" (= "Of course that works!" — natural agreement)
- ❌ "Ootan sua innolla!" (= "I'm waiting for you eagerly" — stiff, sounds translated from "I look forward to seeing you")
- ✅ "Nähdään silloin!" or "Nähdään sit!" (= "See you then!" — natural)

### 5. Missing or wrong colloquial forms
- In casual spoken Finnish, people use: mä/mun/mua, sä/sun/sua, oon/oot, ei oo, meen/tuun, täs/siel
- Flag any formal written forms that should be colloquial in a casual context.

### 6. Unnatural filler/flow
- Spoken Finnish uses: "no", "nii", "tota", "niinku", "joo", "ai", "eiku"
- If dialogue feels robotic or too clean without any natural fillers, flag it.

### 7. Tone tag consistency
- If a line is tagged [pleased] but Matti is asking a scheduling question, suggest a more fitting tag.
- Emotion tags should match what a person would naturally feel saying that line.
"""


# Helper to read language from ideas.json metadata
def _detect_language():
    """Read language from ideas.json metadata."""
    ideas_path = Path("ideas.json")
    if ideas_path.exists():
        try:
            data = json.loads(ideas_path.read_text(encoding="utf-8"))
            return data.get("metadata", {}).get("language", "Finnish")
        except Exception:
            pass
    return "Finnish"


def _run_grammar_check(dialogue_texts: list[str], language: str = "Finnish") -> dict:
    """Run a single grammar check pass and return the parsed result."""
    dialogue_json = json.dumps(dialogue_texts, ensure_ascii=False, indent=2)
    
    # Use Finnish-specific anti-patterns when available, generic prompt otherwise
    anti_patterns = ANTI_PATTERNS_PROMPT if language == "Finnish" else ""
    
    prompt = f"""
Review the following {language} dialogue lines. Check EVERY line for grammar errors, unnatural phrasing,
and non-native patterns. Be VERY strict — if a line could be said more naturally, it MUST be fixed.

{anti_patterns}

## DIALOGUE LINES TO REVIEW:
{dialogue_json}

## OUTPUT FORMAT
Return a JSON object:
{{
    "has_issues": true/false,
    "fixed_lines": ["line1", "line2", ...],
    "changes_made": [
        {{"line_index": 0, "original": "...", "fixed": "...", "error_type": "grammar|unnatural_phrasing|wrong_register|literal_translation|tone_mismatch", "reason": "..."}}
    ]
}}

Rules:
- The "fixed_lines" array MUST have exactly {len(dialogue_texts)} elements (same count as input).
- Keep emotion tags in brackets at the start of each line.
- Preserve the original meaning but make it sound like REAL spoken {language}.
- If the {language} is already perfect, set "has_issues" to false and return original lines unchanged.
- Be aggressive about finding issues — it is better to over-correct than to miss errors.
"""
    
    system = _system_instruction(language)
    config = types.GenerateContentConfig(
        temperature=0.2,
        response_mime_type="application/json",
        system_instruction=system,
    )

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=config,
    )
    
    return json.loads(response.text.strip())


def _verify_fixes(original_texts: list[str], fixed_texts: list[str], language: str = "Finnish") -> dict:
    """Pass 2: Verify that the fixes themselves are natural."""
    
    pairs = []
    for i, (orig, fixed) in enumerate(zip(original_texts, fixed_texts)):
        if orig != fixed:
            pairs.append({"index": i, "original": orig, "fixed": fixed})
    
    if not pairs:
        return {"all_valid": True, "corrections": []}
    
    pairs_json = json.dumps(pairs, ensure_ascii=False, indent=2)
    
    prompt = f"""
You are verifying {language} corrections made by another AI reviewer.
For each pair below, check ONLY whether the "fixed" version introduces NEW problems.

CRITICAL: Your job is NOT to debate whether the original was "acceptable". 
The original was ALREADY flagged as problematic by a native {language} expert.
Your ONLY job is to ensure the fix itself does not introduce NEW errors.

You should REJECT a fix ONLY if:
- The fix introduces a new grammatical error that wasn't in the original
- The fix changes the meaning in a way that contradicts the scene context
- The fix removes the emotion tag in brackets
- The fix is clearly less natural than the original (not just "different but equally valid")

You should ACCEPT a fix if:
- It corrects a genuine error
- It sounds natural in spoken {language}, even if the original was "passable"

Default bias: ACCEPT the fix. Only reject if you are confident the fix is worse.

Pairs to verify:
{pairs_json}

Return a JSON object:
{{
    "all_valid": true/false,
    "corrections": [
        {{"index": 0, "verdict": "accept|reject|improve", "improved_text": "...", "reason": "..."}}
    ]
}}

Rules:
- "accept" = the fix is good, use it as-is
- "reject" = the fix introduces new errors worse than the original
- "improve" = the fix has the right idea but needs minor tweaking, provide "improved_text"
- If all fixes are good, set "all_valid" to true and "corrections" to empty array.
"""
    
    system = _system_instruction(language)
    config = types.GenerateContentConfig(
        temperature=0.1,
        response_mime_type="application/json",
        system_instruction=system,
    )

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=config,
    )
    
    return json.loads(response.text.strip())


def check_and_fix_grammar(dialogue_list: list, language: str = "Finnish") -> tuple[list, bool]:
    """
    Two-pass grammar and naturalness checker.
    Pass 1: Check and fix issues.
    Pass 2: Verify the fixes themselves are natural.
    Returns (fixed_dialogue_list, was_modified).
    Skips SFX entries (type: "sfx") — only checks dialogue lines.
    """
    
    # Separate dialogue entries from SFX entries, preserving positions
    dialogue_indices = []  # indices of dialogue items in the original list
    for i, item in enumerate(dialogue_list):
        if item.get("type") != "sfx":
            dialogue_indices.append(i)
    
    dialogue_texts = [dialogue_list[i].get("text", "") for i in dialogue_indices]
    
    try:
        # --- PASS 1: Check and fix ---
        print("   Pass 1: Checking grammar and naturalness...")
        result = _run_grammar_check(dialogue_texts, language)
        
        if not result.get("has_issues", False):
            print("   ✓ Pass 1: No issues found.")
            return dialogue_list, False
        
        fixed_lines = result.get("fixed_lines", [])
        changes = result.get("changes_made", [])
        
        if len(fixed_lines) != len(dialogue_indices):
            print(f"   ⚠️  Warning: Fixed lines count mismatch ({len(fixed_lines)} vs {len(dialogue_indices)} dialogue lines), keeping original")
            return dialogue_list, False
        
        # Print Pass 1 changes
        if changes:
            print(f"   📝 Pass 1 found {len(changes)} issue(s):")
            for change in changes:
                error_type = change.get('error_type', 'unknown')
                print(f"      [{error_type}]")
                print(f"      • \"{change.get('original', '')[:60]}\"")
                print(f"        → \"{change.get('fixed', '')[:60]}\"")
                print(f"        Reason: {change.get('reason', 'N/A')}")
        
        # --- PASS 2: Verify fixes ---
        print("   Pass 2: Verifying fixes are natural...")
        verification = _verify_fixes(dialogue_texts, fixed_lines, language)
        
        # Apply verification corrections
        corrections = verification.get("corrections", [])
        if corrections:
            for corr in corrections:
                idx = corr.get("index", -1)
                verdict = corr.get("verdict", "accept")
                
                if 0 <= idx < len(fixed_lines):
                    if verdict == "reject":
                        print(f"      ⏪ Pass 2 reverted line {idx}: {corr.get('reason', '')}")
                        fixed_lines[idx] = dialogue_texts[idx]
                    elif verdict == "improve" and corr.get("improved_text"):
                        print(f"      🔧 Pass 2 improved line {idx}: {corr.get('reason', '')}")
                        fixed_lines[idx] = corr["improved_text"]
                    else:
                        print(f"      ✓ Pass 2 accepted fix for line {idx}")
        else:
            print("   ✓ Pass 2: All fixes verified as natural.")
        
        # Check if anything actually changed after verification
        any_changed = any(fixed_lines[i] != dialogue_texts[i] for i in range(len(fixed_lines)))
        
        if any_changed:
            for fix_pos, orig_idx in enumerate(dialogue_indices):
                dialogue_list[orig_idx]["text"] = fixed_lines[fix_pos]
            return dialogue_list, True
        else:
            return dialogue_list, False
            
    except APIError as e:
        raise RuntimeError(f"API Error during grammar check: {e}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"JSON decode error from Gemini response: {e}") from e


def process_script_file(file_path: Path) -> tuple[bool, bool]:
    """Process a single script file, checking and fixing Finnish.
    
    Returns (was_modified, success) tuple.
    """
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"   ❌ Error reading {file_path.name}: {e}")
        return False, False
    
    dialogue_list = data.get("dialogue_list", [])
    if not dialogue_list:
        print(f"   ⚠️  No dialogue found in {file_path.name}")
        return False, False
    
    # Read language from script metadata
    language = data.get("metadata", {}).get("language", "Finnish")
    
    # Check and fix
    try:
        fixed_dialogue, was_modified = check_and_fix_grammar(dialogue_list, language)
    except RuntimeError as e:
        print(f"   ❌ {e}")
        return False, False
    
    if was_modified:
        # Save the fixed version
        data["dialogue_list"] = fixed_dialogue
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"   ✅ Fixed and saved: {file_path.name}")
        return True, True
    else:
        print(f"   ✓ Finnish looks natural: {file_path.name}")
        return False, True


def main():
    """Process all script files in scripts/ folder."""
    
    language = _detect_language()
    
    print("\n" + "="*60)
    print(f"🗣️  GRAMMAR & NATURALNESS CHECKER ({language.upper()})")
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
    error_count = 0
    for script_file in script_files:
        print(f"\n🔍 Checking: {script_file.name}")
        was_modified, success = process_script_file(script_file)
        if was_modified:
            fixed_count += 1
        if not success:
            error_count += 1
    
    print("\n" + "="*60)
    if error_count > 0:
        print(f"❌ {error_count}/{len(script_files)} script(s) had errors!")
        print("="*60 + "\n")
        sys.exit(1)
    elif fixed_count > 0:
        print(f"🎉 Done! Fixed {fixed_count}/{len(script_files)} script(s)")
    else:
        print(f"✅ All scripts already have natural {language}!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
