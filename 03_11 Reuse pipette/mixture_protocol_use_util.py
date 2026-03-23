from opentrons import protocol_api
from protocol_utils import TIP_CAPACITY_UL, generate_volumes, dispense_with_batching  # noqa: F401

metadata = {
    "protocolName": "Sky Blue / Grass Green / Sunset Yellow Mixture Plate - Binary Pairs + Random",
    "description": "48 binary pair wells (SB+GG, SB+SY, GG+SY) + 48 random mixture wells (SB,GG,SY,W). "
                   "Total 96 wells, 200µL each, min 20µL per solution, integer volumes, seed=42.",
    "author": "June",
}

requirements = {"robotType": "Flex", "apiLevel": "2.26"}


def run(protocol: protocol_api.ProtocolContext) -> None:
    # ---- Generate volume arrays ----
    all_volumes = generate_volumes()  # List of 96 × [SB, GG, SY, W]

    # Separate into per-solution arrays for dispensing
    sky_blue_vols      = [v[0] for v in all_volumes]
    grass_green_vols   = [v[1] for v in all_volumes]
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
    reservoir_grass_green = protocol.load_labware(
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
    liquid_grass_green   = protocol.define_liquid("Grass Green",   display_color="#228B22")
    liquid_sunset_yellow = protocol.define_liquid("Sunset Yellow", display_color="#FFC200")
    liquid_water         = protocol.define_liquid("Water",         display_color="#87CEEB")

    reservoir_sky_blue["A1"].load_liquid(liquid_sky_blue,           volume=195000)
    reservoir_grass_green["A1"].load_liquid(liquid_grass_green,     volume=195000)
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
    dispense_with_batching(protocol, pipette, reservoir_grass_green["A1"],
                           all_wells, grass_green_vols, "Grass Green")

    # 5D: Sunset Yellow
    dispense_with_batching(protocol, pipette, reservoir_sunset_yellow["A1"],
                           all_wells, sunset_yellow_vols, "Sunset Yellow")

    protocol.comment("Total tips used: 4 (Water + Sky Blue + Grass Green + Sunset Yellow)")
    protocol.comment("Wells 1-16: SB+GG binary | 17-32: SB+SY binary | 33-48: GG+SY binary | 49-96: Random")

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
