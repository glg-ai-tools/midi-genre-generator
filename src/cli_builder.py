#!/usr/bin/env python3
import json
import sys
import os
import pretty_midi
from pretty_midi import note_name_to_number
from midi_generator import generate_midi
from live_randomizer import generate_live_phrase
import traceback

INSTRUMENT_PROGRAMS = {
    "Drums": 0, "Bass": 32, "Guitar": 24, "Keys": 0,
    "Horns": 60, "FX": 90, "Vocals": 54,
    "Synth": 81, "Pads": 88, "Strings": 48, "Lead": 80
}

def load_config(path="config/style_workflow_config.json"):
    base = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.normpath(os.path.join(base, "..", path))
    if not os.path.exists(cfg_path):
        raise FileNotFoundError(f"Config not found at {cfg_path}")
    with open(cfg_path, "r") as f:
        return json.load(f)

def prompt_list(prompt, options, allow_back=True):
    while True:
        print("\n" + prompt)
        for i, opt in enumerate(options, 1):
            print(f"  {i}) {opt['name']}")
        print(f"  0) {'back' if allow_back else 'exit'}")
        choice = input("> ").strip()
        if choice == "0":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice)-1]
        print("Invalid choice, try again.")

def prompt_int(prompt, lo, hi, allow_back=True):
    while True:
        resp = input(f"{prompt} [{lo}-{hi}] (0 to {'back' if allow_back else 'exit'}): ").strip()
        if resp == "0":
            return None
        if resp.isdigit() and lo <= int(resp) <= hi:
            return int(resp)
        print("Invalid number, try again.")

def prompt_yesno(prompt):
    resp = input(f"{prompt} (y/N): ").strip().lower()
    return resp == "y"

def run():
    try:
        cfg = load_config()
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        sys.exit(1)

    style = prompt_list("Choose style:", cfg["styles"], allow_back=False)
    if not style:
        sys.exit()
    sub = prompt_list(f"Choose substyle of {style['name']}:", style["substyles"])
    if sub is None:
        return run()

    lo, hi = sub["bpm_range"]
    bpm = prompt_int("Enter desired BPM", lo, hi)
    if bpm is None:
        return run()

    chosen = []
    for instr in sub["instruments"]:
        if prompt_yesno(f"Include {instr}?"):
            chosen.append(instr)

    keys = cfg["keys_modes"]["keys"]
    modes = cfg["keys_modes"]["modes"]
    key = None
    while not key:
        print("\nChoose key: " + ", ".join(keys))
        inp = input("> ").strip().title()
        if inp in keys:
            key = inp
    mode = None
    while not mode:
        print("\nChoose mode: " + ", ".join(modes))
        inp = input("> ").strip().title()
        if inp in modes:
            mode = inp

    kr = sub.get("key_range", {"low":4,"high":4})
    octave = prompt_int(f"Choose octave for key '{key}'", kr["low"], kr["high"], allow_back=False)
    key_with_octave = f"{key}{octave}"

    print("\nYour choices:")
    print(f" Style:       {style['name']} → {sub['name']}")
    print(f" BPM:         {bpm}")
    print(f" Instruments: {', '.join(chosen) or 'None'}")
    print(f" Key & Mode:  {key_with_octave} {mode}")
    if not prompt_yesno("Proceed with MIDI generation?"):
        print("Restarting…")
        return run()

    instrument_mapping = {i: INSTRUMENT_PROGRAMS[i] for i in chosen if i in INSTRUMENT_PROGRAMS}
    os.makedirs("output", exist_ok=True)
    out_base = f"{style['id']}_{sub['id']}_{bpm}_{key_with_octave}{mode}"

    live_rules = cfg.get("live_rules", {})
    if not live_rules:
        print("⚠ No live_rules in config—using defaults.")
        live_rules = {
            "measures":16,"grid_division":16,
            "instrument_precedence":[], "randomization":{"density":{},"pattern_types":{}},
            "allocation_zones":{}, "drum_pattern":{}
        }

    live = prompt_yesno(
        "Enter live mode? (y = randomized 16-bar phrase, n = standard MIDI)"
    )
    if live:
        # ensure Drums in template
        if "Drums" not in sub["instruments"]:
            sub["instruments"].append("Drums")
        try:
            pm = generate_live_phrase(
                template=sub,
                live_rules=live_rules,
                key_root=note_name_to_number(key_with_octave),
                mode=mode,
                tempo=bpm
            )
            live_path = f"output/{out_base}_live.mid"
            pm.write(live_path)
            print(f"✔ Live MIDI written: {live_path}")
            print(f"→ Live file saved at {os.path.abspath(live_path)}")
        except Exception as e:
            print(f"❌ Live mode failed: {e}")
            traceback.print_exc()
    else:
        try:
            output_file = f"output/{out_base}.mid"
            template = {
                "instruments": instrument_mapping,
                "chord_progression": sub.get("chord_progression", ["I","IV","V","I"]),
                "length_bars": sub.get("length_bars", 8),
                "drum_pattern": live_rules.get("drum_pattern", {})
            }
            generate_midi(
                template=template,
                bpm=bpm,
                key_root=note_name_to_number(key_with_octave),
                mode=mode,
                chosen_instruments=chosen,
                output_path=output_file
            )
            print(f"✔ MIDI file generated: {output_file}")
        except Exception as e:
            print(f"❌ Static mode failed: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    run()
