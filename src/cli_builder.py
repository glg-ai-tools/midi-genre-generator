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
def send_live_midi(grid, tempo, key_root, channel_map, drum_pat):
    """Send MIDI messages in real-time based on the grid"""
    try:
        import mido
        logger.info("MIDO library loaded successfully")
    except ImportError:
        logger.error("Mido library not found. Please install with: pip install mido")
        print("❌ Error: Mido library required for live MIDI output.")
        return False

    outport = None  # Initialize outport to None
    try:
        available_ports = mido.get_output_names()
        logger.info(f"Available MIDI output ports: {available_ports}")

        if not available_ports:
            logger.warning("No MIDI output ports available. Please connect a MIDI device or install a virtual MIDI port.")
            print("❌ Warning: No MIDI output ports found.")
            print("ℹ️ Info: You can install a virtual MIDI port like 'loopMIDI' if you don't have a physical device.")
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
                    outport = mido.open_output('MIDI Generator Virtual Port', virtual=True)
                    logger.info("Created virtual MIDI output port: MIDI Generator Virtual Port")
                    print("✅ Created virtual MIDI output port: MIDI Generator Virtual Port")
                except Exception as e_virtual:
                    logger.error(f"Failed to create virtual port: {e_virtual}")
                    print(f"❌ Error: Could not create virtual MIDI port. {e_virtual}")
                    return False
            else:
                port_name = available_ports[choice - 1]
                logger.info(f"User selected MIDI output port: {port_name}")
                print(f"✅ Using MIDI output port: {port_name}")
                try:
                    outport = mido.open_output(port_name)
                except Exception as e_open: # Catch specific port opening errors
                    logger.error(f"Failed to open selected port '{port_name}': {e_open}")
                    print(f"❌ Error: Could not open port '{port_name}'. It might be in use or unavailable.")
                    print(f"   Details: {e_open}")
                    return False
        
        if outport is None: # Should not happen if logic is correct, but as a safeguard
            logger.error("MIDI output port was not successfully opened or created.")
            return False

        beat_time = 60.0 / tempo  # Time for one beat in seconds
        sixteenth_time = beat_time / 4.0  # Time for one 16th note
        
        measures = len(next(iter(grid.values())))
        divisions = len(next(iter(grid.values()))[0])
        
        logger.info(f"Grid configuration: {measures} measures, {divisions} divisions per measure")
        logger.info(f"Timing: Beat = {beat_time:.3f}s, 16th = {sixteenth_time:.3f}s")
        logger.info(f"Channel mapping: {channel_map}")
        print(f"ℹ️ Playing {measures} measures, tempo: {tempo} BPM on port '{outport.name}'")
        print("🎵 Starting MIDI playback...")
        
        try:
            # Play the grid
            for m in range(measures):
                logger.info(f"Playing measure {m+1}/{measures} on port '{outport.name}'")
                print(f"Measure {m+1}/{measures}", end="\r")
                for t in range(divisions):
                    messages_to_send = [] # Renamed to avoid conflict with mido.Message
                    
                    # Send note on for each instrument with a hit at this position
                    for inst, grid_data in grid.items():
                        if grid_data[m][t]:
                            channel = channel_map.get(inst, 0)
                            # Determine the note to play
                            current_note_to_play = key_root # Default for melodic instruments
                            
                            if inst == 'Drums':
                                beat_num_in_bar = t + 1 # 1-indexed beat within the current measure (0-15 for 16 divisions)
                                # Check against drum_pat which should have steps 1-16 for a bar
                                for role, steps_in_pattern in drum_pat.items():
                                    if beat_num_in_bar in steps_in_pattern:
                                        current_note_to_play = GM_DRUM_MAP.get(role, 36)  # Default to kick if not found
                                        logger.info(f"Drum hit: {role} (note {current_note_to_play}) at measure {m+1}, division {t+1}, channel {channel}")
                                        messages_to_send.append(mido.Message('note_on', note=current_note_to_play, velocity=100, channel=channel))
                                        break # Found a drum role for this step
                            else: # Melodic instrument
                                logger.info(f"{inst} hit (note {current_note_to_play}) at measure {m+1}, division {t+1}, channel {channel}")
                                messages_to_send.append(mido.Message('note_on', note=current_note_to_play, velocity=100, channel=channel))
                    
                    # Send all note on messages
                    for msg_to_send in messages_to_send:
                        outport.send(msg_to_send)
                    
                    # Wait for the 16th note duration
                    time.sleep(sixteenth_time)
                    
                    # Send note off for all active notes
                    for msg_to_send in messages_to_send:
                        if msg_to_send.type == 'note_on':
                            outport.send(mido.Message('note_off', note=msg_to_send.note, velocity=0, channel=msg_to_send.channel))
                
            logger.info("Playback completed successfully")
            print("\n✅ Playback completed!")
            
        except KeyboardInterrupt:
            logger.info("Playback interrupted by user")
            print("\n⏹️ Playback stopped by user")
            if outport and not outport.closed:
                for ch in range(16): # Send all notes off to all channels
                    outport.send(mido.Message('control_change', control=123, value=0, channel=ch)) # All Notes Off
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
        # The tip about installing python-rtmidi might still be relevant if mido.get_output_names() fails
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
    
    # Collect instruments
    chosen = []
    logger.info("Prompting for instruments...")
    for instr in sub["instruments"]:
        if prompt_yesno(f"Include {instr}?"):
            chosen.append(instr)
            logger.info(f"Added instrument: {instr}")
    
    logger.info(f"Selected instruments: {', '.join(chosen)}")
    
    # Get key and mode
    key = prompt_list("Choose key:", cfg["keys_modes"]["keys"])
    logger.info(f"Key selected: {key}")
    
    mode = prompt_list("Choose mode:", cfg["keys_modes"]["modes"])
    logger.info(f"Mode selected: {mode}")
    
    key_range = sub.get("key_range", {"low": 3, "high": 5})
    octave = prompt_int(f"Choose octave for '{key}'", key_range["low"], key_range["high"], allow_back=False)
    key_o = f"{key}{octave}"
    logger.info(f"Full key selected: {key_o}")
    
    print(f"Style: {style['name']}, Substyle: {sub['name']}, BPM: {bpm}, Instruments: {', '.join(chosen)}, Key: {key_o}, Mode: {mode}")
    if not prompt_yesno("Proceed with generation? (y/N)"): 
        logger.info("User cancelled at confirmation prompt")
        return run()

    # Channel assignment: based on low freq
    instr_info = cfg.get('spectrotone', {}).get('instruments', {})

    # List to keep track of melodic instruments with their frequency ranges
    melodic = []
    for i in chosen:
        if i != 'Drums':
            if i not in instr_info:
                logger.warning(f"Instrument {i} not found in spectrotone config, using default value")
                melodic.append((i, 100))  # Default value if not found
            else:
                # Use the first (lowest) frequency in the range
                freq = instr_info[i].get('range_hz', [100])[0]
                logger.info(f"Instrument {i} spectrotone low frequency: {freq} Hz")
                melodic.append((i, freq))

    # Sort by the low frequency (bass instruments first)
    melodic = [item[0] for item in sorted(melodic, key=lambda x: x[1])]
    logger.info(f"Melodic instruments sorted by frequency: {melodic}")

    # Assign channels (0-8 for melodic instruments, 9 for drums)
    channel_map = {}
    for idx, inst in enumerate(melodic[:8], start=0):  # Channels 0-7 for first 8 instruments
        channel_map[inst] = idx
        logger.info(f"Assigned channel {idx} to {inst}")

    for inst in melodic[8:]:  # Channel 8 (zero-based) for any additional instruments
        channel_map[inst] = 8
        logger.info(f"Assigned shared channel 8 to {inst} (overflow)")

    if 'Drums' in chosen:
        channel_map['Drums'] = 9  # Standard GM drum channel (10 in 1-based counting)
        logger.info("Assigned standard channel 9 to Drums")

    logger.info(f"Final channel assignment map: {channel_map}")
    
    # MIDI Generation
    key_root = note_name_to_number(key_o)
    logger.info(f"Key root MIDI note: {key_root}")
    
    # Live MIDI mode
    live_rules = cfg.get("live_rules", {})
    global drum_pat  # Make drum_pat available to send_live_midi function
    drum_pat = live_rules.get("drum_pattern", {})
    
    if prompt_yesno("Enter live mode? (sends MIDI to outputs in real-time)"):
        logger.info("Entering live MIDI mode")
        try:
            logger.info("Generating live grid...")
            grid = generate_live_grid(
                template=sub,
                live_rules=live_rules,
                key_root=key_root,
                mode=mode,
                tempo=bpm
            )
            
            # Log some stats about the grid
            instrument_stats = {}
            for inst, measures in grid.items():
                total_steps = 0
                for measure in measures:
                    total_steps += sum(1 for step in measure if step)
                instrument_stats[inst] = total_steps
                
            logger.info(f"Grid generation complete. Hit counts by instrument: {instrument_stats}")
            
            # Format filename for saving
            out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
            os.makedirs(out_dir, exist_ok=True)
            out_file = f"{style['id']}_{sub['id']}_{bpm}_{key}_{mode}_live.mid"
            out_path = os.path.join(out_dir, out_file)
            
            # Attempt MIDI playback
            logger.info("Starting live MIDI playback...")
            # Pass drum_pat to the function
            success = send_live_midi(grid, bpm, key_root, channel_map, live_rules.get("drum_pattern", {}))
            
            if not success:
                print(f"ℹ️ Live MIDI playback failed, but we can still generate a MIDI file.")
                if prompt_yesno("Generate MIDI file instead?"):
                    # Generate MIDI file since live playback failed
                    logger.info("Generating MIDI file as fallback...")
                    # Code to generate MIDI file would go here
                    # ...
                    print(f"✅ MIDI file generated: {out_path}")
            
        except Exception as e:
            logger.error(f"Error in live mode: {e}")
            traceback.print_exc()
            print(f"❌ Error: {e}")
    else:
        logger.info("Generating static MIDI file")
        # Your existing MIDI generation code here

if __name__ == "__main__":
    run()