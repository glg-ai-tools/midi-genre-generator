#!/usr/bin/env python3
import json
import sys
import os
import pretty_midi
from pretty_midi import note_name_to_number
from midi_generator import generate_midi
import traceback

# Predefined mapping of instrument names to program numbers
INSTRUMENT_PROGRAMS = {
    "Drums": 0,
    "Bass": 32,
    "Guitar": 24,
    "Keys": 0,
    "Horns": 60,
    "FX": 90,
    "Vocals": 54,
    "Synth": 81,
    "Pads": 88,
    "Strings": 48,
    "Lead": 80
}

# -- Prompt Helpers --------------------------------

def load_config(path="config/style_workflow_config.json"):
    """
    Load the configuration file from the given path.
    The path is resolved relative to the script's location.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.normpath(os.path.join(base_dir, "..", path))
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at {config_path}")
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Error parsing JSON configuration file: {e}")

def prompt_list(prompt, options, allow_back=True):
    """
    Prompt the user to select an option from a list.
    """
    while True:
        print("\n" + prompt)
        for i, opt in enumerate(options, 1):
            print(f"  {i}) {opt['name']}")
        if allow_back:
            print("  0) back")
        else:
            print("  0) exit")
        choice = input("> ").strip()
        if choice == "0":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice)-1]
        print("Invalid choice, try again.")

def prompt_int(prompt, lo, hi, allow_back=True):
    """
    Prompt the user to enter an integer within a range.
    """
    while True:
        resp = input(f"{prompt} [{lo}-{hi}] (0 to {'back' if allow_back else 'exit'}): ").strip()
        if resp == "0":
            return None
        if resp.isdigit() and lo <= int(resp) <= hi:
            return int(resp)
        print("Invalid number, try again.")

def prompt_yesno(prompt):
    """
    Prompt the user for a yes/no response.
    """
    resp = input(f"{prompt} (y/N): ").strip().lower()
    return resp == "y"

# -- Main Flow ------------------------------------

def run():
    """
    Main function to run the MIDI generation workflow.
    """
    try:
        cfg = load_config()
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)

    # 1) Style
    style = prompt_list("Choose style:", cfg["styles"], allow_back=False)
    if not style:
        sys.exit()
    # 2) Substyle
    sub = prompt_list(f"Choose substyle of {style['name']}:", style["substyles"])
    if sub is None:
        return run()
    # 3) BPM
    lo, hi = sub["bpm_range"]
    bpm = prompt_int("Enter desired BPM", lo, hi)
    if bpm is None:
        return run()
    # 4) Instruments
    chosen = []
    for instr in sub["instruments"]:
        if prompt_yesno(f"Include {instr}?"):
            chosen.append(instr)
    # 5) Key & Mode
    keys = cfg["keys_modes"]["keys"]
    modes = cfg["keys_modes"]["modes"]
    key = None
    while not key:
        print("\nChoose key:")
        print("  " + ", ".join(keys))
        inp = input("> ").strip().title()
        if inp in keys:
            key = inp
    mode = None
    while not mode:
        print("\nChoose mode:")
        print("  " + ", ".join(modes))
        inp = input("> ").strip().title()
        if inp in modes:
            mode = inp
    # Determine octave range based on substyle
    key_range = sub.get("key_range", {"low": 4, "high": 4})  # Default to octave 4 if not specified
    low_octave = key_range["low"]
    high_octave = key_range["high"]
    print(f"\nChoose octave for key '{key}' (range: {low_octave}-{high_octave}):")
    octave = prompt_int("Enter octave", low_octave, high_octave, allow_back=False)
    key_with_octave = f"{key}{octave}"

    # 6) Confirm
    print("\nYour choices:")
    print(f" Style:        {style['name']} → {sub['name']}")
    print(f" BPM:          {bpm}")
    print(f" Instruments:  {', '.join(chosen) or 'None'}")
    print(f" Key & Mode:   {key_with_octave} {mode}")
    if not prompt_yesno("Proceed with MIDI generation?"):
        print("Restarting…")
        return run()

    # Transform chosen instruments into a dictionary with program numbers
    instrument_mapping = {instr: INSTRUMENT_PROGRAMS[instr] for instr in chosen if instr in INSTRUMENT_PROGRAMS}

    # 7) Generate
    os.makedirs("output", exist_ok=True)
    output_file = f"output/{style['id']}_{sub['id']}_{bpm}_{key_with_octave}{mode}.mid"
    template = {
        "instruments": instrument_mapping,
        "bpm": bpm,
        "key": key_with_octave,
        "mode": mode,
        "chord_progression": ["I", "IV", "V", "I"],  # Default progression
        "length_bars": 8,  # Default length
        "drum_pattern": {
            "kick": [1, 3],
            "snare": [2, 4],
            "closed_hat": [1, 2, 3, 4],
            "open_hat": []
        }
    }
    try:
        generate_midi(
            template=template,
            bpm=bpm,
            key_root=pretty_midi.note_name_to_number(key_with_octave),
            mode=mode,
            chosen_instruments=chosen,
            output_path=output_file
        )
        print(f"\n✔ MIDI file generated: {output_file}")
    except Exception as e:
        print(f"\n❌ Error generating MIDI file: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    run()
