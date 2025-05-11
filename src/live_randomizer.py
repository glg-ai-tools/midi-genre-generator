import random
import logging

logger = logging.getLogger(__name__)

def make_euclidean(k, n):
    """
    Generate a Euclidean rhythm with k pulses across n steps.
    Returns a list of boolean values.
    """
    if k <= 0: return [False] * n
    if k >= n: return [True] * n
    counts = [[1] for _ in range(k)] + [[0] for _ in range(n-k)]
    while len(counts) > 1:
        # Ensure we don't try to pop from an empty list if k is very small or n-k is small
        len_counts_half = len(counts) // 2
        for i in range(min(len_counts_half, len(counts) - len_counts_half)): # Iterate up to the shorter part
            counts[i] += counts.pop()
    return [bool(x) for x in counts[0]]

def generate_live_grid(template, live_rules, key_root, mode, tempo, chosen_instrument_ids, master_instrument_defs, cfg):
    """
    Generate a 2D grid of hits for each instrument based on live rules and style-specific patterns.
    'template' is the substyle_config object.
    'cfg' is the full application configuration.
    Returns a dictionary of instrument_id -> 2D grid (measures x divisions).
    """
    measures = live_rules.get('measures', 16)
    divisions = live_rules.get('grid_division', 16)
    global_ordering = live_rules.get('instrument_precedence', [])
    global_density_map = live_rules.get('randomization', {}).get('density', {})
    global_pattern_types = live_rules.get('randomization', {}).get('pattern_types', {})
    global_zones = live_rules.get('allocation_zones', {})
    
    logger.info(f"Generating live grid: {measures} measures, {divisions} divisions")
    logger.info(f"Chosen instruments for generation: {chosen_instrument_ids}")
    logger.info(f"Global instrument precedence: {global_ordering}")

    grid = {}
    # Initialize grid only for chosen instruments
    for inst_id in chosen_instrument_ids:
        grid[inst_id] = [[False] * divisions for _ in range(measures)]
        logger.info(f"Initialized grid for {inst_id}")

    # Create a lookup for instrument_setup details for chosen instruments
    instrument_setups = {}
    for item in template.get("instrument_setup", []):
        if item.get("instrument_id") in chosen_instrument_ids:
            instrument_setups[item["instrument_id"]] = item
    
    # Process instruments according to global precedence order
    # Only process if the instrument was chosen by the user and has a setup
    for inst_id in global_ordering:
        if inst_id not in chosen_instrument_ids or inst_id not in instrument_setups:
            if inst_id in chosen_instrument_ids: # Chosen but no setup found (should ideally not happen if config is correct)
                 logger.warning(f"Skipping {inst_id} - chosen by user but no setup found in substyle '{template.get('name')}'.")
            # else: # Not chosen by user, so skipping is normal
            #    logger.debug(f"Skipping {inst_id} - not in chosen instruments for this generation.")
            continue
            
        logger.info(f"Processing {inst_id}")
        
        # Get instrument-specific configuration from instrument_setup
        inst_config = instrument_setups[inst_id]
        
        # Get style-specific or global fallback values
        # Zone: Use global zone as fallback if not in inst_config (though ideally it should be)
        z0, z1 = global_zones.get(inst_id, [0, measures]) 
        # Density: Start with global, then apply style modifier
        current_density = global_density_map.get(inst_id, 0.2) 
        current_density *= inst_config.get("style_density_modifier", 1.0)
        # Pattern type: Use global as fallback
        pattern_type_from_global = global_pattern_types.get(inst_id, 'euclidean') 
        
        density_interpretation = inst_config.get("density_interpretation", "global_fallback") # e.g., "pattern_probability", "tiered_from_pattern", "global_fallback"
        style_patterns = inst_config.get("patterns", {})

        logger.info(f"{inst_id} config: zone=[{z0},{z1}], final_density={current_density:.2f}, interpretation='{density_interpretation}'")
        if style_patterns:
            logger.info(f"{inst_id} has style_patterns: {list(style_patterns.keys())}")

        for m in range(z0, z1):
            if m >= measures:
                continue  # Safety check
            
            measure_hits = [False] * divisions # Default to silence for the measure

            if density_interpretation == "pattern_probability" and style_patterns:
                # Determine which pattern to use (e.g., "kick", "snare" for drums, or a single main pattern)
                # This part needs to be more robust if an instrument has multiple pattern types (like drums)
                # For now, let's assume a simple case or that send_live_midi handles drum sub-patterns.
                # Here, we'll try to get a generic 'style_pattern_full' or the first available pattern.
                
                pattern_key_to_use = None
                if "style_pattern_full" in style_patterns:
                    pattern_key_to_use = "style_pattern_full"
                elif style_patterns: # Get the first pattern if 'style_pattern_full' isn't there
                    pattern_key_to_use = next(iter(style_patterns))

                if pattern_key_to_use and isinstance(style_patterns.get(pattern_key_to_use), list):
                    base_pattern = style_patterns[pattern_key_to_use]
                    if len(base_pattern) == divisions and random.random() < current_density:
                        measure_hits = list(base_pattern) # Make a copy
                        logger.debug(f"{inst_id} m{m}: Using style pattern '{pattern_key_to_use}' due to probability.")
                    else:
                        logger.debug(f"{inst_id} m{m}: Style pattern '{pattern_key_to_use}' not triggered by probability or malformed.")
                else: # Fallback if no suitable style pattern for this interpretation
                    logger.debug(f"{inst_id} m{m}: No suitable style pattern for 'pattern_probability', falling back to global for measure.")
                    density_interpretation = "global_fallback" # Force fallback for this measure

            # Tiered interpretation (simplified example)
            elif density_interpretation == "tiered_from_pattern" and "style_pattern_full" in style_patterns and isinstance(style_patterns["style_pattern_full"], list):
                full_pattern = style_patterns["style_pattern_full"]
                if len(full_pattern) == divisions:
                    num_core_notes = inst_config.get("core_pattern_notes", 1)
                    num_full_notes = inst_config.get("full_pattern_notes", sum(1 for x in full_pattern if x)) # Count true hits in pattern
                    
                    notes_to_play = 0
                    if current_density >= 0.75 and num_full_notes > 0: # Play full pattern
                        notes_to_play = num_full_notes
                    elif current_density >= 0.40: # Play core notes
                        notes_to_play = num_core_notes
                    elif current_density > 0.0: # Play at least one note if possible
                        notes_to_play = max(1, num_core_notes // 2) if num_core_notes > 0 else 0
                    
                    if notes_to_play > 0:
                        # Get indices of actual hits in the full_pattern
                        hit_indices = [i for i, hit_present in enumerate(full_pattern) if hit_present]
                        random.shuffle(hit_indices) # Shuffle to pick random notes from the pattern
                        
                        for i in range(min(notes_to_play, len(hit_indices))):
                            measure_hits[hit_indices[i]] = True
                        logger.debug(f"{inst_id} m{m}: Using tiered pattern, playing {notes_to_play} notes.")
                    else:
                        logger.debug(f"{inst_id} m{m}: Tiered pattern resulted in 0 notes for density {current_density:.2f}.")

                else:
                    logger.debug(f"{inst_id} m{m}: 'style_pattern_full' malformed for tiered, falling back to global.")
                    density_interpretation = "global_fallback" # Force fallback

            # Fallback to global Euclidean/probability if no style pattern applies or forced
            if density_interpretation == "global_fallback":
                logger.debug(f"{inst_id} m{m}: Using global fallback generation (type: {pattern_type_from_global}).")
                if pattern_type_from_global == 'euclidean':
                    k = max(0, int(current_density * divisions)) # Allow k=0 for very low densities
                    measure_hits = make_euclidean(k, divisions)
                else: # probability
                    measure_hits = [random.random() < current_density for _ in range(divisions)]
            
            # Place hits on the main grid, respecting precedence
            for t, on in enumerate(measure_hits):
                if not on: 
                    continue
                    
                skip_hit = False
                # Check against all higher precedence instruments that are *also chosen by the user*
                for h_inst_id in global_ordering[:global_ordering.index(inst_id)]:
                    if h_inst_id in grid: # Check if the higher precedence instrument is part of the current generation
                        if m < len(grid[h_inst_id]) and t < len(grid[h_inst_id][m]) and grid[h_inst_id][m][t]:
                            skip_hit = True
                            break
                        
                if skip_hit:
                    continue
                    
                grid[inst_id][m][t] = True
    
    # Log the density of hits for each instrument
    for inst_id_log, inst_grid_log in grid.items():
        if not inst_grid_log: continue # Should not happen if initialized correctly
        total_hits = sum(sum(1 for step in row if step) for row in inst_grid_log)
        total_steps_in_grid = measures * divisions # Potential steps for this instrument
        # Actual available steps might be less due to allocation zones, but this gives overall grid density
        if total_steps_in_grid > 0:
            logger.info(f"{inst_id_log} hit density: {total_hits}/{total_steps_in_grid} ({total_hits/total_steps_in_grid*100:.1f}%)")
        else:
            logger.info(f"{inst_id_log} hit density: 0/0 (No steps defined)")
            
    return grid
