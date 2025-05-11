import pretty_midi
import os

GM_DRUM_MAP = {
    "kick": 36, "snare": 38, "closed_hat": 42, "open_hat": 46,
    "ride": 51, "crash": 49, "tom_low": 45, "tom_mid": 48,
    "tom_high": 50, "shaker": 70, "tambourine": 54, "clap": 39
}

INSTRUMENT_RANGES = {
    "Bass": (28, 52),   # E1–E3
    "Guitar": (40, 76), # E2–E5 (Adjusted typical range)
    "Keys": (21, 108),  # A0–C8
    "Horns": (54, 86),  # F#3–D6 (Adjusted typical range for section)
    "Horn Section": (54, 86),
    "Pads": (48, 78),   # C3–F#5
    "Lead": (60, 96),   # C4–C7
    "Vocals": (48, 72)  # C3-C5 (Example, highly variable)
    # Add other instruments from INSTRUMENT_PROGRAMS if they have specific ranges
}

def clamp_pitch(pitch, low, high):
    while pitch < low:
        pitch += 12
    while pitch > high:
        pitch -= 12
    return pitch

def chord_to_pitches(chord_symbol, key_root_midi, mode_name):
    scale_intervals_map = { # Intervals from tonic for major scale based modes
        "ionian": [0, 2, 4, 5, 7, 9, 11],
        "dorian": [0, 2, 3, 5, 7, 9, 10],
        "phrygian": [0, 1, 3, 5, 7, 8, 10],
        "lydian": [0, 2, 4, 6, 7, 9, 11],
        "mixolydian": [0, 2, 4, 5, 7, 9, 10],
        "aeolian": [0, 2, 3, 5, 7, 8, 10],
        "locrian": [0, 1, 3, 5, 6, 8, 10]
    }
    
    current_scale_intervals = scale_intervals_map.get(mode_name.lower(), scale_intervals_map["ionian"])

    roman_to_degree = { 
        'I': 0, 'II': 1, 'III': 2, 'IV': 3, 'V': 4, 'VI': 5, 'VII': 6,
        'i': 0, 'ii': 1, 'iii': 2, 'iv': 3, 'v': 4, 'vi': 5, 'vii': 6
    }
    
    degree_char = chord_symbol.upper().replace('M', '').replace('7', '').replace('DIM','').replace('AUG','')
    degree_index = roman_to_degree.get(degree_char, 0)
    
    chord_root_offset = current_scale_intervals[degree_index % 7]
    
    scale_notes = [(key_root_midi + interval) for interval in current_scale_intervals]

    chord_root_note_in_scale = scale_notes[degree_index % 7]

    base_pitch = key_root_midi + chord_root_offset
    
    is_major_chord = degree_char in ['I', 'IV', 'V']
    
    third_interval = 4 if is_major_chord else 3
    fifth_interval = 7

    pitches = [base_pitch, base_pitch + third_interval, base_pitch + fifth_interval]
    return pitches

def apply_drum_pattern(inst, beats, role, beat_dur, velocity=100):
    if role not in GM_DRUM_MAP:
        return
    note_num = GM_DRUM_MAP[role]
    for beat_time in beats:
        time_per_step = (beat_dur * 4) / 16
        t0 = (beat_time - 1) * time_per_step
        t1 = t0 + (time_per_step * 0.5)
        inst.notes.append(pretty_midi.Note(velocity, note_num, t0, t1))

def generate_midi(template, bpm, key_root, mode, chosen_instruments, output_path):
    pm = pretty_midi.PrettyMIDI(initial_tempo=float(bpm))
    beat_dur = 60.0 / float(bpm)

    if 'Drums' in chosen_instruments and 'Drums' in template.get('instruments', {}):
        drum_instrument_config = template['instruments']['Drums']
        drum_inst = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")
        
        drum_pattern_source = template.get('drum_pattern', {})
        num_bars = template.get('length_bars', 8)

        for bar_idx in range(num_bars):
            bar_start_time = bar_idx * 4 * beat_dur
            for role, steps_in_pattern in drum_pattern_source.items():
                if role not in GM_DRUM_MAP:
                    continue
                note_num = GM_DRUM_MAP[role]
                time_per_16th_step = beat_dur / 4.0

                for step_num in steps_in_pattern:
                    t0 = bar_start_time + (step_num - 1) * time_per_16th_step
                    t1 = t0 + (time_per_16th_step * 0.5)
                    drum_inst.notes.append(pretty_midi.Note(100, note_num, t0, t1))
        if drum_inst.notes:
            pm.instruments.append(drum_inst)

    instrument_configs = template.get('instruments', {})
    chords = template.get('chord_progression', ["I"])
    num_bars_melodic = template.get('length_bars', 8)

    for inst_name, program_num in instrument_configs.items():
        if inst_name == 'Drums' or inst_name not in chosen_instruments:
            continue
        
        inst_obj = pretty_midi.Instrument(program=int(program_num), name=inst_name)
        low_range, high_range = INSTRUMENT_RANGES.get(inst_name, (0, 127))

        for bar_idx in range(num_bars_melodic):
            current_chord_symbol = chords[bar_idx % len(chords)]
            pitches_for_chord = chord_to_pitches(current_chord_symbol, key_root, mode)
            
            bar_start_time = bar_idx * 4 * beat_dur
            bar_end_time = (bar_idx + 1) * 4 * beat_dur
            
            for pitch in pitches_for_chord:
                clamped_pitch = clamp_pitch(pitch, low_range, high_range)
                note = pretty_midi.Note(velocity=80, pitch=clamped_pitch, start=bar_start_time, end=bar_end_time)
                inst_obj.notes.append(note)
        
        if inst_obj.notes:
            pm.instruments.append(inst_obj)

    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    pm.write(output_path)
    print(f"✔ MIDI file generated: {output_path}")
    print(f"→ Full path: {os.path.abspath(output_path)}")