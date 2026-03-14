import argparse
import copy
import json
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("NEURON_MODULE_OPTIONS", "-nogui")

_mpl_config_dir = Path(os.environ.get("TMPDIR", "/tmp")) / "matplotlib-src_reformated"
_mpl_config_dir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_mpl_config_dir))

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from currentscape import plot as plot_currentscape
except ImportError as exc:
    raise ImportError(
        "currentscape is required to run this script. Use an environment where it is installed."
    ) from exc

from run_best_vip_trial import (
    DEFAULT_STUDY_LABEL,
    DEFAULT_TRIAL_NUMBER,
    REPO_ROOT,
    _apply_trial_params,
    _bootstrap_simulation_imports,
    _get_trial,
    _load_netparams_module,
    _load_study,
    _resolve_batch_dir,
    _trial_value_payload,
)


CONDITIONS = [
    {
        "name": "03_baseline_pc2b_olm_loop_only",
        "applyControlPC2B": False,
        "PYROLMweight": 4e-3,
        "OLMPYRweight": 5e-3,
        "VIPOLMweight": 0.0,
        "nMSweight": 0.0,
    },
    {
        "name": "04_baseline_pc2b_full_loop",
        "applyControlPC2B": False,
        "PYROLMweight": 3e-3,
        "OLMPYRweight": 5e-3,
        "VIPOLMweight": 1e-2,
        "nMSweight": "trial",
    },
    {
        "name": "01_control_pc2b_no_recurrent_inh",
        "applyControlPC2B": True,
        "PYROLMweight": 0.0,
        "OLMPYRweight": 0.0,
        "VIPOLMweight": 0.0,
        "nMSweight": 0.0,
    },
    {
        "name": "02_baseline_pc2b_no_recurrent_inh",
        "applyControlPC2B": False,
        "PYROLMweight": 0.0,
        "OLMPYRweight": 0.0,
        "VIPOLMweight": 0.0,
        "nMSweight": 0.0,
    },
]


CURRENTSCAPE_CURRENT_SPECS = {
    "PC2B": [
        {"label": "na16a", "mech": "na16a", "var": "ina"},
        {"label": "nap", "mech": "nap", "var": "ina"},
        {"label": "cal", "mech": "cal", "var": "ica"},
        {"label": "cal4", "mech": "cal4", "var": "ica"},
        {"label": "car", "mech": "car", "var": "ica"},
        {"label": "cat", "mech": "cat", "var": "ica"},
        {"label": "Kv2like", "mech": "Kv2like", "var": "ik"},
        {"label": "kap", "mech": "kap", "var": "ik"},
        {"label": "kd", "mech": "kd", "var": "ik"},
        {"label": "km", "mech": "km", "var": "ik"},
        {"label": "kca", "mech": "kca", "var": "ik"},
        {"label": "mykca", "mech": "mykca", "var": "ik"},
        {"label": "h", "mech": "h", "var": "i"},
        {"label": "ican", "mech": "ican", "var": "itrpm4"},
        {"label": "pas", "mech": "pas", "var": "i"},
    ],
    "OLM": [
        {"label": "Nasoma", "mech": "Nasoma", "var": "ina"},
        {"label": "Ih_OLM", "mech": "Ih_OLM", "var": "ih"},
        {"label": "Ika", "mech": "Ika", "var": "ik"},
        {"label": "Ikdrf", "mech": "Ikdrf", "var": "ik"},
        {"label": "Ikdrs", "mech": "Ikdrs", "var": "ik"},
        {"label": "IM", "mech": "IM", "var": "ik"},
        {"label": "passsd", "mech": "passsd", "var": "i"},
    ],
    "VIP": [
        {"label": "Nafcr", "mech": "Nafcr", "var": "ina"},
        {"label": "cancr", "mech": "cancr", "var": "ica"},
        {"label": "Ih_VIP", "mech": "Ih_VIP", "var": "ih"},
        {"label": "IKscr", "mech": "IKscr", "var": "ik"},
        {"label": "kdrcr", "mech": "kdrcr", "var": "ik"},
        {"label": "iCcr", "mech": "iCcr", "var": "ik"},
        {"label": "gskch", "mech": "gskch", "var": "ik"},
        {"label": "pas", "mech": "pas", "var": "i"},
    ],
}
CURRENTSCAPE_MAX_CURRENTS = 8


def _parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run four full-network conditions using VIP parameters from one "
            "Optuna trial and save them under the repo-root output_best folder."
        )
    )
    parser.add_argument(
        "--study-label",
        default=DEFAULT_STUDY_LABEL,
        help="Optuna study label under src_reformated/batch_runs.",
    )
    parser.add_argument(
        "--batch-dir",
        default=None,
        help="Override the study output folder. Defaults to src_reformated/batch_runs/<study-label>.",
    )
    parser.add_argument(
        "--trial",
        type=int,
        default=DEFAULT_TRIAL_NUMBER,
        help="Trial number whose VIP parameters should be applied.",
    )
    parser.add_argument(
        "--output-dir",
        default=str((REPO_ROOT / "output_best").resolve()),
        help="Repo-root output folder for all four reruns.",
    )
    return parser.parse_args()


def _trace_key_sort_key(key):
    suffix = str(key).split("_")[-1]
    if suffix.isdigit():
        return (0, int(suffix))
    return (1, str(key))


def _currentscape_voltage_trace_name(pop_name):
    return f"V_soma_{pop_name}_currentscape"


def _currentscape_current_trace_name(pop_name, current_label):
    return f"I_soma_{pop_name}_{current_label}"


def _augment_record_traces_for_currentscape(sim_cfg):
    augmented_record_traces = copy.deepcopy(getattr(sim_cfg, "recordTraces", {}))
    for pop_name, current_specs in CURRENTSCAPE_CURRENT_SPECS.items():
        augmented_record_traces[_currentscape_voltage_trace_name(pop_name)] = {
            "sec": "soma",
            "loc": 0.5,
            "var": "v",
            "conds": {"pop": pop_name},
        }
        for current_spec in current_specs:
            augmented_record_traces[_currentscape_current_trace_name(pop_name, current_spec["label"])] = {
                "sec": "soma",
                "loc": 0.5,
                "mech": current_spec["mech"],
                "var": current_spec["var"],
                "conds": {"pop": pop_name},
            }
    sim_cfg.recordTraces = augmented_record_traces


def _extract_first_trace(trace_store):
    if trace_store is None:
        return None
    if isinstance(trace_store, dict):
        if not trace_store:
            return None
        first_key = sorted(trace_store, key=_trace_key_sort_key)[0]
        trace_store = trace_store[first_key]
    trace_array = np.asarray(trace_store, dtype=float)
    if trace_array.size == 0:
        return None
    return trace_array


def _align_currentscape_data(time, voltage, currents):
    lengths = [len(time), len(voltage)] + [len(current) for current in currents]
    if not lengths:
        return None
    common_length = min(lengths)
    if common_length == 0:
        return None
    return (
        np.asarray(time[:common_length], dtype=float),
        np.asarray(voltage[:common_length], dtype=float),
        [np.asarray(current[:common_length], dtype=float) for current in currents],
    )


def _save_soma_currentscape_figure(condition_name, sim_label, sim_data, output_dir, pop_name):
    time = np.asarray(sim_data.get("t", []), dtype=float)
    voltage = _extract_first_trace(sim_data.get(_currentscape_voltage_trace_name(pop_name)))
    if time.size == 0 or voltage is None:
        return None

    available_currents = []
    for current_spec in CURRENTSCAPE_CURRENT_SPECS[pop_name]:
        trace_name = _currentscape_current_trace_name(pop_name, current_spec["label"])
        current_trace = _extract_first_trace(sim_data.get(trace_name))
        if current_trace is None:
            continue
        available_currents.append(
            {
                "label": current_spec["label"],
                "trace": current_trace,
                "mean_abs_current": float(np.mean(np.abs(current_trace))),
            }
        )

    if not available_currents:
        return None

    available_currents.sort(key=lambda current: current["mean_abs_current"], reverse=True)
    selected_currents = available_currents[:CURRENTSCAPE_MAX_CURRENTS]
    current_names = [current["label"] for current in selected_currents]
    current_traces = [current["trace"] for current in selected_currents]

    aligned = _align_currentscape_data(time, voltage, current_traces)
    if aligned is None:
        return None

    aligned_time, aligned_voltage, aligned_currents = aligned
    output_name = f"{sim_label}_{pop_name}_soma_currentscape"
    config = {
        "title": f"{condition_name} | {pop_name} soma currents",
        "figsize": (7.5, 9.0),
        "lw": 0.8,
        "show": {
            "legend": True,
            "all_currents": True,
            "xlabels": True,
            "xticklabels": True,
        },
        "current": {
            "names": current_names,
            "units": "[mA/cm2]",
            "reorder": False,
        },
        "colormap": {
            "name": "tab10",
            "n_colors": 10,
        },
        "voltage": {
            "units": "[mV]",
        },
        "xaxis": {
            "units": "[ms]",
        },
        "legend": {
            "textsize": 7,
        },
        "adjust": {
            "left": 0.14,
            "right": 0.82,
            "top": 0.95,
            "bottom": 0.08,
        },
        "output": {
            "savefig": True,
            "dir": str(output_dir),
            "fname": output_name,
            "extension": "png",
            "dpi": 200,
            "transparent": False,
        },
    }

    figure = plot_currentscape(
        voltage_data=aligned_voltage,
        currents_data=np.vstack(aligned_currents),
        config=config,
        time=aligned_time,
    )
    plt.close(figure)

    output_path = output_dir / f"{output_name}.png"
    return str(output_path) if output_path.exists() else None


def _save_all_soma_currentscape_figures(condition_name, sim_label, sim_data, output_dir):
    plot_paths = {}
    for pop_name in CURRENTSCAPE_CURRENT_SPECS:
        plot_path = _save_soma_currentscape_figure(
            condition_name=condition_name,
            sim_label=sim_label,
            sim_data=sim_data,
            output_dir=output_dir,
            pop_name=pop_name,
        )
        if plot_path is not None:
            plot_paths[pop_name] = plot_path
    return plot_paths


def _save_combined_v_soma_figure(sim_cfg, sim_data, output_path):
    time = sim_data.get("t", [])
    voltage_traces = sim_data.get("V_soma", {})
    if len(time) == 0 or not voltage_traces:
        return None

    record_labels = []
    for entry in getattr(sim_cfg, "recordCells", []):
        if isinstance(entry, (list, tuple)) and len(entry) == 2:
            record_labels.append(f"{entry[0]}[{entry[1]}]")
        else:
            record_labels.append(str(entry))

    trace_keys = sorted(
        voltage_traces,
        key=_trace_key_sort_key,
    )
    colors = ["#1f77b4", "#d62728", "#2ca02c"]

    fig, axis = plt.subplots(figsize=(12, 5))
    for index, trace_key in enumerate(trace_keys):
        label = record_labels[index] if index < len(record_labels) else trace_key
        axis.plot(
            time,
            voltage_traces[trace_key],
            linewidth=1.0,
            color=colors[index % len(colors)],
            label=label,
        )

    axis.set_xlabel("Time (ms)")
    axis.set_ylabel("V_soma (mV)")
    axis.set_title("PC2B, OLM, and VIP on the same axis")
    axis.legend(loc="best")
    axis.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    return str(output_path)


def _run_condition(sim_module, sim_cfg, refresh_cfg_fn, trial, trial_params, base_output_dir, condition):
    _apply_trial_params(sim_cfg, trial_params)
    sim_cfg._batchtk_label_pointer = None
    sim_cfg._batchtk_path_pointer = None
    sim_cfg.vipBatchProtocol = False
    sim_cfg.enableDefaultAnalysis = True
    sim_cfg.applyControlPC2B = condition["applyControlPC2B"]
    sim_cfg.PYROLMweight = condition["PYROLMweight"]
    sim_cfg.OLMPYRweight = condition["OLMPYRweight"]
    sim_cfg.VIPOLMweight = condition["VIPOLMweight"]
    if condition["nMSweight"] != "trial":
        sim_cfg.nMSweight = condition["nMSweight"]

    condition_dir = base_output_dir / condition["name"]
    condition_dir.mkdir(parents=True, exist_ok=True)

    sim_cfg.saveFolder = str(condition_dir)
    refresh_cfg_fn(sim_cfg)
    sim_cfg.saveFolder = str(condition_dir)
    sim_cfg.simLabel = f"trial_{trial.number}_{condition['name']}_{sim_cfg.simLabel}"
    original_record_traces = copy.deepcopy(getattr(sim_cfg, "recordTraces", {}))
    _augment_record_traces_for_currentscape(sim_cfg)

    combined_trace_path = None
    currentscape_paths = {}
    try:
        if hasattr(sim_module, "net"):
            sim_module.clearAll()

        netparams_module = _load_netparams_module()
        full_netparams = netparams_module.netParams

        sim_cfg.saveFolder = str(condition_dir)
        sim_module.initialize(simConfig=sim_cfg, netParams=full_netparams)
        sim_module.net.createPops()
        sim_module.net.createCells()
        sim_module.net.connectCells()
        sim_module.net.addStims()
        sim_module.setupRecording()
        sim_module.runSim()
        sim_module.gatherData()
        sim_data = sim_module.allSimData if hasattr(sim_module, "allSimData") else sim_module.simData
        combined_trace_path = _save_combined_v_soma_figure(
            sim_cfg=sim_cfg,
            sim_data=sim_data,
            output_path=condition_dir / f"{sim_cfg.simLabel}_traces_overlay.png",
        )
        currentscape_paths = _save_all_soma_currentscape_figures(
            condition_name=condition["name"],
            sim_label=sim_cfg.simLabel,
            sim_data=sim_data,
            output_dir=condition_dir,
        )
        sim_module.saveData()
    finally:
        sim_cfg.recordTraces = original_record_traces
        if hasattr(sim_module, "cfg"):
            sim_module.cfg.recordTraces = original_record_traces
    sim_module.analysis.plotData()

    data_json_path = condition_dir / f"{sim_cfg.simLabel}_data.json"
    result = {
        "condition": condition["name"],
        "applyControlPC2B": sim_cfg.applyControlPC2B,
        "PYROLMweight": sim_cfg.PYROLMweight,
        "OLMPYRweight": sim_cfg.OLMPYRweight,
        "VIPOLMweight": sim_cfg.VIPOLMweight,
        "nMSweight": sim_cfg.nMSweight,
        "output_dir": str(condition_dir),
        "sim_label": sim_cfg.simLabel,
        "data_json": str(data_json_path) if data_json_path.exists() else None,
        "combined_v_soma_plot": combined_trace_path,
        "currentscape_plots": currentscape_paths,
    }

    if hasattr(sim_module, "net"):
        sim_module.clearAll()

    return result


def main():
    args = _parse_args()

    batch_dir = _resolve_batch_dir(args.study_label, args.batch_dir)
    study, journal_path = _load_study(batch_dir, args.study_label)
    trial = _get_trial(study, args.trial)
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    sim_module, sim_cfg, refresh_cfg_fn = _bootstrap_simulation_imports()

    run_results = []
    for condition in CONDITIONS:
        print(f"Running {condition['name']}...")
        run_results.append(
            _run_condition(
                sim_module=sim_module,
                sim_cfg=sim_cfg,
                refresh_cfg_fn=refresh_cfg_fn,
                trial=trial,
                trial_params=trial.params,
                base_output_dir=output_dir,
                condition=condition,
            )
        )

    summary = {
        "study_label": args.study_label,
        "study_name": study.study_name,
        "journal_path": str(journal_path),
        "trial_number": trial.number,
        "trial_state": trial.state.name,
        "trial_value": _trial_value_payload(trial),
        "trial_params": dict(trial.params),
        "output_dir": str(output_dir),
        "conditions": run_results,
    }

    summary_path = output_dir / f"trial_{trial.number}_output_best_summary.json"
    with summary_path.open("w", encoding="utf-8") as summary_file:
        json.dump(summary, summary_file, indent=2, sort_keys=True)

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
