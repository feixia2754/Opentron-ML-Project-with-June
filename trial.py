from opentrons import protocol_api

metadata = {
    "protocolName": "Two-Column Contiguous-Run Dispense",
    "description": (
        "Dispense two columns in column-major order using contiguous-run refill logic. "
        "Each column gets volumes 10,10,10,10,20,80,50,20 uL."
    ),
    "author": "June + Codex",
}

requirements = {"robotType": "Flex", "apiLevel": "2.26"}

# Plate layout assumption: 8 rows x 12 columns, column-major traversal.
PLATE_ROWS = 8
PLATE_COLUMNS = 12
NUM_COLUMNS_TO_PIPETTE = 2
VOLUMES_PER_COLUMN = [10, 10, 10, 10, 20, 80, 50, 20]

# Keep every aspirate strictly below 200 uL.
TIP_CAPACITY_UL = 199

# Replace tip between contiguous mini-runs. With this setup, it replaces 3 times.
REPLACE_TIP_BETWEEN_RUNS = True


def _plan_contiguous_run(volumes, start_idx, end_idx, tip_capacity_ul):
    """
    Find the largest upcoming contiguous non-zero run in [start_idx, end_idx)
    whose total dispense volume is <= tip_capacity_ul.

    Returns (run_start_idx, run_end_idx_exclusive, run_total_ul).
    Returns (end_idx, end_idx, 0) if no positive-volume wells remain.
    """
    i = start_idx
    while i < end_idx and volumes[i] <= 0:
        i += 1

    if i >= end_idx:
        return end_idx, end_idx, 0

    total = 0
    j = i
    while j < end_idx:
        vol = volumes[j]
        if vol <= 0:
            break
        if vol > tip_capacity_ul:
            raise ValueError(
                f"Requested dispense volume {vol}uL exceeds tip capacity {tip_capacity_ul}uL."
            )
        if total + vol > tip_capacity_ul:
            break
        total += vol
        j += 1

    return i, j, total


def dispense_liquid_across_blocks(
    protocol,
    pipette,
    all_wells,
    well_blocks,
    liquid_name,
    source_well,
    volumes,
    tip_capacity_ul=TIP_CAPACITY_UL,
    replace_tip_between_runs=REPLACE_TIP_BETWEEN_RUNS,
):
    """
    Dispense across block ranges with contiguous-run lookahead.

    Assumptions:
    - all_wells/volumes use column-major order (A1..H1, A2..H2, ...).
    - Wells with volume <= 0 are skipped.
    - Each aspirate uses the exact run total, not full tip capacity.
    """
    protocol.comment(f"Dispensing {liquid_name} with contiguous-run planning")

    tip_on = False
    tip_replacements = 0

    for block_name, start_idx, end_idx in well_blocks:
        protocol.comment(f"{liquid_name}: {block_name}")
        block_cursor = start_idx

        while block_cursor < end_idx:
            run_start, run_end, run_total = _plan_contiguous_run(
                volumes=volumes,
                start_idx=block_cursor,
                end_idx=end_idx,
                tip_capacity_ul=tip_capacity_ul,
            )

            if run_total == 0:
                break

            if run_total > pipette.max_volume:
                raise ValueError(
                    f"Run volume {run_total}uL exceeds pipette max volume {pipette.max_volume}uL."
                )

            if not tip_on:
                pipette.pick_up_tip()
                tip_on = True
            elif replace_tip_between_runs:
                pipette.drop_tip()
                pipette.pick_up_tip()
                tip_replacements += 1

            pipette.aspirate(run_total, source_well)

            for idx in range(run_start, run_end):
                vol = volumes[idx]
                if vol <= 0:
                    continue
                pipette.dispense(vol, all_wells[idx].top(-5))
                pipette.blow_out(all_wells[idx].top(-2))

            block_cursor = run_end

    if tip_on:
        pipette.drop_tip()

    protocol.comment(f"Tip replacements during dispense: {tip_replacements}")


def run(protocol: protocol_api.ProtocolContext) -> None:
    # Labware
    tip_rack = protocol.load_labware(
        "opentrons_flex_96_tiprack_200ul",
        location="A2",
        namespace="opentrons",
        version=1,
    )
    source_reservoir = protocol.load_labware(
        "nest_1_reservoir_195ml",
        location="A1",
        namespace="opentrons",
        version=3,
    )
    plate = protocol.load_labware(
        "armadillo_96_wellplate_200ul_pcr_full_skirt",
        location="D2",
        namespace="opentrons",
        version=3,
    )

    # Instrument
    pipette = protocol.load_instrument(
        "flex_1channel_1000",
        mount="right",
        tip_racks=[tip_rack],
    )

    # Build two-column column-major target order: A1..H1, A2..H2
    all_wells = [well for col in plate.columns()[:NUM_COLUMNS_TO_PIPETTE] for well in col]

    # Per-column dispensing pattern repeated for two columns.
    volumes = VOLUMES_PER_COLUMN * NUM_COLUMNS_TO_PIPETTE

    # Block per column so each column is completed before moving to the next.
    well_blocks = [
        (f"Column {col + 1}", col * PLATE_ROWS, (col + 1) * PLATE_ROWS)
        for col in range(NUM_COLUMNS_TO_PIPETTE)
    ]

    dispense_liquid_across_blocks(
        protocol=protocol,
        pipette=pipette,
        all_wells=all_wells,
        well_blocks=well_blocks,
        liquid_name="Sample",
        source_well=source_reservoir["A1"],
        volumes=volumes,
        tip_capacity_ul=TIP_CAPACITY_UL,
        replace_tip_between_runs=True,
    )
