import pretty_midi
import os

# GM Drum mapping and playable ranges
GM_DRUM_MAP = {
    "kick":       36,  # Bass Drum 1
    "snare":      38,  # Acoustic Snare
    "closed_hat": 42,  # Closed Hi-Hat
    "open_hat":   46,  # Open Hi-Hat
    "tom_low":    45,  # Low Tom
    "tom_mid":    48,  # Mid Tom
    "tom_high":   50,  # High Tom
    "ride":       51,  # Ride Cymbal 1
    "crash":      49   # Crash Cymbal 1
}

# Instrument pitch ranges (low and high MIDI note numbers)
INSTRUMENT_RANGES = {
    "Bass":   (28, 52),   # E1–E3
    "Guitar": (40, 64),   # E3–E5
    "Keys":   (21, 108),  # A0–C8
    "Horns":  (54, 74),   # F#3–D5
    "Pads":   (48, 78),   # C3–F#5
    "Lead":   (60, 84),   # C4–C6
}

NOTE_MAP = {
    # Map scale degrees to semitone offsets in C major; you’ll transpose by key later
    'I': 0, 'ii': 2, 'iii': 4, 'IV': 5, 'V': 7, 'vi': 9, 'vii°': 11
}

def chord_to_pitches(chord_symbol, key_root, mode):
    """
    Convert a chord symbol like "i", "V", "VII" to absolute MIDI pitches
    in the given key and mode. (Stub: implement modal mappings here.)
    """
    # TODO: Build scale per mode, find scale degree, return triad notes
    return [key_root + NOTE_MAP[chord_symbol], key_root + NOTE_MAP[chord_symbol]+4, key_root + NOTE_MAP[chord_symbol]+7]

def apply_pattern(pm_instr, pattern, start_time, beat_duration, velocity=100):
    """
    Given a pattern dict (e.g. kick on beats [1,3]), place notes into pm_instr.
    """
    for beat in pattern:
        t = start_time + (beat - 1) * beat_duration
        pm_instr.notes.append(pretty_midi.Note(velocity, pretty_midi.program_to_drum_note(36), t, t + 0.05))

def apply_drum_pattern(inst, beats, role, beat_dur, velocity=100):
    """
    Add a drum pattern to the given instrument.
    :param inst: The PrettyMIDI instrument object.
    :param beats: A list of beat numbers where the drum should play.
    :param role: The drum role (e.g., 'kick', 'snare').
    :param beat_dur: The duration of a single beat in seconds.
    :param velocity: The velocity of the drum hits.
    """
    if role not in GM_DRUM_MAP:
        return
    note_num = GM_DRUM_MAP[role]
    for beat in beats:
        t0 = (beat - 1) * beat_dur  # Start time of the note
        t1 = t0 + 0.05  # Short duration for drum hits
        inst.notes.append(pretty_midi.Note(velocity, note_num, t0, t1))

def clamp_pitch(pitch, low, high):
    """
    Clamp a pitch to the specified range by transposing it up or down by octaves.
    :param pitch: The MIDI pitch to clamp.
    :param low: The lowest allowable pitch.
    :param high: The highest allowable pitch.
    :return: The clamped pitch.
    """
    while pitch < low:
        pitch += 12  # Transpose up by an octave
    while pitch > high:
        pitch -= 12  # Transpose down by an octave
    return pitch

def generate_midi(template, bpm, key_root, mode, chosen_instruments, output_path):
    midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    beat_dur = 60.0 / bpm

    # Drums
    if "Drums" in chosen_instruments:
        drum_inst = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")
        patt = template.get('drum_pattern', {})
        apply_drum_pattern(drum_inst, patt.get('kick', []), 'kick', beat_dur)
        apply_drum_pattern(drum_inst, patt.get('snare', []), 'snare', beat_dur)
        apply_drum_pattern(drum_inst, patt.get('closed_hat', []), 'closed_hat', beat_dur)
        apply_drum_pattern(drum_inst, patt.get('open_hat', []), 'open_hat', beat_dur)
        midi.instruments.append(drum_inst)

        # Save individual drum MIDI file
        drum_output_path = os.path.splitext(output_path)[0] + "_Drums.mid"
        drum_midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
        drum_midi.instruments.append(drum_inst)
        drum_midi.write(drum_output_path)
        print(f"✔ Drum MIDI written to {drum_output_path}")

    # Other instruments
    for name, program in template.get('instruments', {}).items():
        if name not in chosen_instruments or name == 'Drums':
            continue
        inst = pretty_midi.Instrument(program=program, name=name)
        chords = template.get('chord_progression', ["I", "IV", "V", "I"])  # Default progression
        length = template.get('length_bars', 8)
        low, high = INSTRUMENT_RANGES.get(name, (0, 127))
        for bar in range(length):
            sym = chords[bar % len(chords)]
            pitches = chord_to_pitches(sym, key_root, mode)
            start = bar * 4 * beat_dur
            end = (bar + 1) * 4 * beat_dur
            for p in pitches:
                p_safe = clamp_pitch(p, low, high)
                inst.notes.append(pretty_midi.Note(80, p_safe, start, end))
        midi.instruments.append(inst)

        # Save individual instrument MIDI file
        instrument_output_path = os.path.splitext(output_path)[0] + f"_{name}.mid"
        instrument_midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
        instrument_midi.instruments.append(inst)
        instrument_midi.write(instrument_output_path)
        print(f"✔ {name} MIDI written to {instrument_output_path}")

    # Write combined MIDI file
    midi.write(output_path)
    print(f"✔ Combined MIDI written to {output_path}")
