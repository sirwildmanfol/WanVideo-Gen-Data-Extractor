#!/usr/bin/env python3
"""
ComfyUI Video Metadata Analyzer - Universal Version
Works on Windows/Linux/Mac without external dependencies

Usage: python genparameters.py <video_filename>

Requirements: pip install pymediainfo
"""

import sys
import json
import os
from pathlib import Path

try:
    from pymediainfo import MediaInfo
except ImportError:
    print("Error: pymediainfo not installed.")
    print("Install it with: pip install pymediainfo")
    print("\nThis library includes MediaInfo, so no external tools needed!")
    sys.exit(1)


# Terminal colors (work on Windows 10+ and Unix)
class Colors:
    GREEN = "\033[1;32m"
    RED = "\033[1;31m"
    BLUE = "\033[1;34m"
    YELLOW = "\033[1;33m"
    RESET = "\033[0m"
    
    @classmethod
    def enable_colors(cls):
        """Enable ANSI colors on Windows"""
        if sys.platform == "win32":
            try:
                # Enable ANSI escape sequences on Windows 10+
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            except:
                # Fallback: disable colors if ANSI not supported
                cls.GREEN = cls.RED = cls.BLUE = cls.YELLOW = cls.RESET = ""


def clear_screen():
    """Clear terminal screen (cross-platform)"""
    os.system('cls' if sys.platform == 'win32' else 'clear')


def get_video_metadata(video_path):
    """
    Extract metadata from video using pymediainfo
    Tries both 'prompt' and 'comment' fields
    
    Returns: raw metadata string or None
    """
    try:
        media_info = MediaInfo.parse(video_path)
        
        # Iterate through tracks to find General track with metadata
        for track in media_info.tracks:
            if track.track_type == "General":
                # Try 'prompt' field first (newer ComfyUI format)
                if hasattr(track, 'prompt') and track.prompt:
                    return track.prompt
                
                # Try 'comment' field (older format)
                if hasattr(track, 'comment') and track.comment:
                    return track.comment
                
                # Also try other_* fields (some containers use these)
                if hasattr(track, 'other_comment') and track.other_comment:
                    return track.other_comment[0] if isinstance(track.other_comment, list) else track.other_comment
        
        return None
        
    except Exception as e:
        print(f"{Colors.RED}[!] Error reading video file: {e}{Colors.RESET}")
        sys.exit(1)


def extract_nodes(data):
    """
    Recursively extract the nodes dictionary from nested JSON structures
    Handles various ComfyUI metadata formats
    """
    if isinstance(data, dict):
        if "prompt" in data:
            return extract_nodes(data["prompt"])
        return data
    
    if isinstance(data, str):
        try:
            # Try to parse as JSON
            return extract_nodes(json.loads(data))
        except:
            # Handle badly escaped strings (common in newer files)
            try:
                # Force decode escapes (transform \" into ")
                fixed = data.encode().decode('unicode_escape').strip('"')
                return extract_nodes(json.loads(fixed))
            except:
                return None
    
    return None


def analyze_workflow(raw_data):
    """
    Parse ComfyUI workflow metadata and extract key information
    Returns: dict with positives, negatives, loras, models
    """
    nodes = extract_nodes(raw_data)
    
    if not nodes:
        raise ValueError("Unable to decode node structure.")
    
    positives = []
    negatives = []
    loras = []
    models = []
    
    # Iterate through nodes
    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            continue
        
        class_type = node.get("class_type", "")
        inputs = node.get("inputs", {})
        title = node.get("_meta", {}).get("title", "").lower()
        
        # Extract Prompts (Positive and Negative)
        if class_type == "CLIPTextEncode":
            text = inputs.get("text", "")
            if text:
                if "negative" in title or "negative" in node_id.lower():
                    negatives.append(text)
                else:
                    positives.append(text)
        
        # Extract LoRAs
        if "lora_name" in inputs:
            strength = inputs.get("strength_model") or inputs.get("strength") or "1.0"
            loras.append(f"{inputs['lora_name']} (Weight: {strength})")
        
        # Extract Models (GGUF, Checkpoints, etc)
        if "unet_name" in inputs:
            models.append(inputs["unet_name"])
        elif "ckpt_name" in inputs:
            models.append(inputs["ckpt_name"])
    
    return {
        'positives': positives,
        'negatives': negatives,
        'loras': loras,
        'models': models
    }


def print_results(results):
    """Print formatted analysis results"""
    
    if results['positives']:
        print(f"{Colors.GREEN}>>> POSITIVE PROMPT:{Colors.RESET}")
        for prompt in results['positives']:
            print(f"{prompt}")
            print("-" * 40)
    
    if results['negatives']:
        print(f"\n{Colors.RED}>>> NEGATIVE PROMPT:{Colors.RESET}")
        for prompt in results['negatives']:
            print(f"{prompt}")
            print("-" * 40)
    
    if results['loras']:
        print(f"\n{Colors.YELLOW}>>> LORAS USED:{Colors.RESET}")
        for lora in sorted(set(results['loras'])):
            print(f"  • {lora}")
    
    if results['models']:
        print(f"\n{Colors.BLUE}>>> MODELS / CHECKPOINTS:{Colors.RESET}")
        for model in sorted(set(results['models'])):
            print(f"  • {model}")


def main():
    # Enable colors on all platforms
    Colors.enable_colors()
    
    # Check arguments
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <video_filename>")
        sys.exit(1)
    
    video_path = sys.argv[1]
    
    # Check if file exists
    if not os.path.isfile(video_path):
        print(f"{Colors.RED}[!] Error: File not found: {video_path}{Colors.RESET}")
        sys.exit(1)
    
    # Clear screen and print header
    clear_screen()
    print("=" * 58)
    print(f"{Colors.BLUE} COMFYUI VIDEO METADATA ANALYSIS {Colors.RESET}")
    print(f"{Colors.YELLOW} File:{Colors.RESET} {os.path.basename(video_path)}")
    print("=" * 58)
    
    # Get metadata using pymediainfo
    raw_data = get_video_metadata(video_path)
    
    if not raw_data:
        print(f"{Colors.RED}[!] Error: No metadata found in file.{Colors.RESET}")
        print(" Make sure 'save_metadata' was enabled in ComfyUI.")
        sys.exit(1)
    
    # Parse and analyze
    try:
        results = analyze_workflow(raw_data)
        print_results(results)
        
    except Exception as e:
        print(f"{Colors.RED}[!] JSON parsing error:{Colors.RESET} {e}")
        # Emergency debug dump
        print(f"\nRaw data preview for debugging:\n{raw_data[:200]}...")
        sys.exit(1)
    
    print("=" * 58)


if __name__ == "__main__":
    main()
