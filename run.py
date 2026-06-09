#!/usr/bin/env python3
"""
Full Pipeline Runner for Kielo Convo Generator

Runs the complete video generation pipeline from ideas to final subtitled videos.
"""

import subprocess
import sys
from pathlib import Path
from cleanup import cleanup
from cefr_levels import is_cefr_level, normalize_level


def run_step(script_name: str, description: str, args: list = None) -> bool:
    """Run a pipeline step and return success status."""
    print(f"\n{'='*60}")
    print(f"🚀 {description}")
    cmd_str = f"python {script_name}"
    if args:
        cmd_str += " " + " ".join(args)
    print(f"   Running: {cmd_str}")
    print('='*60)
    
    cmd = [sys.executable, script_name]
    if args:
        cmd.extend(args)
        
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    
    if result.returncode != 0:
        print(f"\n❌ Error: {script_name} failed with exit code {result.returncode}")
        return False
    
    print(f"✅ {script_name} completed successfully")
    return True


def main():
    """Run the full video generation pipeline."""
    print("\n" + "="*60)
    print("🎬 KIELO CONVO GENERATOR - FULL PIPELINE")
    print("="*60)
    
    # Clean up previous run for a fresh start
    cleanup()
    
    # Parse optional arguments: number of outputs (int), CEFR level (A1–C2), or topic (string)
    num_outputs = None
    topic = None
    level = None

    for arg in sys.argv[1:]:
        if arg.isdigit():
            num_outputs = arg
            print(f"ℹ️  Overriding default output count to: {num_outputs}")
        elif is_cefr_level(arg):
            level = normalize_level(arg)
            print(f"ℹ️  Targeting CEFR level: {level}")
        else:
            topic = arg
            print(f"ℹ️  Setting topic to: {topic}")

    # Step 1 arguments
    step1_args = []
    if num_outputs:
        step1_args.append(str(num_outputs))
    if level:
        step1_args.append(level)
    if topic:
        step1_args.append(topic)

    pipeline_steps = [
        ("generate_ideas_json.py", "Step 1/9: Generating conversation ideas", step1_args),
        ("generate_scripts.py", "Step 2/9: Generating dialogue scripts", []),
        ("check_finnish_grammar.py", "Step 3/9: Checking Finnish grammar & naturalness", []),
        ("generate_illustrations.py", "Step 4/9: Generating illustrations", []),
        ("generate_sfx.py", "Step 5/9: Generating sound effects", []),
        ("tts_generator.py", "Step 6/9: Generating audio (TTS)", []),
        ("sfx_mixer.py", "Step 7/9: Mixing sound effects into audio", []),
        ("generate_videos.py", "Step 8/9: Creating videos", []),
        ("music_mixer.py", "Step 9/9: Adding background music", []),
    ]
    
    for script, description, args in pipeline_steps:
        if not run_step(script, description, args):
            print(f"\n❌ Pipeline stopped due to error in {script}")
            sys.exit(1)
    
    print("\n" + "="*60)
    print("🎉 PIPELINE COMPLETE!")
    print("   Final videos are in: output_videos/")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
