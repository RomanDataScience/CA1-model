# CA1 Model Repository

This repository contains a NetPyNE/NEURON implementation of a small CA1 circuit centered on:

- one pyramidal cell model (`PC2B`)
- one `OLM` interneuron model
- one `VIP` interneuron model (`BilashVIP`)
- three external drive populations represented as `VecStim` inputs: `SC`, `PP`, and `MS`

The code supports two main use cases:

1. Running the full microcircuit with fixed parameters.
2. Running a reduced VIP-only batch protocol and optimizing VIP-related parameters with Optuna.

The current codebase is organized around the `src/` directory, imported cell rules in `cells/`, NEURON mechanisms in `mechanisms/`, compiled mechanism artifacts in `arm64/`, and study/output folders at the repo root.

## Current Architecture

The execution flow for a normal network run is:

1. `src/config/*.py` defines base parameters and derived quantities.
2. `src/cfg.py` builds a global `netpyne.specs.SimConfig` and exposes `refresh_cfg()`.
3. `src/netParams.py` loads the cell JSON files, applies condition-dependent edits, and builds all populations, synapses, and connections.
4. `src/init.py` initializes NetPyNE, creates the network, runs the simulation, saves outputs, and produces default plots.

The execution flow for the Optuna workflow is:

1. `src/batch_vip_optuna.py` defines the search space and launches the study.
2. `src/init_vip_batch.py` runs two VIP-only phases for each trial: `ms_off` and `ms_on`.
3. `src/vip_batch_fitness.py` computes the objective from VIP spike counts per theta cycle.
4. `src/vip_batch_plots.py` saves a side-by-side trace figure for the two phases.
5. The search space currently includes VIP initial voltage via `vipBatchVInit`.
6. Artifacts are written under `batch_runs/<study-label>/`.

## Main Folders

- `src/`: simulation code, batch drivers, replay scripts, and plotting utilities.
- `src/config/`: modular configuration loaders used to populate `cfg`.
- `cells/`: NetPyNE cell-rule JSON files used by the current model.
- `mechanisms/`: editable `.mod` sources grouped by mechanism family or cell class.
- `arm64/`: compiled NEURON mechanism outputs for Apple Silicon.
- `singleCellSuite/`: one-cell ramp-protocol runners and morphology plotting helpers.
- `batch_runs/`: current root-level Optuna study output location.
- `output/`: default output directory for standard full-network runs.
- `src/batch_runs/`: legacy study-output location kept only for older artifacts.

Each of those folders now has its own `README.md` with local details.

## Common Workflows

Compile mechanisms after editing any `.mod` file:

```bash
nrnivmodl $(find mechanisms -name "*.mod" | sort)
```

Run the default full network:

```bash
python src/init.py
```

Launch the VIP Optuna search:

```bash
python src/batch_vip_optuna.py
```

Replay one Optuna trial in the full network:

```bash
python src/run_best_vip_trial.py --trial 74
```

Replay one trial across the four named network conditions:

```bash
python src/run_best_vip_conditions.py --trial 74
```

Replay one trial and also save soma currentscape plots:

```bash
python src/run_best_vip_conditions_currentscape.py --trial 74
```

Replay multiple selected trials listed in `batch_runs/BestTrials.txt`:

Create `batch_runs/BestTrials.txt` with one Optuna trial number per line, for example:

```text
469
463
415
```

Then run:

```bash
python src/run_best_vip_conditions_from_best_trials.py --study-label vip_optuna_theta_gate
```

This wrapper runs both:

- `src/run_best_vip_conditions.py`
- `src/run_best_vip_conditions_currentscape.py`

for each listed trial and writes the outputs under `output_best_batch/`.

Run a single-cell ramp protocol:

```bash
python singleCellSuite/run_pc2b.py
python singleCellSuite/run_bilash_vip.py
python singleCellSuite/run_olm_cell.py
python singleCellSuite/run_bilash_pyr.py
```

Render a cell morphology from JSON:

```bash
python singleCellSuite/plotGeometry.py PC2B
```

## Important Parameters

The most important parameters live in `src/config/` and are then combined in `src/config/derived.py`.

Key groups:

- simulation controls: `dt`, `duration`, `Transient`, `cvode_active`, `saveFolder`
- cell/model toggles: `applyControlPC2B`, `IcanGbarFactor`, `overrideIcanConcrelease`, `vipInputResistanceScale`
- theta drive: `thetaCycles`, `thetaInterBurstISI`, `thetaIntraBurstISI`, `thetaSpikesPerBurst`
- VIP batch protocol: `vipBatchNoMsCycles`, `vipBatchMsCycles`, `vipBatchTargetSpikesPerCycle`, `vipBatchVInit`
- external input wiring: `nVipScInputs`, `nVipPpInputs`, `nMSinputs`, `nMSweight`
- recurrent connectivity: `PYROLMweight`, `OLMPYRweight`, `VIPOLMweight`

When a script mutates config values at runtime, it typically calls `refresh_cfg()` to recompute derived fields such as:

- `duration`
- `thetaSpikeTimes`
- `thetaCycleWindows`
- effective AMPA/NMDA weights
- effective VIP batch initialization voltage used during VIP-only search phases
- `recordCells`
- default analysis requests
- `simLabel`

## Outputs

By default:

- standard full-network runs write to `output/`
- Optuna studies write to `batch_runs/<study-label>/`
- replay scripts default to `batch_runs/<study-label>/full_trial_<trial>/` or `output_best/`
- single-cell runners write to `singleCellSuite/results/`

Typical saved files include:

- `*_data.json`: NetPyNE simulation payload
- `*.png`: traces, rasters, spike histograms, or currentscape plots
- `*.run`, `*.sh`, `*.out`, `*.sgl`: batch-launch artifacts
- `*.optuna.journal.log`: Optuna journal storage

## Environment Notes

The code assumes a Python environment with at least:

- `neuron`
- `netpyne`
- `matplotlib`
- `optuna`

Optional extras:

- `currentscape` for `src/run_best_vip_conditions_currentscape.py`

The repository currently includes compiled `arm64/` artifacts, which are useful on Apple Silicon but should be treated as generated files. If the mechanisms change, re-run `nrnivmodl mechanisms`.

## Current Scope

This repo snapshot does not currently include a maintained `tests/` directory. The focus is on executable simulation workflows and saved study artifacts:

- full-network runs from `src/init.py`
- VIP batch optimization from `src/batch_vip_optuna.py`
- replay and analysis scripts under `src/`
- single-cell protocol utilities under `singleCellSuite/`

Some documentation still refers to external or historical assets such as compiled mechanisms and legacy output locations. The active runtime paths in this repo are the ones listed above and in the folder READMEs.
