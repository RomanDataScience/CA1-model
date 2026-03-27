# `src_network/`

This folder contains the executable Python code for the expanded CA1 network variant.

## What Lives Here

- `cfg.py`: builds the global NetPyNE `SimConfig` object and exposes `refresh_cfg()`.
- `netParams.py`: loads cell rules, validates population depth bands, and defines the positioned populations, synapses, and connectivity.
- `init.py`: standard full-network entry point for the `src_network` configuration.
- `init_vip_batch.py`: reduced VIP-only two-phase batch protocol used by Optuna.
- `batch_vip_optuna.py`: defines the Optuna study and dispatch settings.
- `vip_batch_fitness.py`: objective function helpers for the VIP batch protocol.
- `vip_batch_plots.py`: plotting helpers for VIP batch traces.
- `run_best_vip_trial.py`: replays one Optuna trial in the full network.
- `run_best_vip_conditions.py`: replays one trial across four manually named network conditions.
- `run_best_vip_conditions_currentscape.py`: same as above, plus soma currentscape figures.
- `run_best_vip_conditions_from_best_trials.py`: replays each trial listed in `batch_runs/BestTrials.txt`.
- `PlotSynConn.py`: plots synaptic contact locations on cell morphologies.
- `config/`: modular config loaders for the expanded network.

## Execution Flow

For the full network:

1. Import `cfg` from `cfg.py`.
2. `refresh_cfg()` computes all derived timing, weights, labels, and recording settings.
3. `src_network/config/cells.py` expands the resident CA1 populations to 10 cells each and defines the network dimensions and population depth bands.
4. `netParams.py` imports the JSON cell rules from `cells/`, validates `cfg.popYNormRanges`, sets a cuboid network geometry, and builds positioned populations.
5. Condition modifiers are applied:
   - `apply_pc2b_condition_mods()` adjusts `PC2B` control and ICAN-related parameters.
   - `apply_vip_condition_mods()` adjusts VIP leak conductances to realize a target input resistance scale.
6. NetPyNE builds the network and runs the simulation.

For the VIP batch/Optuna workflow:

1. `batch_vip_optuna.py` defines the search space.
2. Each trial runs `src_network/init_vip_batch.py`.
3. The batch runner executes `ms_off` and `ms_on` phases separately.
4. The search space currently includes `vipBatchVInit`, which controls the initial membrane voltage used in the VIP-only batch simulation.
5. The objective is computed from spike counts inside and outside the theta windows.
6. The combined loss is sent back through `sim.send()`.

## Important Runtime Conventions

- The repo root is discovered from `Path(__file__).resolve().parents[1]`.
- Full-network default outputs go to `output/`.
- Optuna study outputs go to `batch_runs/<study-label>/` at the repo root.
- `src_network/config/sim.py` sets `cfg.simLabelBase = "CA1_10"` so outputs are labeled as the 10-cell-per-population network.
- Resident `PC2B`, `OLM`, and `VIP` populations are 10-cell ensembles instead of single representative cells.
- `src_network/netParams.py` assigns `ynormRange` values to each population and uses a cuboid geometry (`sizeX`, `sizeY`, `sizeZ`) to preserve laminar placement.
- Replay scripts reapply trial-specific `vipBatchVInit` to `hParams["v_init"]` so full-network reruns stay consistent with the batch search.
- Several scripts set `MPLBACKEND=Agg` and `NEURON_MODULE_OPTIONS=-nogui` to run headless.

## Typical Commands

Run a full simulation:

```bash
python3 src_network/init.py
```

Run the Optuna search:

```bash
python3 src_network/batch_vip_optuna.py
```

Replay a chosen trial:

```bash
python3 src_network/run_best_vip_trial.py --trial 74
```

Replay one trial across the four named network conditions:

```bash
python3 src_network/run_best_vip_conditions.py --trial 74
```

Replay one trial and also save soma currentscape plots:

```bash
python3 src_network/run_best_vip_conditions_currentscape.py --trial 74
```

Replay multiple selected trials listed in `batch_runs/BestTrials.txt`:

```bash
python3 src_network/run_best_vip_conditions_from_best_trials.py --study-label vip_optuna_theta_gate
```

Make synaptic contact plots:

```bash
python3 src_network/PlotSynConn.py
```

## Notes For Developers

- `cfg` is a mutable global object reused by many scripts.
- After changing any base parameter programmatically, including `cellsPerType`, `popYNormRanges`, or other population-layout settings, call `refresh_cfg()` before building `netParams`.
- `netParams.py` is executed at import time; configuration should be in its final state before importing it.
- The batch replay scripts dynamically reload `netParams` so that edited config values take effect.
