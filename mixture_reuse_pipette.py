import numpy as np
from opentrons import protocol_api

metadata = {
    "protocolName": "RYB Mixture Plate - Binary Pairs + Random",
    "description": "48 binary pair wells (R+Y, R+B, Y+B) + 48 random mixture wells (R,Y,B,W). "
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

    # R=0, Y=1, B=2, W=3
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


def run(protocol: protocol_api.ProtocolContext) -> None:
    # ---- Generate volume arrays ----
    all_volumes = generate_volumes()  # List of 96 × [R, Y, B, W]

    # Separate into per-solution arrays for dispensing
    red_vols    = [v[0] for v in all_volumes]
    yellow_vols = [v[1] for v in all_volumes]
    blue_vols   = [v[2] for v in all_volumes]
    water_vols  = [v[3] for v in all_volumes]

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

    reservoir_red = protocol.load_labware(
        "nest_1_reservoir_195ml", location="A1",
        namespace="opentrons", version=3,
    )
    reservoir_yellow = protocol.load_labware(
        "nest_1_reservoir_195ml", location="B1",
        namespace="opentrons", version=3,
    )
    reservoir_blue = protocol.load_labware(
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
    liquid_red = protocol.define_liquid("Red", display_color="#FF0000")
    liquid_yellow = protocol.define_liquid("Yellow", display_color="#FFD700")
    liquid_blue = protocol.define_liquid("Blue", display_color="#0000FF")
    liquid_water = protocol.define_liquid("Water", display_color="#87CEEB")

    reservoir_red["A1"].load_liquid(liquid_red, volume=195000)
    reservoir_yellow["A1"].load_liquid(liquid_yellow, volume=195000)
    reservoir_blue["A1"].load_liquid(liquid_blue, volume=195000)
    reservoir_water["A1"].load_liquid(liquid_water, volume=195000)

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

    # ---- Step 5: Dispense liquids continuously by well block (1 tip per solution) ----
    well_blocks = [
        ("Wells 1-16 (R+Y binary)", 0, 16),
        ("Wells 17-32 (R+B binary)", 16, 32),
        ("Wells 33-48 (Y+B binary)", 32, 48),
        ("Wells 49-96 (Random)", 48, 96),
    ]

    def dispense_liquid_across_blocks(liquid_name, source_well, volumes):
        protocol.comment(f"Dispensing {liquid_name} continuously across well blocks (1 tip)")
        pipette.pick_up_tip()

        for block_name, start_idx, end_idx in well_blocks:
            protocol.comment(f"{liquid_name}: {block_name}")
            for well, vol in zip(all_wells[start_idx:end_idx], volumes[start_idx:end_idx]):
                if vol <= 0:
                    continue

                # Keep the same tip and refill only when needed.
                if pipette.current_volume < vol:
                    refill_vol = pipette.max_volume - pipette.current_volume
                    pipette.aspirate(refill_vol, source_well)

                pipette.dispense(vol, well.top(-5))
                pipette.blow_out(well.top(-2))

        pipette.drop_tip()

    # 5A-5D: Continuous dispensing by block, variable aliquot per well
    dispense_liquid_across_blocks("Water", reservoir_water["A1"], water_vols)
    dispense_liquid_across_blocks("Red", reservoir_red["A1"], red_vols)
    dispense_liquid_across_blocks("Yellow", reservoir_yellow["A1"], yellow_vols)
    dispense_liquid_across_blocks("Blue", reservoir_blue["A1"], blue_vols)

    protocol.comment("Total tips used: 4 (Water + Red + Yellow + Blue)")
    protocol.comment("Wells 1-16: R+Y binary | 17-32: R+B binary | 33-48: Y+B binary | 49-96: Random")

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
