"""
protocol_utils.py
Shared utilities for mixture_protocol.py and virtual_trial.py.

  - generate_volumes()        : pure NumPy — no opentrons dependency
  - plan_batches()            : pure Python — no opentrons dependency
  - dispense_with_batching()  : accepts opentrons objects as arguments
                                but never imports opentrons itself,
                                so this module is safe to import anywhere.
"""

import numpy as np

TIP_CAPACITY_UL = 199  # Stay strictly below the 200 µL physical limit.


def generate_volumes():
    """
    Return a list of 96 well volumes, each a 4-element list [C0, C1, C2, Water].

    Structure:
      - 48 binary-pair wells  (C0+C1, C0+C2, C1+C2) with optional water dilution
      - 48 random-mixture wells drawn from a symmetric Dirichlet (seed=42)

    Color index mapping:
      0 → Sky Blue
      1 → Grass Green
      2 → Sunset Yellow
      3 → Water
    """
    total_vol = 200
    min_vol = 20

    def make_binary_pair(idx_a: int, idx_b: int) -> list:
        wells = []
        # 8 undiluted
        for a, b in [(180, 20), (160, 40), (140, 60), (120, 80),
                     (100, 100), (80, 120), (60, 140), (40, 160)]:
            v = [0, 0, 0, 0]
            v[idx_a], v[idx_b] = a, b
            wells.append(v)
        # 4 mid-diluted
        for a, b in [(100, 20), (80, 40), (60, 60), (40, 80)]:
            v = [0, 0, 0, 0]
            v[idx_a], v[idx_b] = a, b
            v[3] = total_vol - a - b
            wells.append(v)
        # 4 heavily diluted
        for a, b, w in [(60, 20, 120), (40, 40, 120), (20, 60, 120), (20, 20, 160)]:
            v = [0, 0, 0, 0]
            v[idx_a], v[idx_b] = a, b
            v[3] = w
            wells.append(v)
        return wells

    binary = make_binary_pair(0, 1) + make_binary_pair(0, 2) + make_binary_pair(1, 2)

    rng = np.random.default_rng(seed=42)
    random_wells = []
    for _ in range(48):
        fracs = rng.dirichlet([1, 1, 1, 1])
        vols = np.array([min_vol] * 4, dtype=float) + fracs * (total_vol - 4 * min_vol)
        vols = np.round(vols).astype(int)
        diff = total_vol - int(vols.sum())
        if diff != 0:
            vols[np.argmax(vols)] += diff
        random_wells.append(vols.tolist())

    return binary + random_wells


def plan_batches(wells, volumes, tip_capacity: int = TIP_CAPACITY_UL) -> list:
    """
    Partition wells into contiguous-run batches that each fit within tip_capacity.

    Parameters
    ----------
    wells      : sequence of well identifiers (opentrons Well objects or strings).
    volumes    : sequence of int/float volumes, one per well.
    tip_capacity : maximum µL per aspiration (default TIP_CAPACITY_UL).

    Returns
    -------
    List of batches.  Each batch is a list of (well, volume) tuples.
    Wells with volume <= 0 are silently skipped.
    """
    targets = [(w, v) for w, v in zip(wells, volumes) if v > 0]

    batches: list = []
    batch: list = []
    batch_total = 0

    for well, vol in targets:
        if batch_total + vol > tip_capacity:
            batches.append(batch)
            batch = []
            batch_total = 0
        batch.append((well, vol))
        batch_total += vol

    if batch:
        batches.append(batch)

    return batches


def dispense_with_batching(protocol, pipette, source_well, all_wells, volumes, liquid_name):
    """
    Dispense *volumes* into *all_wells* on the Opentrons Flex using contiguous-run batching.

    One tip covers the entire liquid; it is picked up at the start and dropped
    at the end.  Each batch = one aspirate + N dispenses.

    Parameters
    ----------
    protocol    : opentrons ProtocolContext
    pipette     : loaded InstrumentContext
    source_well : source reservoir well
    all_wells   : sequence of destination Well objects (row-major order)
    volumes     : sequence of volumes matching all_wells
    liquid_name : string label used in protocol comments
    """
    protocol.comment(f"Dispensing {liquid_name} with contiguous-run batching")

    batches = plan_batches(all_wells, volumes)

    if not batches:
        protocol.comment(f"  No wells require {liquid_name}, skipping.")
        return

    pipette.pick_up_tip()

    for batch in batches:
        batch_total = sum(v for _, v in batch)
        pipette.aspirate(batch_total, source_well)
        for b_well, b_vol in batch:
            pipette.dispense(b_vol, b_well.top(-5))
        if pipette.current_volume > 0:
            pipette.blow_out(source_well.top())

    pipette.drop_tip()
    protocol.comment(f"  {liquid_name}: {len(batches)} batch(es), 1 tip total.")
