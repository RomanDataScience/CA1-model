import argparse
import importlib
import json
import os
import sys
from collections.abc import MutableMapping
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("NEURON_MODULE_OPTIONS", "-nogui")
mpl_config_dir = Path(os.environ.get("TMPDIR", "/tmp")) / "matplotlib-cache"
mpl_config_dir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(mpl_config_dir))

import matplotlib

matplotlib.use("Agg")

import optuna

try:
    from optuna.storages.journal import JournalFileBackend

    def _build_journal_storage(journal_path):
        return optuna.storages.JournalStorage(JournalFileBackend(str(journal_path)))

except ImportError:
    from optuna.storages import JournalStorage, JournalFileStorage

    def _build_journal_storage(journal_path):
        return JournalStorage(JournalFileStorage(str(journal_path)))

from vip_batch_plots import extract_recorded_trace, save_combined_vip_trace_figure

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STUDY_LABEL = "vip_optuna_theta_gate_v3"
DEFAULT_BATCH_DIR = REPO_ROOT / "src_reformated" / "batch_runs" / DEFAULT_STUDY_LABEL
sim = None
cfg = None
refresh_cfg = None
summarize_vip_theta_response = None


def parse_args():
    parser = argparse.ArgumentParser(description="Rerun and plot the best VIP Optuna trial.")
    parser.add_argument(
        "--study-label",
        default=DEFAULT_STUDY_LABEL,
        help="Optuna study label used in batch_vip_optuna.py.",
    )
    parser.add_argument(
        "--batch-dir",
        default=str(DEFAULT_BATCH_DIR),
        help="Directory containing the Optuna journal and trial outputs.",
    )
    parser.add_argument(
        "--trial",
        type=int,
        default=None,
        help="Specific Optuna trial number to rerun. Defaults to the best trial.",
    )
    parser.add_argument(
        "--phase",
        choices=("both", "ms_off", "ms_on"),
        default="both",
        help="Which phase to rerun.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to save rerun data and figures. Defaults to batch_dir/best_trial_<n>.",
    )
    return parser.parse_args()


def _bootstrap_simulation_imports():
    global sim, cfg, refresh_cfg, summarize_vip_theta_response
    if sim is not None:
        return

    from netpyne import sim as netpyne_sim
    from cfg import cfg as sim_cfg, refresh_cfg as refresh_cfg_fn
    from vip_batch_fitness import summarize_vip_theta_response as summarize_fn

    sim = netpyne_sim
    cfg = sim_cfg
    refresh_cfg = refresh_cfg_fn
    summarize_vip_theta_response = summarize_fn


def _load_study(batch_dir, study_label):
    journal_path = batch_dir / f"{study_label}_optuna.optuna.journal.log"
    if not journal_path.exists():
        raise FileNotFoundError(f"Optuna journal not found: {journal_path}")
    storage = _build_journal_storage(journal_path)
    study_name = f"{study_label}_optuna"
    study = optuna.load_study(study_name=study_name, storage=storage)
    return study, journal_path


def _get_trial(study, trial_number):
    if trial_number is None:
        return study.best_trial
    for trial in study.trials:
        if trial.number == trial_number:
            return trial
    raise ValueError(f"Trial {trial_number} was not found in study {study.study_name}.")


def _set_cfg_path(target_cfg, dotted_path, value):
    parts = dotted_path.split(".")
    current = target_cfg
    for part in parts[:-1]:
        if isinstance(current, MutableMapping):
            current = current[part]
        else:
            current = getattr(current, part)
    if isinstance(current, MutableMapping):
        current[parts[-1]] = value
    else:
        setattr(current, parts[-1], value)


def _apply_trial_params(params):
    for dotted_path, value in params.items():
        _set_cfg_path(cfg, dotted_path, value)


def _load_netparams_module():
    if "netParams" in sys.modules:
        return importlib.reload(sys.modules["netParams"])
    return importlib.import_module("netParams")


def _restrict_to_vip_only(phase_netparams):
    keep_pops = {"VIP", "SC", "PP", "MS"}
    keep_conn_prefixes = ("SC->VIP_", "PP->VIP_", "MS->VIP_")

    for pop_name in list(phase_netparams.popParams.keys()):
        if pop_name not in keep_pops:
            del phase_netparams.popParams[pop_name]

    for cell_name in list(phase_netparams.cellParams.keys()):
        if cell_name != "BilashVIP":
            del phase_netparams.cellParams[cell_name]

    for conn_name in list(phase_netparams.connParams.keys()):
        if not conn_name.startswith(keep_conn_prefixes):
            del phase_netparams.connParams[conn_name]

    for subconn_name in list(phase_netparams.subConnParams.keys()):
        del phase_netparams.subConnParams[subconn_name]

    return phase_netparams


def _configure_phase(output_dir, phase_name, ms_enabled):
    cfg.vipBatchProtocol = False
    cfg.enableDefaultAnalysis = False
    refresh_cfg(cfg)
    cfg.hParams["v_init"] = float(getattr(cfg, "vipBatchVInit", cfg.hParams["v_init"]))
    cfg.saveFolder = str(output_dir)
    cfg.recordCells = [("VIP", 0)]
    cfg.recordTraces = {
        "V_soma": {"sec": "soma", "loc": 0.5, "var": "v"},
        "I_nAch": {"synMech": "nACh_IS3", "var": "i", "conds": {"pop": "VIP"}},
    }


def _phase_summary(sim_data, ms_enabled):
    vip_gids = list(range(int(cfg.VIP)))
    if ms_enabled:
        return summarize_vip_theta_response(
            simData=sim_data,
            vip_gids=vip_gids,
            no_ms_windows=[],
            ms_windows=cfg.thetaCycleWindows,
            target_spikes_per_cycle=cfg.vipBatchTargetSpikesPerCycle,
        )
    return summarize_vip_theta_response(
        simData=sim_data,
        vip_gids=vip_gids,
        no_ms_windows=cfg.thetaCycleWindows,
        ms_windows=[],
        target_spikes_per_cycle=0,
        missing_vip_penalty=0.0,
    )


def _plot_phase(output_dir, phase_name):
    time_range = [0, cfg.duration]
    raster_path = output_dir / f"{phase_name}_raster.png"
    traces_path = output_dir / f"{phase_name}_traces.png"
    sim.analysis.plotRaster(
        include=["VIP", "SC", "PP", "MS"],
        timeRange=time_range,
        marker="|",
        saveFig=str(raster_path),
        showFig=False,
    )
    sim.analysis.plotTraces(
        include=[("VIP", 0)],
        timeRange=time_range,
        oneFigPer="cell",
        legend=True,
        saveFig=str(traces_path),
        showFig=False,
    )
    return {
        "raster": str(raster_path),
        "traces": str(traces_path),
    }


def _run_phase(output_dir, phase_name, ms_enabled):
    if hasattr(sim, "net"):
        sim.clearAll()

    _configure_phase(output_dir, phase_name, ms_enabled)
    netparams_module = _load_netparams_module()
    phase_netparams = _restrict_to_vip_only(netparams_module.netParams)
    cfg.saveFolder = str(output_dir)
    cfg.simLabel = phase_name

    if not ms_enabled:
        cfg.MS_train = [1.0]
        phase_netparams.popParams["MS"]["numCells"] = 1
        phase_netparams.popParams["MS"]["spkTimes"] = cfg.MS_train
    else:
        phase_netparams.popParams["MS"]["numCells"] = int(cfg.nMS)
        phase_netparams.popParams["MS"]["spkTimes"] = list(cfg.MS_train)

    sim.initialize(simConfig=cfg, netParams=phase_netparams)
    sim.net.createPops()
    sim.net.createCells()
    sim.net.connectCells()
    sim.net.addStims()
    sim.setupRecording()
    sim.runSim()
    sim.gatherData()

    phase_sim_data = sim.allSimData if hasattr(sim, "allSimData") else sim.simData
    summary = _phase_summary(sim.simData, ms_enabled=ms_enabled)
    trace_data = extract_recorded_trace(
        sim_data=phase_sim_data,
        trace_name="V_soma",
        gid=0,
        record_step=cfg.recordStep,
    )
    trace_data["sc_pp_spike_times"] = list(cfg.thetaSpikeTimes)
    trace_data["ms_spike_times"] = [] if not ms_enabled else list(cfg.MS_train)
    sim.saveData()
    figure_paths = _plot_phase(output_dir, phase_name)
    sim.clearAll()

    return {
        "summary": summary,
        "figures": figure_paths,
        "data_file": str(Path(cfg.saveFolder) / f"{phase_name}_data.json"),
        "trace_data": trace_data,
    }


def main():
    args = parse_args()
    batch_dir = Path(args.batch_dir).resolve()
    study, journal_path = _load_study(batch_dir, args.study_label)
    trial = _get_trial(study, args.trial)
    _bootstrap_simulation_imports()

    output_dir = Path(args.output_dir).resolve() if args.output_dir else batch_dir / f"best_trial_{trial.number}"
    output_dir.mkdir(parents=True, exist_ok=True)

    _apply_trial_params(trial.params)

    phases = []
    if args.phase in ("both", "ms_off"):
        phases.append(("best_trial_{}_ms_off".format(trial.number), False))
    if args.phase in ("both", "ms_on"):
        phases.append(("best_trial_{}_ms_on".format(trial.number), True))

    results = {}
    for phase_name, ms_enabled in phases:
        results[phase_name] = _run_phase(output_dir, phase_name, ms_enabled)

    combined_trace_figure = None
    if len(results) == 2:
        phase_names = list(results.keys())
        combined_trace_figure = save_combined_vip_trace_figure(
            no_ms_trace=results[phase_names[0]]["trace_data"],
            ms_trace=results[phase_names[1]]["trace_data"],
            output_path=output_dir / f"best_trial_{trial.number}_vip_traces_ms_off_ms_on.png",
        )
    serializable_results = {
        phase_name: {key: value for key, value in phase_result.items() if key != "trace_data"}
        for phase_name, phase_result in results.items()
    }

    summary_path = output_dir / "best_trial_summary.json"
    payload = {
        "study_name": study.study_name,
        "journal_path": str(journal_path),
        "trial_number": trial.number,
        "trial_value": trial.value,
        "trial_params": trial.params,
        "output_dir": str(output_dir),
        "combined_trace_figure": combined_trace_figure,
        "phases": serializable_results,
    }
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    print(f"Best trial rerun complete: trial {trial.number}")
    print(f"Summary: {summary_path}")
    for phase_name, phase_result in results.items():
        print(f"{phase_name}: loss={phase_result['summary']['loss']}")
        print(f"  data: {phase_result['data_file']}")
        print(f"  raster: {phase_result['figures']['raster']}")
        print(f"  traces: {phase_result['figures']['traces']}")
    if combined_trace_figure:
        print(f"Combined VIP traces: {combined_trace_figure}")


if __name__ == "__main__":
    main()
