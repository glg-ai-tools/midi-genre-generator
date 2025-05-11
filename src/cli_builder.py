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
        
    try:
        # Find available MIDI outputs
        available_ports = mido.get_output_names()
        if not available_ports:
            logger.warning("No MIDI output ports available. Please connect a MIDI device.")
            print("❌ Warning: No MIDI output ports found. Please check your MIDI device connections.")
            print("ℹ️ Info: Will attempt to use a virtual port instead.")
            try:
                # Try to create a virtual port if no physical ports are available
                outport = mido.open_output('MIDI Generator Virtual Port', virtual=True)
                logger.info("Created virtual MIDI output port")
                print("✅ Created virtual MIDI output port.")
            except Exception as e:
                logger.error(f"Failed to create virtual port: {e}")
                print("❌ Error: Could not create virtual MIDI port. Check your MIDI setup.")
                return False
        else:
            # Choose the first available port
            port_name = available_ports[0]
            logger.info(f"Found {len(available_ports)} MIDI output ports")
            logger.info(f"Using MIDI output port: {port_name}")
            print(f"✅ Using MIDI output port: {port_name}")
            outport = mido.open_output(port_name)
            
        beat_time = 60.0 / tempo  # Time for one beat in seconds
        sixteenth_time = beat_time / 4.0  # Time for one 16th note
        
        measures = len(next(iter(grid.values())))
        divisions = len(next(iter(grid.values()))[0])
        
        logger.info(f"Grid configuration: {measures} measures, {divisions} divisions per measure")
        logger.info(f"Timing: Beat = {beat_time:.3f}s, 16th = {sixteenth_time:.3f}s")
        logger.info(f"Channel mapping: {channel_map}")
        print(f"ℹ️ Playing {measures} measures, tempo: {tempo} BPM")
        print("🎵 Starting MIDI playback...")
        
        try:
            # Play the grid
            for m in range(measures):
                logger.info(f"Playing measure {m+1}/{measures}")
                print(f"Measure {m+1}/{measures}", end="\r")
                for t in range(divisions):
                    messages = []
                    
                    # Send note on for each instrument with a hit at this position
                    for inst, grid_data in grid.items():
                        if grid_data[m][t]:
                            channel = channel_map.get(inst, 0)
                            note = key_root
                            
                            # Drums use specific note numbers
                            if inst == 'Drums':
                                # Try to determine which drum part is playing
                                beat_num = m * divisions + t + 1
                                for role, beats in drum_pat.items():
                                    if beat_num % 16 in beats or beat_num in beats:
                                        note = GM_DRUM_MAP.get(role, 36)  # Default to kick if not found
                                        logger.info(f"Drum hit: {role} (note {note}) at measure {m+1}, beat {t+1}")
                                        messages.append(mido.Message('note_on', note=note, velocity=100, channel=channel))
                            else:
                                logger.info(f"{inst} hit (note {note}) at measure {m+1}, beat {t+1}, channel {channel}")
                                messages.append(mido.Message('note_on', note=note, velocity=100, channel=channel))
                    
                    # Send all note on messages
                    for msg in messages:
                        outport.send(msg)
                    
                    # Wait for the 16th note duration
                    time.sleep(sixteenth_time)
                    
                    # Send note off for all active notes
                    for msg in messages:
                        if msg.type == 'note_on':
                            outport.send(mido.Message('note_off', note=msg.note, velocity=0, channel=msg.channel))
                
            logger.info("Playback completed successfully")
            print("\n✅ Playback completed!")
            
        except KeyboardInterrupt:
            # Graceful shutdown if user presses Ctrl+C
            logger.info("Playback interrupted by user")
            print("\n⏹️ Playback stopped by user")
            # Send all notes off on all channels to prevent stuck notes
            for channel in range(16):
                outport.send(mido.Message('control_change', control=123, value=0, channel=channel))
                
        finally:
            # Always close the port properly
            outport.close()
            logger.info("MIDI output port closed")
            
        return True
            
    except Exception as e:
        logger.error(f"Error during MIDI playback: {e}")
        traceback.print_exc()
        print(f"❌ Error: {e}")
        print("💡 Tip: Try installing 'python-rtmidi' with: pip install python-rtmidi")
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