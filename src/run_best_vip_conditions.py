import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt

from run_best_vip_trial import (
    DEFAULT_STUDY_LABEL,
    DEFAULT_TRIAL_NUMBER,
    REPO_ROOT,
    _apply_trial_params,
    _apply_trial_v_init,
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
        help="Optuna study label under batch_runs at the repo root.",
    )
    parser.add_argument(
        "--batch-dir",
        default=None,
        help="Override the study output folder. Defaults to <repo>/batch_runs/<study-label>.",
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
        key=lambda key: int(key.split("_")[-1]) if "_" in key and key.split("_")[-1].isdigit() else key,
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
    _apply_trial_v_init(sim_cfg)
    sim_cfg.saveFolder = str(condition_dir)
    sim_cfg.simLabel = f"trial_{trial.number}_{condition['name']}_{sim_cfg.simLabel}"

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
    combined_trace_path = _save_combined_v_soma_figure(
        sim_cfg=sim_cfg,
        sim_data=sim_module.allSimData if hasattr(sim_module, "allSimData") else sim_module.simData,
        output_path=condition_dir / f"{sim_cfg.simLabel}_traces_overlay.png",
    )
    sim_module.saveData()
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
