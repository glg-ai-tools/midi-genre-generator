import random
import logging

logger = logging.getLogger(__name__)

def make_euclidean(k, n):
    """
    Generate a Euclidean rhythm with k pulses across n steps.
    Returns a list of boolean values.
    """
    counts = [[1] for _ in range(k)] + [[0] for _ in range(n-k)]
    while len(counts) > 1:
        for i in range(len(counts)//2):
            counts[i] += counts.pop()
    return [bool(x) for x in counts[0]]

# Returns dict inst -> 2D grid
def generate_live_grid(template, live_rules, key_root, mode, tempo):
    """
    Generate a 2D grid of hits for each instrument based on live rules.
    Returns a dictionary of instrument -> 2D grid (measures x divisions).
    """
    measures = live_rules.get('measures', 16)
    divisions = live_rules.get('grid_division', 16)
    ordering = live_rules.get('instrument_precedence', [])
    density_map = live_rules.get('randomization', {}).get('density', {})
    types = live_rules.get('randomization', {}).get('pattern_types', {})
    zones = live_rules.get('allocation_zones', {})
    
    logger.info(f"Generating live grid: {measures} measures, {divisions} divisions")
    logger.info(f"Available instruments in template: {template.get('instruments', [])}")
    logger.info(f"Instrument precedence: {ordering}")

    # Initialize grid for all instruments from template
    grid = {}
    for inst in template.get('instruments', []):
        grid[inst] = [[False] * divisions for _ in range(measures)]
        logger.info(f"Initialized grid for {inst}")
    
    # Process instruments according to precedence order
    for inst in ordering:
        # Skip if instrument not in template/grid
        if inst not in grid:
            logger.info(f"Skipping {inst} - not in template")
            continue
            
        logger.info(f"Processing {inst}")
        z0, z1 = zones.get(inst, [0, measures])
        d = density_map.get(inst, 0.2)
        ptype = types.get(inst, 'euclidean')
        
        logger.info(f"{inst} configuration: zone=[{z0},{z1}], density={d}, pattern={ptype}")
        
        for m in range(z0, z1):
            if m >= measures:
                continue  # Safety check
                
            if ptype == 'euclidean':
                k = max(1, int(d * divisions))
                hits = make_euclidean(k, divisions)
            else:
                hits = [random.random() < d for _ in range(divisions)]
                
            for t, on in enumerate(hits):
                if not on: 
                    continue
                    
                # Check if higher precedence instruments already have a hit here
                skip_hit = False
                for h in ordering[:ordering.index(inst)]:
                    if h in grid and m < len(grid[h]) and t < len(grid[h][m]) and grid[h][m][t]:
                        skip_hit = True
                        break
                        
                if skip_hit:
                    continue
                    
                grid[inst][m][t] = True
    
    # Log the density of hits for each instrument
    for inst, inst_grid in grid.items():
        total_hits = sum(sum(row) for row in inst_grid)
        total_steps = measures * divisions
        logger.info(f"{inst} hit density: {total_hits}/{total_steps} ({total_hits/total_steps*100:.1f}%)")
    
    return grid
