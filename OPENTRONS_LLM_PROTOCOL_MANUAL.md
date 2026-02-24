# Opentrons + LLM Protocol Design Manual

Last updated: 2026-02-09 (US)

This is the reusable playbook to start every new protocol conversation.

## 1) Scope and intent

This manual is for designing Opentrons Flex/OT-2 protocols with LLM assistance (OpentronsAI or general LLMs).  
Primary goal: generate protocols faster without reducing safety, compatibility, or run reliability.

## 2) Canonical websites (start here every time)

### A. Official Opentrons docs (highest priority)

- Documentation home: https://docs.opentrons.com/
- Flex protocol development overview (includes OpentronsAI): https://docs.opentrons.com/flex/protocols/
- OpentronsAI docs: https://docs.opentrons.com/flex/protocols/opentrons-ai/
- Protocol Designer manual: https://docs.opentrons.com/protocol-designer/
- Protocol Designer requirements/overview: https://docs.opentrons.com/protocol-designer/about/
- Protocol Designer transfer steps: https://docs.opentrons.com/protocol-designer/steps/transfer/
- Protocol Designer module steps: https://docs.opentrons.com/protocol-designer/steps/module/
- Protocol Designer warnings/errors: https://docs.opentrons.com/protocol-designer/warnings-errors/
- Protocol Designer export behavior: https://docs.opentrons.com/protocol-designer/export-protocol/
- Protocol Designer modify existing protocol: https://docs.opentrons.com/protocol-designer/modify-protocol/
- Python API tutorial (includes simulation command): https://docs.opentrons.com/python-api/tutorial/
- Python API versioning: https://docs.opentrons.com/python-api/versioning/
- Python API labware: https://docs.opentrons.com/python-api/labware/
- Python API moving labware: https://docs.opentrons.com/python-api/moving-labware/
- Python API module setup: https://docs.opentrons.com/python-api/modules/setup/
- Python API concurrent module actions: https://docs.opentrons.com/python-api/modules/concurrent/
- Python API multiple modules of same type: https://docs.opentrons.com/python-api/modules/multiple-same-type/
- Python API liquid classes: https://docs.opentrons.com/python-api/liquid-classes/
- Python API complex command parameters: https://docs.opentrons.com/python-api/complex-commands/parameters/
- Python API runtime parameters: https://docs.opentrons.com/python-api/runtime-parameters/
- Python API command line: https://docs.opentrons.com/python-api/advanced-control/command-line/
- Python API execute/simulate reference: https://docs.opentrons.com/python-api/reference/execute-simulate/
- Flex labware definitions + custom labware guidance: https://docs.opentrons.com/flex/labware/definitions/
- Protocol Library docs page: https://docs.opentrons.com/flex/protocols/library/

### B. Official Opentrons ecosystem websites

- Opentrons main site (product updates, AI messaging): https://opentrons.com/
- Protocol Designer product page: https://opentrons.com/protocol-designer
- Protocol Library product page: https://opentrons.com/intro-to-protocol-library
- Protocol Library source repository: https://github.com/Opentrons/Protocols
- Labware Creator tool: https://labware.opentrons.com/

### C. LLM engineering references (for robust generation/evaluation)

- OpenAI Structured Outputs: https://platform.openai.com/docs/guides/structured-outputs/ui-generation
- OpenAI evaluation best practices: https://platform.openai.com/docs/guides/evaluation-best-practices
- OpenAI safety best practices: https://platform.openai.com/docs/guides/safety-best-practices

## 3) Key facts to keep current (high-impact)

- Protocol Designer now exports `.py` (not new `.json`) and requires current app compatibility.
- As of docs checked on 2026-02-09, latest robot software listed is `8.8.0`, with max API support:
  - Flex: `2.15` to `2.27`
  - OT-2: `2.0` to `2.27`
- On Flex, `requirements = {"robotType": "Flex", "apiLevel": "X.Y"}` is required.
- `apiLevel` must be specified in exactly one place (metadata or requirements), not both.
- `opentrons_simulate` is available from local Python module install (`pip install opentrons`) for offline simulation.
- `opentrons_execute` runs protocols on-robot CLI.
- OpentronsAI can make mistakes; protocol review is required before execution.

## 4) Standard workflow for each new protocol conversation

### Step 1: Intake spec (never skip)

Capture:

- Robot: Flex or OT-2
- Software/App version on robot
- Protocol path: Protocol Designer, Python API, or OpentronsAI
- Pipettes + mounts + channels
- Labware list with exact load names (or custom labware JSON availability)
- Labware purpose mapping (sample storage, reaction, mixing, reagent reservoir, readout plate, waste)
- Modules/fixtures/gripper usage
- Liquids and viscosities (water-like/volatile/viscous)
- Volumes, replicate count, sample count range
- Tip policy (always/once/per source/per destination/never)
- Contamination constraints and carryover tolerance
- Timing constraints (incubation, heating/shaking, throughput target)
- Required runtime parameters (sample count, dry-run switch, CSV cherrypick, etc.)

### Step 2: Choose build mode

- Use Protocol Designer when workflow fits supported step forms and visual timeline.
- Use Python API when logic, loops, branching, advanced module timing, or custom control is needed.
- Use OpentronsAI to draft/modify quickly, then validate as if handwritten.

### Step 3: Generate with schema-constrained output

Have LLM produce structured sections:

- `assumptions`
- `deck_layout`
- `labware_and_modules`
- `pipettes_and_tips`
- `liquid_strategy`
- `protocol_code`
- `risk_checks`
- `simulation_expectations`

Use strict JSON schema when possible (Structured Outputs), then render to Python.

### Step 4: Static review before simulation

Check:

- Valid `requirements` and `apiLevel`
- All labware/module load names valid for target robot
- Deck slot compatibility and module placement constraints
- Tip availability and tip strategy consistency
- No illegal well ratios for transfer/distribute/consolidate patterns
- Aspirate/dispense/mix depths are explicitly defined and conservative
- Lids/move steps/gripper requirements are respected

### Step 5: Simulate and inspect runlog

- Local simulation: `opentrons_simulate protocol.py`
- For on-robot CLI checks: `opentrons_execute /data/protocol.py` (robot terminal/SSH)
- Confirm aspirate/dispense order, tip pickup/drop cadence, module state sequencing, and absence of errors.

### Step 6: Dry run then wet run

- Dry run with safe substitute liquid/empty labware workflow as appropriate.
- Wet run only after simulation + dry run pass.

## 5) LLM prompt templates

### A. First-turn intake prompt (assistant to user)

Use this at the start of every new protocol:

```text
Provide:
1) Robot (Flex or OT-2) and software/app version
2) Pipettes and tip racks
3) Labware load names (or custom labware JSONs)
4) Modules/fixtures/gripper usage
5) Source->destination mapping and volumes
6) Liquid types (aqueous/volatile/viscous)
7) Tip policy and contamination constraints
8) Runtime-parameter needs (sample count, dry run, CSV, etc.)
9) Throughput/timing targets
10) Whether you want Protocol Designer output, Python API code, or both
```

### B. Generation prompt (for LLM protocol drafting)

```text
Generate an Opentrons protocol for [Flex/OT-2] using API [X.Y].
Return:
- assumptions
- exact deck layout
- exact load names
- complete Python code
- risk checks
- simulation checklist
Constraints:
- no invented load names
- include requirements block for Flex
- optimize tip usage under contamination constraints
- include comments only where behavior is non-obvious
```

### C. Self-critique prompt (before accepting output)

```text
Audit the protocol for:
1) API compatibility
2) deck/module collisions
3) tip depletion or unsafe reuse
4) liquid-handling risks (viscous/volatile handling)
5) module sequencing or blocking/concurrency mistakes
6) likely runtime errors in opentrons_simulate
Return only concrete issues and exact code edits.
```

## 6) Reliability checklist (must pass)

- Protocol has a single authoritative API version declaration.
- Target robot/software supports requested API level.
- Custom labware files are available/imported in the app if used.
- Protocol Designer warnings reviewed; errors resolved before export/run.
- Tip handling choice is intentional for contamination model.
- Pipetting depths are deliberate, with a minimum safe bottom clearance before first run.
- Liquid class usage is deliberate (Flex liquid classes from API 2.24+).
- For multiple same-type modules, account for USB port load order behavior.
- For concurrent module actions (API 2.27+), blocking vs non-blocking behavior is deliberate.
- Simulation output reviewed line-by-line for first execution.
- Dry run completed before biological/expensive reagents.

## 6A) Pipette depth safety rules (prevent over-insertion)

Default starting policy for new protocols:

- Set conservative clearances first, then optimize after dry-run success.
- Use `pipette.well_bottom_clearance.aspirate = 1.0` mm (or higher for fragile pellets/beads).
- Use `pipette.well_bottom_clearance.dispense = 2.0` mm (or higher to reduce splashing/contact).
- Avoid aspirating/dispensing exactly at `bottom(z=0)` unless explicitly validated.
- Never use negative values from bottom (for example `bottom(z=-1)`).

Preferred Python API patterns:

```python
# Conservative global clearances
pipette.well_bottom_clearance.aspirate = 1.0
pipette.well_bottom_clearance.dispense = 2.0

# Explicit per-step locations when needed
pipette.aspirate(50, source.bottom(z=1.5))
pipette.dispense(50, dest.bottom(z=2.0))
```

Protocol Designer guidance:

- In transfer settings, review aspirate/dispense position fields for every liquid move.
- Start with larger offsets from bottom for first runs, then reduce only when required by residual-volume recovery.
- Re-check depths after changing labware definitions, tube type, or total transfer volume.

Depth review before first wet run:

- Deepest planned insertion for each labware type is documented.
- No step uses bottom contact as a default.
- Low-volume tail steps (near empty source wells/tubes) have explicit, safe handling logic.
- Simulation plus dry run confirm no scraping/contact events.

## 6B) Labware choice by purpose (how usage differs)

Use this matrix to choose labware before writing code/steps.

| Purpose | Best-fit labware | Why it fits | Usage differences to enforce |
| --- | --- | --- | --- |
| High-throughput assays/screening | 96/384 well flat-bottom plates | Dense format, consistent geometry, easy plate-reader handoff | Prefer multichannel; set conservative dispense height to reduce splashing; watch evaporation on long runs |
| Maximum volume per well/sample staging | Deep-well plates | High per-well capacity for pooling/washes | Slower mixing often needed; track deeper aspiration safely; use explicit bottom clearances |
| Reagent distribution to many wells | Reservoirs (single-channel or multi-channel) | Large shared volume, fewer refill interruptions | Keep aspiration away from dead-volume floor; for viscous reagents use slower aspirate and higher dispense |
| Low-throughput standards/controls | Tube racks (1.5 mL, 2 mL, 15/50 mL) | Flexible per-tube handling and heterogeneous volumes | Usually single-channel only; conical bottoms need explicit low-volume strategy near end of tube |
| Thermal cycling/PCR prep | PCR plates/tubes compatible with thermocycler | Sealing + thermal uniformity | Use thermocycler-compatible labware only; avoid aggressive mixing in thin-walled wells |
| Temperature hold during prep | Aluminum block + tubes on Temperature Module | Stable cooling/heating for reagents/samples | Confirm adapter + labware stack is supported; recheck accessible heights for pipetting |
| Bead cleanup/separation | Mag-compatible plates/tubes on Magnetic Module | Reliable pellet capture with magnetic field | Use engage/disengage timing; avoid aspirating near pellet side; increase aspirate clearance after magnet engage |
| Heated shaking/incubation | Heater-Shaker compatible deep-well/plates | Controlled temp + agitation | Respect latch/open state; no pipetting while shaking; ensure labware is heater-shaker approved |
| Final destination for readout | Assay/readout plate format required by instrument | Downstream compatibility (reader/imager) | Prioritize transfer accuracy and consistent dispense location over speed |
| Consumable liquid handling quality | Tip racks (filter/non-filter, low-retention variants) | Aerosol protection or better viscous-liquid release | Filter tips for contamination-sensitive workflows; low-retention for sticky liquids |

Selection rules that change protocol behavior:

- Multichannel transfer requires SBS plate geometry; tube racks generally force single-channel logic.
- Conical wells/tubes need end-of-volume safeguards (higher aspirate Z, smaller final pulls, optional pre-wet).
- Flat-bottom plates are easier for repeatable depth control and uniform dispensing.
- Deep-well/reservoir workflows should include dead-volume planning so final transfers do not bottom out.
- Module workflows must use only labware definitions supported by that module and robot version.
- Use exact Opentrons load names (or validated custom labware) before coding any deck layout.

## 7) OpentronsAI-specific operating rules

- Treat OpentronsAI output as draft, not ground truth.
- Request explicit assumptions and missing requirements.
- Ask OpentronsAI to simulate, but still perform independent simulation review.
- If converting to Protocol Designer, verify no feature loss from unsupported API details.

## 8) Common failure patterns to catch early

- Wrong robot type in requirements.
- API level above robot-supported max.
- Inconsistent deck coordinate system (Flex coordinate slots vs OT-2 numeric slots).
- Invalid pipette-tip-labware combinations.
- Overly aggressive aspirate/dispense depth that causes tip collision or scraping.
- Distribute/consolidate contamination assumptions not matching `new_tip` behavior.
- Hidden behavior changes after importing/updating old Protocol Designer files.
- Unreviewed warnings accepted as "probably fine."

## 9) Practical defaults for new projects

- Default to newest API level supported by deployed robot software.
- Start with explicit runtime parameters for sample count and dry-run toggle.
- Use Opentrons-verified liquid classes on Flex for non-water liquids.
- Prefer clear, conservative tip policies first; optimize later after baseline success.
- Keep first working version simple; add concurrency and optimizations after validation.

## 10) Update cadence for this manual

Re-check at start of major work or monthly:

- Python API versioning page
- Protocol Designer export/compatibility pages
- OpentronsAI docs page
- Module capability pages
- LLM structured output/eval guidance pages

If any of the above changes, update this file before next protocol sprint.

## 11) Project reference style (informed by `mixture_protocol.py`)

For this project, `mixture_protocol.py` is a strong reference, not a strict template.
Future generated protocols can use different structure when it improves clarity, safety, or performance.

Preferred patterns to reuse when useful:

- Clear `metadata` with protocol intent, constraints, and authorship.
- Explicit `requirements` for Flex + chosen API level.
- Separate deterministic data-generation helper(s) from `run()`.
- Explicit labware/module loading with full identifiers (`namespace`, `version`) where applicable.
- Module workflow is step-labeled and operationally ordered (latch state, plate moves, read sequence).
- Gripper-based `move_lid()` and `move_labware()` used for plate transport.
- Liquids defined with `define_liquid()` and source wells preloaded with expected volumes.
- Dispensing grouped by reagent/color with simple, auditable loops.
- Tip policy is explicit and low-complexity (for this pattern: 1 tip per reagent across destination wells).
- Dispense near top (`well.top(...)`) to avoid deep insertion and reduce collision risk.
- Operational comments describe milestone steps and tip usage.
- End of protocol includes instrument readout action and export filename convention.

Flexible guardrails derived from this reference:

- Keep protocol flow linear and readable before adding optimizations.
- Prefer explicit constants (volumes, seed, wavelengths, shake speed, delay) over hidden magic values.
- Keep contamination model explicit in code comments and tip policy.
- Keep deck transitions explicit whenever a plate moves between modules/instruments.
- Deviate from the reference structure when the workflow demands it, but keep all safety checks.
