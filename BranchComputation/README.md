# BranchComputation

This folder contains a dedicated PC2B branch-computation sweep that keeps the existing `src_reformated` theta stimulation protocol but removes OLM and VIP from the simulation. It is aimed at the single-cell question: how does up-state duration change as more PP and SC branches are co-activated?

## Design choices

- The runner now uses [cells/PC2B_new.json](/Users/romanbaravalle/Documents/Consultancy/GaspariniCanavier_CA1Grant_2026/CA1-model/cells/PC2B_new.json) by default. In this cell, dendritic `ICAN` is limited to `trunk_0` through `trunk_7` rather than the full apical tree.
- The SC and PP target zones come directly from the current theta protocol in `src_reformated/config/derived.py`.
- The default batch is now `N x intensity`, where `N` sweeps every 3 connections starting at `1` and appends the protocol maximum if needed.
- In each `N`, the script samples `N` SC theta sites and `N` PP theta sites without replacement from the already-targeted theta site lists.
- Input intensity is controlled by scaling the baseline PC2B theta synaptic factor `cfg.factorSynPYR`.
- The default intensity sweep now uses 5 values from `0.25` to `1.5`.
- This batch overrides the solver settings to `dt = 1e-2`, `recordStep = 1e-2`, and `cvode_atol = 1e-6`.
- Every run saves compressed dendritic `ICAN` traces in `traces.npz`, a `run_summary.json`, and four figures in `plots/`.
- A batch-level `batch_summary.csv` and `batch_summary.json` are written at the end with first-pass up-state and post hoc activated-`ICAN` section metrics.
- If you want the older wide-apical `ICAN` distribution again, pass `--cell-file cells/PC2B.json`.

## Per-run plots

Each parameter combination now generates:

- `plots/morphology_inputs.png`: the PC2B morphology with the sampled SC and PP sites marked at their actual section/`loc` positions.
- `plots/soma_voltage.png`: `V_soma` over time, with theta spike times, somatic spikes, baseline, threshold, and the detected main up-state window.
- `plots/summed_dendritic_ican.png`: summed inward dendritic `ICAN` over time.
- `plots/dendritic_ican_heatmap.png`: section-by-section inward `ICAN` heatmap.
- `plots/summary_panel.png`: a 2x2 panel combining the time-series plots plus a text summary of the active SC/PP sites and run metrics.

All run-level plots now start `200 ms` before the first theta spike time and extend to the end of the simulation.
The morphology plot uses the `xz` projection by default; override it with `--morphology-projection xy|xz|yz`.

## How target sections and locations vary

The script now samples individual theta-site connections, not whole sections. That means the configured sweep variable `N` is exactly the number of SC connections and the number of PP connections active in that run.

- SC theta sites come from `src_reformated/config/derived.py`.
- SC has these built-in site patterns:
  `trunk_10` to `trunk_15` at `loc=0.5`
  `apic_27` to `apic_32` at `loc=0.5`
  `apic_28` to `apic_31` also at `loc=0.2` and `loc=0.8`
- PP theta sites come from `apic_40` to `apic_59`, all at `loc=0.8`.

For each run:

- `N` SC theta sites are drawn at random without replacement from the 20 SC sites already defined by the protocol.
- `N` PP theta sites are drawn at random without replacement from the 20 PP sites already defined by the protocol.
- By default, `N` takes values like `1, 4, 7, 10, ...` and includes the maximum available connection count as the final point.

The random draws are reproducible through `--random-seed`, and the exact sampled sites for every `N` are stored in `batch_config.json`.

Important detail for SC:

- Because the sampling unit is the site, SC `loc` values are drawn directly from the existing SC site list:
  `trunk_10` to `trunk_15` at `loc=0.5`
  `apic_27` to `apic_32` at `loc=0.5`
  `apic_28` to `apic_31` also at `loc=0.2` and `loc=0.8`
- PP draws come from `apic_40` to `apic_59`, all at `loc=0.8`.

So:

- Every run has exactly `N` SC connections and exactly `N` PP connections.
- The exact target sections and SC `loc` values differ from run to run.
- The number of unique sections is not fixed, because multiple selected SC sites can land on the same section at different `loc` values.

The exact active sites for each run are written into `run_summary.json` under `active_sc_sites`, `active_pp_sites`, `active_sc_sites_grouped`, and `active_pp_sites_grouped`.

## Default run

```bash
python BranchComputation/run_branch_computation_batch.py
```

Outputs go to `BranchComputation/output/`.

## Smaller test run

```bash
python BranchComputation/run_branch_computation_batch.py \
  --connection-counts 1 2 3 \
  --intensity-scales 1.0 1.5
```

## Notes on the metrics

- `up_state.duration_ms` is a first-pass somatic proxy based on smoothed `V_soma` crossing a baseline-relative threshold after theta begins.
- `dendritic_ican.duration_ms` is based on the summed inward dendritic `ICAN` staying above a configurable fraction of its peak.
- `activated_ican.section_count` is a post hoc proxy for the number of activated dendritic branches, defined here from per-section inward `ICAN` peaks.
- These metrics are meant to accelerate screening. If you need a stricter dendritic plateau definition later, the raw per-section `ICAN` traces are already stored for re-analysis.
