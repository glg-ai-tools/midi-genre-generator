import json
import sys
import os
import time
import traceback
import logging
import mido
from midi_generator import generate_midi
from live_randomizer import generate_live_grid
from pretty_midi import note_name_to_number

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'midi_generator.log'))
    ]
)
logger = logging.getLogger(__name__)

# GM drum map for live streaming
GM_DRUM_MAP = {
    "kick": 36, "snare": 38,
    "closed_hat": 42, "open_hat": 46,
    "ride": 51, "crash": 49,
    "tom_low": 45, "tom_mid": 48, "tom_high": 50,
    "shaker": 70, "tambourine": 54, "clap": 39
}

# Live mode functions
def send_live_midi(grid, tempo, key_root, channel_map, sub, cfg): # sub is substyle_config
    """Send MIDI messages in real-time based on the grid"""
    try:
        import mido
        logger.info("MIDO library loaded successfully")
    except ImportError:
        logger.error("Mido library not found. Please install with: pip install mido")
        print("❌ Error: Mido library required for live MIDI output.")
        return False

    outport = None
    try:
        available_ports = mido.get_output_names()
        logger.info(f"Available MIDI output ports: {available_ports}")

        if not available_ports:
            logger.warning("No MIDI output ports available.")
            print("❌ Warning: No MIDI output ports found.")
            print("ℹ️ Info: You can install a virtual MIDI port like 'loopMIDI'.")
            return False
        else:
            print("\nAvailable MIDI Output Ports:")
            for i, port_name_option in enumerate(available_ports):
                print(f"  {i + 1}) {port_name_option}")
            print("  0) Cancel / Use Virtual Port (if available or fallback)")

            while True:
                try:
                    choice = int(input("Choose a MIDI output port (number): ").strip())
                    if 0 <= choice <= len(available_ports):
                        break
                    else:
                        print(f"Please enter a number between 0 and {len(available_ports)}.")
                except ValueError:
                    print("Invalid input. Please enter a number.")

            if choice == 0:
                logger.info("User chose to cancel or attempt virtual port.")
                print("ℹ️ Attempting to use a virtual port or fallback...")
                try:
                    # Try a common name or allow mido to create one if backend supports it
                    outport = mido.open_output('MIDI Generator Virtual Output', virtual=True)
                    logger.info(f"Created or using virtual MIDI output port: {outport.name}")
                    print(f"✅ Using virtual MIDI output port: {outport.name}")
                except Exception as e_virtual:
                    logger.error(f"Failed to create or open virtual port: {e_virtual}")
                    print(f"❌ Error: Could not create/open virtual MIDI port. {e_virtual}")
                    return False
            else:
                port_name = available_ports[choice - 1]
                logger.info(f"User selected MIDI output port: {port_name}")
                try:
                    outport = mido.open_output(port_name)
                    print(f"✅ Using MIDI output port: {port_name}")
                except Exception as e_open:
                    logger.error(f"Failed to open selected port '{port_name}': {e_open}")
                    print(f"❌ Error: Could not open port '{port_name}'. Details: {e_open}")
                    return False
        
        if outport is None:
            logger.error("MIDI output port was not successfully opened or created.")
            return False

        beat_time = 60.0 / tempo
        sixteenth_time = beat_time / 4.0
        
        # Determine measures and divisions from the grid structure
        # Assumes grid is not empty and all instruments have same structure
        if not grid or not any(grid.values()):
            logger.error("Grid is empty or invalid. Cannot proceed with MIDI playback.")
            print("❌ Error: Cannot play MIDI from an empty or invalid grid.")
            if outport and not outport.closed: outport.close()
            return False
            
        first_instrument_grid = next(iter(grid.values()))
        measures = len(first_instrument_grid)
        divisions = len(first_instrument_grid[0]) if measures > 0 else 0

        if measures == 0 or divisions == 0:
            logger.error(f"Grid has zero measures or divisions. Measures: {measures}, Divisions: {divisions}")
            print("❌ Error: Grid has no playable content.")
            if outport and not outport.closed: outport.close()
            return False
        
        logger.info(f"Grid configuration: {measures} measures, {divisions} divisions per measure")
        logger.info(f"Timing: Beat = {beat_time:.3f}s, 16th = {sixteenth_time:.3f}s")
        logger.info(f"Channel mapping: {channel_map}")
        print(f"ℹ️ Playing {measures} measures, tempo: {tempo} BPM on port '{outport.name}'")
        print("🎵 Starting MIDI playback...")
        
        # Pre-fetch drum setup if "Drums" is a chosen instrument
        drums_instrument_id = "Drums" 
        drum_style_patterns = None
        # Find the "Drums" instrument setup in the current substyle
        for inst_setup_item in sub.get("instrument_setup", []):
            if inst_setup_item.get("instrument_id") == drums_instrument_id:
                drum_style_patterns = inst_setup_item.get("patterns", {})
                if drum_style_patterns:
                    logger.info(f"Found style-specific drum patterns for '{drums_instrument_id}': {list(drum_style_patterns.keys())}")
                else: # This case means "Drums" is in instrument_setup but has no "patterns" dict
                    logger.warning(f"'{drums_instrument_id}' is in instrument_setup but has no patterns defined in substyle '{sub.get('name')}'.")
                break 
        
        try:
            for m in range(measures):
                logger.info(f"Playing measure {m+1}/{measures} on port '{outport.name}'")
                print(f"Measure {m+1}/{measures}", end="\r")
                for t in range(divisions):
                    messages_to_send_on = [] 
                    
                    for inst_id, inst_grid_data in grid.items():
                        if inst_id not in channel_map: # Instrument was in grid but not chosen or no channel assigned
                            logger.warning(f"Skipping notes for '{inst_id}' - no channel mapping found.")
                            continue

                        if inst_grid_data[m][t]: # If the grid says this instrument should play NOW
                            channel = channel_map[inst_id]
                            
                            if inst_id == drums_instrument_id and drum_style_patterns:
                                # Handle Drums based on its style-specific sub-patterns
                                for drum_part_name, pattern_array in drum_style_patterns.items():
                                    if isinstance(pattern_array, list) and t < len(pattern_array) and pattern_array[t]: # Check hit in pattern
                                        midi_note = GM_DRUM_MAP.get(drum_part_name)
                                        if midi_note is not None:
                                            logger.debug(f"DRUM: {drum_part_name} (note {midi_note}) at M{m+1},T{t+1} on Ch{channel}")
                                            messages_to_send_on.append(mido.Message('note_on', note=midi_note, velocity=100, channel=channel))
                                        else:
                                            logger.warning(f"Drum part '{drum_part_name}' not in GM_DRUM_MAP. Skipping.")
                            
                            elif inst_id != drums_instrument_id: # Melodic instruments
                                note_to_play = key_root 
                                # Placeholder for future advanced melodic note selection:
                                # current_chord_name = sub['chord_progression'][m % len(sub['chord_progression'])]
                                # pitches_in_chord = chord_to_pitches(current_chord_name, key_root, mode)
                                # if pitches_in_chord: note_to_play = random.choice(pitches_in_chord)
                                # note_to_play = clamp_pitch(note_to_play, inst_id, master_instrument_defs, cfg)
                                logger.debug(f"MELODIC: {inst_id} (note {note_to_play}) at M{m+1},T{t+1} on Ch{channel}")
                                messages_to_send_on.append(mido.Message('note_on', note=note_to_play, velocity=100, channel=channel))

                    for msg in messages_to_send_on:
                        outport.send(msg)
                    
                    time.sleep(sixteenth_time)
                    
                    for msg in messages_to_send_on:
                        outport.send(mido.Message('note_off', note=msg.note, velocity=0, channel=msg.channel))
                
            logger.info("Playback completed successfully")
            print("\n✅ Playback completed!")
            
        except KeyboardInterrupt:
            logger.info("Playback interrupted by user")
            print("\n⏹️ Playback stopped by user")
            if outport and not outport.closed:
                for ch_off in range(16): 
                    outport.send(mido.Message('control_change', control=123, value=0, channel=ch_off))
                logger.info("Sent All Notes Off command.")
                
        finally:
            if outport and not outport.closed:
                outport.close()
                logger.info(f"MIDI output port '{outport.name}' closed.")
            
        return True
            
    except Exception as e:
        logger.error(f"Error during MIDI setup or playback: {e}")
        traceback.print_exc()
        print(f"❌ Error: {e}")
        if "rtmidi" in str(e).lower():
             print("💡 Tip: Ensure 'python-rtmidi' is installed: pip install python-rtmidi")
        return False

# Rest of your CLI functions
def load_config():
    base = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base, "..", "config", "style_workflow_config.json")
    logger.info(f"Loading configuration from: {config_path}")
    with open(config_path, "r") as f:
        config = json.load(f)
        logger.info(f"Configuration loaded successfully with {len(config['styles'])} styles")
        return config

def prompt_yesno(prompt):
    resp = input(f"{prompt} (y/N): ").strip().lower()
    return resp == "y"

def prompt_list(prompt, options, allow_back=True):
    """
    Prompts the user to select from a list of options.
    """
    while True:
        print(prompt)
        for i, opt in enumerate(options, 1):
            name = opt["name"] if isinstance(opt, dict) else opt
            print(f"{i}) {name}")
        if allow_back:
            print("0) Back")
        choice = input("> ").strip()
        if choice == "0" and allow_back:
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx]
            print(f"Please enter a number between 1 and {len(options)}.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def prompt_int(prompt, lo, hi, allow_back=True):
    """
    Prompts the user to enter an integer within a specified range.
    """
    while True:
        try:
            print(f"{prompt} ({lo}-{hi})")
            if allow_back:
                print("0) Back")
            choice = int(input("> ").strip())
            if allow_back and choice == 0:
                return None
            if lo <= choice <= hi:
                return choice
            print(f"Please enter a number between {lo} and {hi}.")
        except ValueError:
            print("Invalid input. Please enter a valid integer.")

def run():
    try:
        logger.info("Starting MIDI Genre Generator")
        cfg = load_config()
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        print(f"Error loading configuration: {e}")
        sys.exit(1)
        
    style = prompt_list("Choose style:", cfg["styles"], allow_back=False)
    if not style: 
        logger.info("User exited at style selection")
        sys.exit()
    
    logger.info(f"Style selected: {style['name']}")
    
    sub = prompt_list(f"Choose substyle of {style['name']}:", style['substyles'])
    if sub is None: 
        logger.info("User went back from substyle selection")
        return run()
    
    logger.info(f"Substyle selected: {sub['name']}")
    
    lo, hi = sub["bpm_range"]
    bpm = prompt_int("Enter desired BPM", lo, hi)
    if bpm is None: 
        logger.info("User went back from BPM selection")
        return run()
    
    logger.info(f"BPM selected: {bpm}")
    
    # --- MODIFIED: Collect instruments based on instrument_setup ---
    chosen_instruments_details = [] # To store the full detail of chosen instruments
    chosen_instrument_ids = [] # To store just the IDs for logging and other uses
    logger.info("Prompting for instruments...")
    
    # Ensure 'instrument_setup' exists and is a list
    instrument_options = sub.get("instrument_setup", [])
    if not isinstance(instrument_options, list):
        logger.error(f"Substyle '{sub['name']}' has malformed 'instrument_setup'. Expected a list.")
        print(f"❌ Error: Configuration issue with substyle '{sub['name']}'. Contact developer.")
        return run()

    master_defs = cfg.get("master_instrument_definitions", {})

    for instrument_config_in_style in instrument_options:
        instrument_id = instrument_config_in_style.get("instrument_id")
        if not instrument_id:
            logger.warning(f"Skipping instrument in substyle '{sub['name']}' due to missing 'instrument_id'.")
            continue

        # Get the display name from master_instrument_definitions if possible, fallback to id
        display_name = instrument_id
        if instrument_id in master_defs and "description" in master_defs[instrument_id]:
            pass

        if prompt_yesno(f"Include {display_name}?"):
            chosen_instruments_details.append(instrument_config_in_style) # Store the whole object
            chosen_instrument_ids.append(instrument_id)
            logger.info(f"Added instrument: {instrument_id}")
    
    if not chosen_instrument_ids:
        logger.info("No instruments selected by the user.")
        print("No instruments selected. Exiting.")
        return run()
    logger.info(f"Selected instruments: {', '.join(chosen_instrument_ids)}")
    # --- END MODIFIED ---
    
    # Get key and mode
    key = prompt_list("Choose key:", cfg["keys_modes"]["keys"])
    if key is None:
        logger.info("User went back from key selection")
        return run()
    logger.info(f"Key selected: {key}")
    
    mode = prompt_list("Choose mode:", cfg["keys_modes"]["modes"])
    if mode is None:
        logger.info("User went back from mode selection")
        return run()
    logger.info(f"Mode selected: {mode}")
    
    key_range = sub.get("key_range", {"low": 3, "high": 5})
    octave = prompt_int(f"Choose octave for '{key}'", key_range["low"], key_range["high"], allow_back=False)
    if octave is None: # Should not happen if allow_back is False, but good practice
        logger.info("User went back from octave selection") # Or handle as error
        return run()
    key_o = f"{key}{octave}"
    logger.info(f"Full key selected: {key_o}")
    
    print(f"Style: {style['name']}, Substyle: {sub['name']}, BPM: {bpm}, Instruments: {', '.join(chosen_instrument_ids)}, Key: {key_o}, Mode: {mode}")
    if not prompt_yesno("Proceed with generation? (y/N)"): 
        logger.info("User cancelled at confirmation prompt")
        return run()

    # --- MODIFIED: Channel assignment based on new JSON structure ---
    channel_map = {}
    master_instrument_defs = cfg.get("master_instrument_definitions", {})
    channel_bands = cfg.get("midi_channel_assignment_bands", {})
    
    for instrument_id in chosen_instrument_ids:
        if instrument_id not in master_instrument_defs:
            logger.warning(f"Master definition for instrument '{instrument_id}' not found. Assigning default channel 0.")
            channel_map[instrument_id] = 0 # Fallback channel
            continue

        instr_master_def = master_instrument_defs[instrument_id]

        if "fixed_midi_channel" in instr_master_def:
            channel_map[instrument_id] = instr_master_def["fixed_midi_channel"]
            logger.info(f"Assigned fixed MIDI channel {instr_master_def['fixed_midi_channel']} to {instrument_id}")
        elif "default_midi_channel_band_id" in instr_master_def:
            band_id = instr_master_def["default_midi_channel_band_id"]
            if band_id in channel_bands and "channel" in channel_bands[band_id]:
                channel_map[instrument_id] = channel_bands[band_id]["channel"]
                logger.info(f"Assigned channel {channel_bands[band_id]['channel']} to {instrument_id} (band: {band_id})")
            else:
                logger.warning(f"MIDI channel band '{band_id}' for instrument '{instrument_id}' not found or malformed. Assigning default channel 0.")
                channel_map[instrument_id] = 0 # Fallback channel
        else:
            logger.warning(f"No channel assignment rule found for instrument '{instrument_id}'. Assigning default channel 0.")
            channel_map[instrument_id] = 0 # Fallback channel
            
    logger.info(f"Final channel assignment map: {channel_map}")
    # --- END MODIFIED ---
    
    # MIDI Generation
    key_root = note_name_to_number(key_o)
    logger.info(f"Key root MIDI note: {key_root}")
    
    live_rules = cfg.get("live_rules", {})
    
    if prompt_yesno("Enter live mode? (sends MIDI to outputs in real-time)"):
        logger.info("Entering live MIDI mode")
        try:
            logger.info("Generating live grid...")
            grid = generate_live_grid(
                template=sub,
                live_rules=live_rules,
                key_root=key_root,
                mode=mode,
                tempo=bpm,
                chosen_instrument_ids=chosen_instrument_ids,
                master_instrument_defs=master_instrument_defs,
                cfg=cfg
            )
            
            instrument_stats = {}
            if grid:
                for inst, measures in grid.items():
                    total_steps = 0
                    if measures:
                        for measure in measures:
                            total_steps += sum(1 for step in measure if step)
                    instrument_stats[inst] = total_steps
                logger.info(f"Grid generation complete. Hit counts by instrument: {instrument_stats}")
            else:
                logger.error("Grid generation failed or returned empty.")
                print("❌ Error: Live grid generation failed.")
                return run()

            out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
            os.makedirs(out_dir, exist_ok=True)
            safe_key_o = key_o.replace("#", "s")
            out_file_base = f"{style['id']}_{sub['id']}_{bpm}_{safe_key_o}_{mode}"
            
            logger.info("Starting live MIDI playback...")
            success = send_live_midi(grid, bpm, key_root, channel_map, sub, cfg)
            
            if not success:
                print(f"ℹ️ Live MIDI playback failed or was cancelled.")
                if prompt_yesno(f"Generate MIDI file ({out_file_base}_live.mid) instead?"):
                    logger.info("Generating MIDI file as fallback or alternative...")
                    generate_midi(
                        filename=os.path.join(out_dir, f"{out_file_base}_live_generated.mid"),
                        substyle_config=sub,
                        chosen_instrument_ids=chosen_instrument_ids,
                        channel_map=channel_map,
                        key_root=key_root,
                        mode=mode,
                        bpm=bpm,
                        cfg=cfg
                    )
                    print(f"✅ MIDI file generated: {os.path.join(out_dir, f'{out_file_base}_live_generated.mid')}")
            
        except Exception as e:
            logger.error(f"Error in live mode: {e}")
            traceback.print_exc()
            print(f"❌ Error: {e}")
    else:
        logger.info("Generating static MIDI file")
        out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
        os.makedirs(out_dir, exist_ok=True)
        safe_key_o = key_o.replace("#", "s")
        out_file_base = f"{style['id']}_{sub['id']}_{bpm}_{safe_key_o}_{mode}"
        out_path = os.path.join(out_dir, f"{out_file_base}_static.mid")

        generate_midi(
            filename=out_path,
            substyle_config=sub,
            chosen_instrument_ids=chosen_instrument_ids,
            channel_map=channel_map,
            key_root=key_root,
            mode=mode,
            bpm=bpm,
            cfg=cfg
        )
        print(f"✅ MIDI file generated: {out_path}")

if __name__ == "__main__":
    run()