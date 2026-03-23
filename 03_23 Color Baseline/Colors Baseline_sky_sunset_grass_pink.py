from opentrons import protocol_api

metadata = {
    "protocolName": "Colors Baseline - 4 Colors with 3 Replicates",
    "description": (
        "8-step dilution series for Sky Blue, Sunset Yellow, Grass Green, and Pink dyes "
        "with 3 replicates each (96 wells total)"
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
    
    # Reservoirs with liquids - 4 test colors + water
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
    reservoir_grass_green = protocol.load_labware(
        "nest_1_reservoir_195ml",
        location="C1",  # Grass Green
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
    liquid_grass_green = protocol.define_liquid(
        "Grass Green",
        display_color="#32CD32",
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
    reservoir_grass_green["A1"].load_liquid(liquid_grass_green, volume=195000)
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
    
    # Column assignments - 3 replicates per color across all 12 columns
    # Sky Blue:      columns 1, 5, 9  (indices 0, 4, 8)
    # Sunset Yellow: columns 2, 6, 10 (indices 1, 5, 9)
    # Grass Green:   columns 3, 7, 11 (indices 2, 6, 10)
    # Pink:          columns 4, 8, 12 (indices 3, 7, 11)
    sky_blue_columns = [well_plate_1.columns()[i] for i in [0, 4, 8]]
    sunset_yellow_columns = [well_plate_1.columns()[i] for i in [1, 5, 9]]
    grass_green_columns = [well_plate_1.columns()[i] for i in [2, 6, 10]]
    pink_columns = [well_plate_1.columns()[i] for i in [3, 7, 11]]
    
    # Flatten all columns into single lists
    sky_blue_wells = [well for column in sky_blue_columns for well in column]
    sunset_yellow_wells = [well for column in sunset_yellow_columns for well in column]
    grass_green_wells = [well for column in grass_green_columns for well in column]
    pink_wells = [well for column in pink_columns for well in column]
    
    # All 96 wells that will receive liquids
    all_wells = sky_blue_wells + sunset_yellow_wells + grass_green_wells + pink_wells
    
    # Calculate water volumes for each well (same pattern repeated for all replicates)
    water_volumes = []
    for percentage in percentages:
        water_volume = total_volume - (percentage / 100 * total_volume)
        water_volumes.append(water_volume)
    
    # Repeat water volumes for all 12 columns (4 colors × 3 replicates)
    all_water_volumes = water_volumes * 12
    
    # STEP 5A: Distribute water to all 96 wells with ONE tip
    protocol.comment("Adding water to all 96 wells with blow out (1 tip for 96 wells)")
    pipette_right.pick_up_tip()
    for well, water_vol in zip(all_wells, all_water_volumes):
        if water_vol > 0:
            pipette_right.aspirate(water_vol, reservoir_water["A1"])
            pipette_right.dispense(water_vol, well.top(-5))
            pipette_right.blow_out(well.top(-2))  # Blow out residue
    pipette_right.drop_tip()
    
    # STEP 5B: Add Sky Blue dye to columns 1, 5, 9 with ONE tip
    protocol.comment("Adding Sky Blue dye to columns 1, 5, 9 with blow out (1 tip for 24 wells)")
    pipette_right.pick_up_tip()
    for well_idx, percentage in enumerate(percentages * 3):  # 8 rows × 3 replicates = 24 wells
        color_volume = (percentage / 100) * total_volume
        well = sky_blue_wells[well_idx]
        pipette_right.aspirate(color_volume, reservoir_sky_blue["A1"])
        pipette_right.dispense(color_volume, well.top(-5))
        pipette_right.blow_out(well.top(-2))  # Blow out residue
    pipette_right.drop_tip()
    
    # STEP 5C: Add Sunset Yellow dye to columns 2, 6, 10 with ONE tip
    protocol.comment("Adding Sunset Yellow dye to columns 2, 6, 10 with blow out (1 tip for 24 wells)")
    pipette_right.pick_up_tip()
    for well_idx, percentage in enumerate(percentages * 3):  # 8 rows × 3 replicates = 24 wells
        color_volume = (percentage / 100) * total_volume
        well = sunset_yellow_wells[well_idx]
        pipette_right.aspirate(color_volume, reservoir_sunset_yellow["A1"])
        pipette_right.dispense(color_volume, well.top(-5))
        pipette_right.blow_out(well.top(-2))  # Blow out residue
    pipette_right.drop_tip()
    
    # STEP 5D: Add Grass Green dye to columns 3, 7, 11 with ONE tip
    protocol.comment("Adding Grass Green dye to columns 3, 7, 11 with blow out (1 tip for 24 wells)")
    pipette_right.pick_up_tip()
    for well_idx, percentage in enumerate(percentages * 3):  # 8 rows × 3 replicates = 24 wells
        color_volume = (percentage / 100) * total_volume
        well = grass_green_wells[well_idx]
        pipette_right.aspirate(color_volume, reservoir_grass_green["A1"])
        pipette_right.dispense(color_volume, well.top(-5))
        pipette_right.blow_out(well.top(-2))  # Blow out residue
    pipette_right.drop_tip()

    # STEP 5E: Add Pink dye to columns 4, 8, 12 with ONE tip
    protocol.comment("Adding Pink dye to columns 4, 8, 12 with blow out (1 tip for 24 wells)")
    pipette_right.pick_up_tip()
    for well_idx, percentage in enumerate(percentages * 3):  # 8 rows × 3 replicates = 24 wells
        color_volume = (percentage / 100) * total_volume
        well = pink_wells[well_idx]
        pipette_right.aspirate(color_volume, reservoir_pink["A1"])
        pipette_right.dispense(color_volume, well.top(-5))
        pipette_right.blow_out(well.top(-2))  # Blow out residue
    pipette_right.drop_tip()
    
    protocol.comment(
        "Total tips used: 5 (1 for water + 1 each for Sky Blue, Sunset Yellow, Grass Green, Pink)"
    )
    protocol.comment("Total wells filled: 96 (4 colors × 3 replicates × 8 concentrations)")
    protocol.comment("Blow out added after each dispense to prevent tip residue")

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
