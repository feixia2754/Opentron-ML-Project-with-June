import numpy as np
from opentrons import protocol_api

metadata = {
    "protocolName": "Sky Blue / Pink / Sunset Yellow Mixture Plate - Binary Pairs + Random",
    "description": "48 binary pair wells (SB+PK, SB+SY, PK+SY) + 48 random mixture wells (SB,PK,SY,W). "
                   "Total 96 wells, 200µL each, min 20µL per solution, integer volumes, seed=42.",
    "author": "June",
}

requirements = {"robotType": "Flex", "apiLevel": "2.26"}


def generate_volumes():
    """Generate all 96 well volumes: 48 binary + 48 random (Dirichlet)."""
    total_vol = 200
    min_vol = 20

    # ---- Binary Pairs (48 wells) ----
    def make_binary_pair(idx_a, idx_b):
        wells = []
        # 8 undiluted (no water)
        for a, b in [(180,20),(160,40),(140,60),(120,80),
                      (100,100),(80,120),(60,140),(40,160)]:
            vol = [0, 0, 0, 0]
            vol[idx_a], vol[idx_b] = a, b
            wells.append(vol)
        # 4 mid-diluted (80µL water)
        for a, b in [(100,20),(80,40),(60,60),(40,80)]:
            vol = [0, 0, 0, 0]
            vol[idx_a], vol[idx_b] = a, b
            vol[3] = total_vol - a - b
            wells.append(vol)
        # 4 heavily diluted (120-160µL water)
        for a, b, w in [(60,20,120),(40,40,120),(20,60,120),(20,20,160)]:
            vol = [0, 0, 0, 0]
            vol[idx_a], vol[idx_b] = a, b
            vol[3] = w
            wells.append(vol)
        return wells

    # SB=0, PK=1, SY=2, W=3
    binary = make_binary_pair(0, 1) + make_binary_pair(0, 2) + make_binary_pair(1, 2)

    # ---- Random Mixtures (48 wells, Dirichlet) ----
    rng = np.random.default_rng(seed=42)
    random_wells = []
    for _ in range(48):
        fracs = rng.dirichlet([1, 1, 1, 1])
        remaining = total_vol - 4 * min_vol
        vols = np.array([min_vol] * 4, dtype=float) + fracs * remaining
        vols = np.round(vols).astype(int)
        diff = total_vol - int(vols.sum())
        if diff != 0:
            vols[np.argmax(vols)] += diff
        random_wells.append(vols.tolist())

    return binary + random_wells


TIP_CAPACITY_UL = 199  # Stay strictly below the 200 µL physical limit.


def dispense_with_batching(protocol, pipette, source_well, all_wells, volumes, liquid_name):
    """
    Dispense *volumes* into *all_wells* using contiguous-run batching.

    One tip is used for the entire liquid.  Wells are accumulated one-by-one
    into a batch until adding the next well would exceed TIP_CAPACITY_UL.
    Each batch is executed as a single aspirate followed by individual
    dispenses, maximising volume per tip load.
    """
    protocol.comment(f"Dispensing {liquid_name} with contiguous-run batching")

    targets = [(well, vol) for well, vol in zip(all_wells, volumes) if vol > 0]
    if not targets:
        protocol.comment(f"  No wells require {liquid_name}, skipping.")
        return

    pipette.pick_up_tip()

    batch_wells: list = []
    batch_total = 0
    batch_count = 0

    for well, vol in targets:
        if batch_total + vol > TIP_CAPACITY_UL:
            # Current batch is full — execute it.
            pipette.aspirate(batch_total, source_well)
            for b_well, b_vol in batch_wells:
                pipette.dispense(b_vol, b_well.top(-5))
            if pipette.current_volume > 0:
                pipette.blow_out(source_well.top())
            batch_count += 1
            batch_wells = []
            batch_total = 0

        batch_wells.append((well, vol))
        batch_total += vol

    # Execute the final (possibly only) batch.
    if batch_wells:
        pipette.aspirate(batch_total, source_well)
        for b_well, b_vol in batch_wells:
            pipette.dispense(b_vol, b_well.top(-5))
        if pipette.current_volume > 0:
            pipette.blow_out(source_well.top())
        batch_count += 1

    pipette.drop_tip()
    protocol.comment(f"  {liquid_name}: {batch_count} batch(es), 1 tip total.")


def run(protocol: protocol_api.ProtocolContext) -> None:
    # ---- Generate volume arrays ----
    all_volumes = generate_volumes()  # List of 96 × [SB, PK, SY, W]

    # Separate into per-solution arrays for dispensing
    sky_blue_vols      = [v[0] for v in all_volumes]
    pink_vols          = [v[1] for v in all_volumes]
    sunset_yellow_vols = [v[2] for v in all_volumes]
    water_vols         = [v[3] for v in all_volumes]

    # ---- Load Modules ----
    absorbance_reader = protocol.load_module("absorbanceReaderV1", "D3")
    heater_shaker = protocol.load_module("heaterShakerModuleV1", "D1")

    # ---- Load Adapters ----
    hs_adapter = heater_shaker.load_adapter(
        "opentrons_96_pcr_adapter",
        namespace="opentrons",
        version=1,
    )

    # ---- Load Labware ----
    tip_rack = protocol.load_labware(
        "opentrons_flex_96_tiprack_200ul",
        location="A2",
        namespace="opentrons",
        version=1,
    )

    reservoir_sky_blue = protocol.load_labware(
        "nest_1_reservoir_195ml", location="A1",
        namespace="opentrons", version=3,
    )
    reservoir_pink = protocol.load_labware(
        "nest_1_reservoir_195ml", location="B1",
        namespace="opentrons", version=3,
    )
    reservoir_sunset_yellow = protocol.load_labware(
        "nest_1_reservoir_195ml", location="C1",
        namespace="opentrons", version=3,
    )
    reservoir_water = protocol.load_labware(
        "nest_1_reservoir_195ml", location="B2",
        namespace="opentrons", version=3,
    )

    well_plate = protocol.load_labware(
        "armadillo_96_wellplate_200ul_pcr_full_skirt",
        location="D2",
        label="Mixture Plate",
        namespace="opentrons",
        version=3,
        lid="opentrons_tough_universal_lid",
        lid_namespace="opentrons",
        lid_version=1,
    )

    # ---- Load Pipette ----
    pipette = protocol.load_instrument(
        "flex_1channel_1000", "right", tip_racks=[tip_rack]
    )

    # ---- Load Trash ----
    trash = protocol.load_trash_bin("A3")

    # ---- Define Liquids ----
    liquid_sky_blue      = protocol.define_liquid("Sky Blue",      display_color="#1E90FF")
    liquid_pink          = protocol.define_liquid("Pink",          display_color="#FF69B4")
    liquid_sunset_yellow = protocol.define_liquid("Sunset Yellow", display_color="#FFC200")
    liquid_water         = protocol.define_liquid("Water",         display_color="#87CEEB")

    reservoir_sky_blue["A1"].load_liquid(liquid_sky_blue,           volume=195000)
    reservoir_pink["A1"].load_liquid(liquid_pink,                   volume=195000)
    reservoir_sunset_yellow["A1"].load_liquid(liquid_sunset_yellow, volume=195000)
    reservoir_water["A1"].load_liquid(liquid_water,                 volume=195000)

    # ---- Well order: row-first (A1, A2, ... A12, B1, ... H12) ----
    all_wells = well_plate.wells()  # 96 wells in order

    # ============================================================
    # PROTOCOL STEPS
    # ============================================================

    # Step 1: Move lid off plate
    protocol.move_lid(well_plate, "C3", use_gripper=True)

    # Step 2: Open heater-shaker latch
    heater_shaker.deactivate_heater()
    heater_shaker.open_labware_latch()

    # Step 3: Move plate to heater-shaker
    protocol.move_labware(well_plate, hs_adapter, use_gripper=True)

    # Step 4: Close latch
    heater_shaker.close_labware_latch()

    # ---- Step 5: Dispense liquids (1 tip per solution, contiguous-run batching) ----

    # 5A: Water
    dispense_with_batching(protocol, pipette, reservoir_water["A1"],
                           all_wells, water_vols, "Water")

    # 5B: Sky Blue
    dispense_with_batching(protocol, pipette, reservoir_sky_blue["A1"],
                           all_wells, sky_blue_vols, "Sky Blue")

    # 5C: Grass Green
    dispense_with_batching(protocol, pipette, reservoir_pink["A1"],
                           all_wells, pink_vols, "Pink")

    # 5D: Sunset Yellow
    dispense_with_batching(protocol, pipette, reservoir_sunset_yellow["A1"],
                           all_wells, sunset_yellow_vols, "Sunset Yellow")

    protocol.comment("Total tips used: 4 (Water + Sky Blue + Pink + Sunset Yellow)")
    protocol.comment("Wells 1-16: SB+PK binary | 17-32: SB+SY binary | 33-48: PK+SY binary | 49-96: Random")

    # Step 6: Open latch for lid
    heater_shaker.deactivate_heater()
    heater_shaker.open_labware_latch()

    # Step 7: Put lid back on plate
    protocol.move_lid("C3", well_plate, use_gripper=True)

    # Step 8: Close latch and shake
    heater_shaker.close_labware_latch()
    heater_shaker.set_and_wait_for_shake_speed(1000)
    protocol.delay(seconds=30)

    # Step 9: Stop shaker, open latch
    heater_shaker.deactivate_shaker()
    heater_shaker.open_labware_latch()

    # Step 10: Initialize absorbance reader
    absorbance_reader.close_lid()
    absorbance_reader.initialize("multi", [450, 562, 600, 650])
    absorbance_reader.open_lid()

    # Step 11: Move lid off plate for reader
    protocol.move_lid(well_plate, "D2", use_gripper=True)

    # Step 12: Move plate to absorbance reader
    protocol.move_labware(well_plate, absorbance_reader, use_gripper=True)

    # Step 13: Read absorbance
    absorbance_reader.close_lid()
    absorbance_reader.read(export_filename="RYB_Mixture_Plate")

    # Step 14: Open reader
    absorbance_reader.open_lid()
