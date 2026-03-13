import importlib
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("NEURON_MODULE_OPTIONS", "-nogui")

import matplotlib

matplotlib.use("Agg")

from netpyne import sim

from cfg import cfg, refresh_cfg
from vip_batch_plots import extract_recorded_trace, save_combined_vip_trace_figure
from vip_batch_fitness import combine_vip_phase_summaries, summarize_vip_theta_response


def _get_trial_paths():
    trial_save_folder = getattr(cfg, "_batchtk_path_pointer", None) or cfg.saveFolder
    trial_label = getattr(cfg, "_batchtk_label_pointer", None) or cfg.simLabel
    Path(trial_save_folder).mkdir(parents=True, exist_ok=True)
    return trial_save_folder, trial_label


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


def _phase_summary(sim_data, vip_gids, theta_windows, ms_enabled):
    if ms_enabled:
        return summarize_vip_theta_response(
            simData=sim_data,
            vip_gids=vip_gids,
            no_ms_windows=[],
            ms_windows=theta_windows,
            target_spikes_per_cycle=cfg.vipBatchTargetSpikesPerCycle,
        )
    return summarize_vip_theta_response(
        simData=sim_data,
        vip_gids=vip_gids,
        no_ms_windows=theta_windows,
        ms_windows=[],
        target_spikes_per_cycle=0,
        missing_vip_penalty=0.0,
    )


def _run_phase(phase_name, ms_enabled, vip_gids, trial_save_folder, trial_label):
    if hasattr(sim, "net"):
        sim.clearAll()

    cfg.vipBatchProtocol = False
    cfg.enableDefaultAnalysis = False
    refresh_cfg(cfg)
    cfg.hParams["v_init"] = float(getattr(cfg, "vipBatchVInit", cfg.hParams["v_init"]))
    cfg.saveFolder = trial_save_folder
    cfg.recordCells = [("VIP", 0)]
    cfg.recordTraces = {
        "V_soma": {"sec": "soma", "loc": 0.5, "var": "v"},
        "I_nAch": {"synMech": "nACh_IS3", "var": "i", "conds": {"pop": "VIP"}},
    }

    netparams_module = _load_netparams_module()
    phase_netparams = _restrict_to_vip_only(netparams_module.netParams)

    if not ms_enabled:
        cfg.MS_train = [1.0]
        phase_netparams.popParams["MS"]["numCells"] = 1
        phase_netparams.popParams["MS"]["spkTimes"] = cfg.MS_train
    cfg.simLabel = f"{trial_label}_{phase_name}"

    sim.initialize(simConfig=cfg, netParams=phase_netparams)
    sim.net.createPops()
    sim.net.createCells()
    sim.net.connectCells()
    sim.net.addStims()
    sim.setupRecording()

    sim.runSim()
    sim.gatherData()

    phase_sim_data = sim.allSimData if hasattr(sim, "allSimData") else sim.simData
    summary = _phase_summary(
        sim_data=sim.simData,
        vip_gids=vip_gids,
        theta_windows=cfg.thetaCycleWindows,
        ms_enabled=ms_enabled,
    )
    trace_data = extract_recorded_trace(
        sim_data=phase_sim_data,
        trace_name="V_soma",
        gid=0,
        record_step=cfg.recordStep,
    )
    trace_data["sc_pp_spike_times"] = list(cfg.thetaSpikeTimes)
    trace_data["ms_spike_times"] = [] if not ms_enabled else list(cfg.MS_train)

    sim.saveData()
    sim.clearAll()

    return {"summary": summary, "trace": trace_data}


def main():
    cfg.vipBatchProtocol = False
    cfg.enableDefaultAnalysis = False
    refresh_cfg(cfg)

    trial_save_folder, trial_label = _get_trial_paths()
    vip_gids = list(range(int(cfg.VIP)))

    no_ms_result = _run_phase(
        phase_name="ms_off",
        ms_enabled=False,
        vip_gids=vip_gids,
        trial_save_folder=trial_save_folder,
        trial_label=trial_label,
    )
    ms_result = _run_phase(
        phase_name="ms_on",
        ms_enabled=True,
        vip_gids=vip_gids,
        trial_save_folder=trial_save_folder,
        trial_label=trial_label,
    )

    combined_summary = combine_vip_phase_summaries(
        no_ms_summary=no_ms_result["summary"],
        ms_summary=ms_result["summary"],
        target_spikes_per_cycle=cfg.vipBatchTargetSpikesPerCycle,
        ms_gain_weight=float(getattr(cfg, "vipBatchMsGainWeight", 20.0)),
    )
    combined_summary["combined_trace_figure"] = save_combined_vip_trace_figure(
        no_ms_trace=no_ms_result["trace"],
        ms_trace=ms_result["trace"],
        output_path=Path(trial_save_folder) / f"{trial_label}_vip_traces_ms_off_ms_on.png",
    )

    sim.send(combined_summary)


if __name__ == "__main__":
    main()
