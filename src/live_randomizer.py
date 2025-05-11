### src/live_randomizer.py
import random
import pretty_midi
from midi_generator import generate_midi

# Live-randomizer for Phase Two dynamic phrase generation

def make_euclidean(k, n):
    """Return a Euclidean rhythm: list of n booleans with k hits."""
    counts = [1] * k + [0] * (n - k)
    while len(counts) > 1:
        k = sum(1 for c in counts if c)
        zeros = len(counts) - k
        for i in range(min(k, zeros)):
            counts[i] += counts.pop()
    # final counts is a nested list or int
    # ensure we return length-n boolean list
    flat = counts[0] if isinstance(counts[0], list) else counts
    return [bool(c) for c in flat]


def apply_drum_pattern(inst, beats, role, beat_dur, velocity=100):
    """Apply a drum pattern to a PrettyMIDI instrument."""
    GM_DRUM_MAP = {
        "kick": 36,
        "snare": 38,
        "closed_hat": 42,
        "open_hat": 46,
        "ride": 51,
        "crash": 49,
        "tom_low": 45,
        "tom_mid": 48,
        "tom_high": 50,
        "shaker": 70,
        "tambourine": 54,
        "clap": 39
    }
    if role not in GM_DRUM_MAP:
        return
    note_num = GM_DRUM_MAP[role]
    for beat in beats:
        t0 = (beat - 1) * beat_dur
        t1 = t0 + 0.05
        inst.notes.append(pretty_midi.Note(velocity, note_num, t0, t1))


def generate_live_phrase(template, live_rules, key_root, mode, tempo):
    """
    Generate a live randomized MIDI phrase.
    :param template: dict with 'instruments', etc.
    :param live_rules: dict from config.
    :param key_root: root MIDI pitch.
    :param mode: scale mode (unused stub).
    :param tempo: BPM.
    :return: PrettyMIDI object.
    """
    measures = live_rules.get('measures', 16)
    divisions = live_rules.get('grid_division', 16)
    precedence = live_rules.get('instrument_precedence', [])
    density_map = live_rules.get('randomization', {}).get('density', {})
    types_map = live_rules.get('randomization', {}).get('pattern_types', {})
    zones = live_rules.get('allocation_zones', {})
    drum_pattern = live_rules.get('drum_pattern', {})

    pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    beat_dur = 60.0 / tempo

    # 1) Drums
    if 'Drums' in template.get('instruments', []):
        dr = pretty_midi.Instrument(program=0, is_drum=True, name='Drums')
        for role, beats in drum_pattern.items():
            apply_drum_pattern(dr, beats, role, beat_dur)
        pm.instruments.append(dr)

    # 2) Build grid for non-drums
    grid = {
        inst: [[False] * divisions for _ in range(measures)]
        for inst in template.get('instruments', []) if inst != 'Drums'
    }

    for inst in precedence:
        if inst not in grid:
            continue
        zone = zones.get(inst, [0, measures])
        d = density_map.get(inst, 0.2)
        ptype = types_map.get(inst, 'euclidean')
        for m in range(zone[0], zone[1]):
            if ptype == 'euclidean':
                k = max(1, int(d * divisions))
                hits = make_euclidean(k, divisions)
            else:
                hits = [random.random() < d for _ in range(divisions)]
            for i, on in enumerate(hits):
                if not on:
                    continue
                higher = precedence[:precedence.index(inst)]
                if any(grid.get(h, [[False] * divisions] * measures)[m][i] for h in higher):
                    continue
                grid[inst][m][i] = True

    # 3) Convert grid→notes
    for inst_name, prog in template.get('instruments', {}).items():
        if inst_name == 'Drums':
            continue
        midi_inst = pretty_midi.Instrument(program=prog, name=inst_name)
        for m in range(measures):
            for i, on in enumerate(grid.get(inst_name, [])[m]):
                if not on:
                    continue
                t0 = (m * divisions + i) * (beat_dur / 4)
                t1 = t0 + beat_dur
                midi_inst.notes.append(pretty_midi.Note(100, key_root, t0, t1))
        pm.instruments.append(midi_inst)

    return pm
