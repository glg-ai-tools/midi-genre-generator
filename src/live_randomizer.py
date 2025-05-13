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

    grid = {}
    for inst_id in chosen_instrument_ids:
        grid[inst_id] = [[False] * divisions for _ in range(measures)]
        logger.info(f"Initialized grid for {inst_id}")

    instrument_setups = {}
    for item in template.get("instrument_setup", []):
        if item.get("instrument_id") in chosen_instrument_ids:
            instrument_setups[item["instrument_id"]] = item

    for inst_id in global_ordering:
        if inst_id not in chosen_instrument_ids or inst_id not in instrument_setups:
            if inst_id in chosen_instrument_ids:
                logger.warning(f"Skipping {inst_id} - chosen by user but no setup found in substyle '{template.get('name')}'.")
            continue

        logger.info(f"Processing {inst_id}")

        inst_config = instrument_setups[inst_id]
        z0, z1 = global_zones.get(inst_id, [0, measures])
        current_density = global_density_map.get(inst_id, 0.2)
        current_density *= inst_config.get("style_density_modifier", 1.0)
        pattern_type_from_global = global_pattern_types.get(inst_id, 'euclidean')
        density_interpretation = inst_config.get("density_interpretation", "global_fallback")
        style_patterns = inst_config.get("patterns", {})

        logger.info(f"{inst_id} config: zone=[{z0},{z1}], final_density={current_density:.2f}, interpretation='{density_interpretation}'")
        if style_patterns:
            logger.info(f"{inst_id} has style_patterns: {list(style_patterns.keys())}")

        for m in range(z0, z1):
            if m >= measures:
                continue

            measure_hits = [False] * divisions

            # Handle tiered-from-pattern: play full or core pattern
            if density_interpretation == "tiered_from_pattern" and "style_pattern_full" in style_patterns:
                base_pattern = style_patterns["style_pattern_full"]
                if isinstance(base_pattern, list) and len(base_pattern) == divisions:
                    measure_hits = list(base_pattern)
                    logger.debug(f"{inst_id} m{m}: Using tiered-from-pattern full pattern.")
                else:
                    logger.warning(f"{inst_id} m{m}: Tiered full pattern malformed or not found (expected length {divisions}).")
            # Handle pattern_probability: use provided patterns probabilistically
            elif density_interpretation == "pattern_probability" and style_patterns:
                # Select the pattern key: prefer 'style_pattern_full', else first available
                if "style_pattern_full" in style_patterns:
                    pattern_key_to_use = "style_pattern_full"
                else:
                    pattern_key_to_use = next(iter(style_patterns))
                base_pattern = style_patterns.get(pattern_key_to_use)
                if isinstance(base_pattern, list):
                    if len(base_pattern) == divisions:
                        measure_hits = list(base_pattern)
                        logger.debug(f"{inst_id} m{m}: Using style pattern '{pattern_key_to_use}'.")
                    else:
                        logger.warning(f"{inst_id} m{m}: Style pattern '{pattern_key_to_use}' is malformed (expected length {divisions}).")
                else:
                    logger.warning(f"{inst_id} m{m}: No valid style pattern '{pattern_key_to_use}' found or not a list.")

            # Default or global fallback: Euclidean or random based on global_pattern_types
            elif density_interpretation == "global_fallback":
                if pattern_type_from_global == 'euclidean':
                    k = max(0, min(divisions, int(current_density * divisions)))
                    measure_hits = make_euclidean(k, divisions)
                    logger.debug(f"{inst_id} m{m}: Using global Euclidean fallback with k={k}.")
                else:
                    logger.debug(f"{inst_id} m{m}: Using random probabilistic fallback.")
                    measure_hits = [random.random() < current_density for _ in range(divisions)]
            else:
                # Unsupported interpretation: warn and use empty pattern
                logger.warning(f"{inst_id} m{m}: Unsupported density interpretation '{density_interpretation}'.")
                # measure_hits remains all False

            for t, on in enumerate(measure_hits):
                if on:
                    grid[inst_id][m][t] = True

    for inst_id_log, inst_grid_log in grid.items():
        total_hits = sum(sum(1 for step in row if step) for row in inst_grid_log)
        total_steps_in_grid = measures * divisions
        logger.info(f"{inst_id_log} hit density: {total_hits}/{total_steps_in_grid} ({total_hits/total_steps_in_grid*100:.1f}%)")

    return grid
