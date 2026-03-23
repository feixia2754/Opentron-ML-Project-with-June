# Continuous Pipetting + Grass Green removed for 3-color baseline redo
# Based on 03_11 Reuse pipette protocol with adjustments for 3 colors and updated labware layout
from opentrons import protocol_api

# ---------------------------------------------------------------------------
# Continuous-pipetting helpers (copied from protocol_utils.py)
# ---------------------------------------------------------------------------

TIP_CAPACITY_UL = 199  # Stay strictly below the 200 µL physical limit.


def plan_batches(wells, volumes, tip_capacity: int = TIP_CAPACITY_UL) -> list:
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


# ---------------------------------------------------------------------------

metadata = {
    "protocolName": "Colors Baseline - 3 Colors with 3 Replicates",
    "description": (
        "8-step dilution series for Sky Blue, Sunset Yellow, and Pink dyes "
        "with 3 replicates each (72 wells total)"
    ),
    "author": "OpentronsAI",
    "source": "OpentronsAI",
}

requirements = {"robotType": "Flex", "apiLevel": "2.26"}

def run(protocol: protocol_api.ProtocolContext) -> None:
    # Load Modules:
    absorbance_reader_1 = protocol.load_module("absorbanceReaderV1", "D3")
    heater_shaker_module_1 = protocol.load_module("heaterShakerModuleV1", "D1")

    # Load Adapters:
    adapter_1 = heater_shaker_module_1.load_adapter(
        "opentrons_96_pcr_adapter",
        namespace="opentrons",
        version=1,
    )

    # Load Labware:
    tip_rack_200 = protocol.load_labware(
        "opentrons_flex_96_tiprack_200ul",
        location="A2",
        namespace="opentrons",
        version=1,
    )
    
    # Reservoirs with liquids - 3 test colors + water
    reservoir_sky_blue = protocol.load_labware(
        "nest_1_reservoir_195ml",
        location="B1",  # Sky Blue
        namespace="opentrons",
        version=3,
    )
    reservoir_sunset_yellow = protocol.load_labware(
        "nest_1_reservoir_195ml",
        location="A1",  # Sunset Yellow
        namespace="opentrons",
        version=3,
    )
    reservoir_pink = protocol.load_labware(
        "nest_1_reservoir_195ml",
        location="C2",  # Pink
        namespace="opentrons",
        version=3,
    )
    reservoir_water = protocol.load_labware(
        "nest_1_reservoir_195ml",
        location="B2",  # Water
        namespace="opentrons",
        version=3,
    )
    
    well_plate_1 = protocol.load_labware(
        "armadillo_96_wellplate_200ul_pcr_full_skirt",
        location="D2",
        label="(Retired) Armadillo 96 Well Plate 200 µL PCR Full Skirt",
        namespace="opentrons",
        version=3,
        lid="opentrons_tough_universal_lid",
        lid_namespace="opentrons",
        lid_version=1,
    )

    # Load Pipette:
    pipette_right = protocol.load_instrument(
        "flex_1channel_1000", 
        "right", 
        tip_racks=[tip_rack_200]
    )

    # Load Trash Bins:
    trash_bin_1 = protocol.load_trash_bin("A3")

    # Define liquids
    liquid_sky_blue = protocol.define_liquid(
        "Sky Blue",
        display_color="#87CEEB",
    )
    liquid_sunset_yellow = protocol.define_liquid(
        "Sunset Yellow",
        display_color="#FDB813",
    )
    liquid_pink = protocol.define_liquid(
        "Pink",
        display_color="#FF69B4",
    )
    liquid_water = protocol.define_liquid(
        "Water",
        display_color="#0000ff",
    )

    # Load liquids into reservoirs
    reservoir_sky_blue["A1"].load_liquid(liquid_sky_blue, volume=195000)
    reservoir_sunset_yellow["A1"].load_liquid(liquid_sunset_yellow, volume=195000)
    reservoir_pink["A1"].load_liquid(liquid_pink, volume=195000)
    reservoir_water["A1"].load_liquid(liquid_water, volume=195000)

    # PROTOCOL STEPS

    # Step 1: Move lid
    protocol.move_lid(well_plate_1, "C3", use_gripper=True)

    # Step 2: Heater-Shaker - Open latch
    heater_shaker_module_1.deactivate_heater()
    heater_shaker_module_1.open_labware_latch()

    # Step 3: Move plate to heater-shaker
    protocol.move_labware(well_plate_1, adapter_1, use_gripper=True)

    # Step 4: Heater-Shaker - Close latch
    heater_shaker_module_1.close_labware_latch()
    heater_shaker_module_1.deactivate_heater()

    # Step 5: Dilution series with blow out to prevent residue
    total_volume = 200  # µL
    percentages = [12.5, 25, 37.5, 50, 62.5, 75, 87.5, 100]
    
    # Column assignments - 3 replicates per color across 9 columns
    # Sky Blue:      columns 1, 4, 7  (indices 0, 3, 6)
    # Sunset Yellow: columns 2, 5, 8  (indices 1, 4, 7)
    # Pink:          columns 3, 6, 9  (indices 2, 5, 8)
    sky_blue_columns = [well_plate_1.columns()[i] for i in [0, 3, 6]]
    sunset_yellow_columns = [well_plate_1.columns()[i] for i in [1, 4, 7]]
    pink_columns = [well_plate_1.columns()[i] for i in [2, 5, 8]]

    # Flatten all columns into single lists
    sky_blue_wells = [well for column in sky_blue_columns for well in column]
    sunset_yellow_wells = [well for column in sunset_yellow_columns for well in column]
    pink_wells = [well for column in pink_columns for well in column]

    # All 72 wells that will receive liquids
    all_wells = sky_blue_wells + sunset_yellow_wells + pink_wells

    # Calculate water volumes for each well (same pattern repeated for all replicates)
    water_volumes = []
    for percentage in percentages:
        water_volume = total_volume - (percentage / 100 * total_volume)
        water_volumes.append(water_volume)

    # Repeat water volumes for all 9 columns (3 colors × 3 replicates)
    all_water_volumes = water_volumes * 9
    
    # Build color volumes (percentage * 3 replicates = 24 wells per color)
    color_volumes = [(p / 100) * total_volume for p in percentages * 3]

    # STEP 5A: Distribute water to all 96 wells (continuous pipetting)
    dispense_with_batching(
        protocol, pipette_right, reservoir_water["A1"],
        all_wells, all_water_volumes, "Water"
    )

    # STEP 5B: Add Sky Blue dye to columns 1, 5, 9 (continuous pipetting)
    dispense_with_batching(
        protocol, pipette_right, reservoir_sky_blue["A1"],
        sky_blue_wells, color_volumes, "Sky Blue"
    )

    # STEP 5C: Add Sunset Yellow dye to columns 2, 6, 10 (continuous pipetting)
    dispense_with_batching(
        protocol, pipette_right, reservoir_sunset_yellow["A1"],
        sunset_yellow_wells, color_volumes, "Sunset Yellow"
    )

    # STEP 5D: Add Pink dye to columns 3, 6, 9 (continuous pipetting)
    dispense_with_batching(
        protocol, pipette_right, reservoir_pink["A1"],
        pink_wells, color_volumes, "Pink"
    )

    protocol.comment(
        "Total tips used: 4 (1 for water + 1 each for Sky Blue, Sunset Yellow, Pink)"
    )
    protocol.comment("Total wells filled: 72 (3 colors × 3 replicates × 8 concentrations)")

    # Step 6: Heater-Shaker - Open latch
    heater_shaker_module_1.deactivate_heater()
    heater_shaker_module_1.open_labware_latch()

    # Step 7: Move lid back
    protocol.move_lid("C3", well_plate_1, use_gripper=True)

    # Step 8: Heater-Shaker - Close latch
    heater_shaker_module_1.close_labware_latch()
    heater_shaker_module_1.deactivate_heater()

    # Step 9: Shake the plate for mixing
    heater_shaker_module_1.close_labware_latch()
    heater_shaker_module_1.deactivate_heater()
    heater_shaker_module_1.set_and_wait_for_shake_speed(1000)
    protocol.delay(seconds=30)  # Shake for 30 seconds to mix all wells

    # Step 10: Heater-Shaker - Stop and open
    heater_shaker_module_1.deactivate_heater()
    heater_shaker_module_1.deactivate_shaker()
    heater_shaker_module_1.open_labware_latch()

    # Step 11: Initialize absorbance reader
    absorbance_reader_1.close_lid()
    absorbance_reader_1.initialize("multi", [450, 562, 600, 650])

    # Step 12: Open absorbance reader
    absorbance_reader_1.open_lid()

    # Step 13: Move lid for reading
    protocol.move_lid(well_plate_1, "D2", use_gripper=True)

    # Step 14: Move plate to absorbance reader
    protocol.move_labware(well_plate_1, absorbance_reader_1, use_gripper=True)

    # Step 15: Close lid
    absorbance_reader_1.close_lid()

    # Step 16: Read absorbance - Updated filename
    absorbance_reader_1.close_lid()
    absorbance_reader_1.read(export_filename="Colors_Baseline")

    # Step 17: Open lid
    absorbance_reader_1.open_lid()
