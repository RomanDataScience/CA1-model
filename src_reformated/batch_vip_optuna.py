from collections import OrderedDict
from pathlib import Path

from netpyne.batch import Batch

from vip_batch_fitness import build_vip_gid_range, build_vip_protocol_windows, vip_theta_fitness


BASE_DIR = Path(__file__).resolve().parent
ENV_BIN = Path("/Users/romanbaravalle/miniconda3/envs/M1_CEBRA/bin")
NRN_COMMAND = str(ENV_BIN / "nrniv")
MPI_COMMAND = str(ENV_BIN / "mpiexec")

NO_MS_CYCLES = 5
MS_CYCLES = 5
INTER_PHASE_GAP = 200.0
TARGET_SPIKES_PER_CYCLE = 4
MAX_TRIALS = 40


def build_vip_optuna_batch():
    params = OrderedDict(
        [
            ("factorSynVIP", [0.1, 3.0]),
            ("nMSweight", [1e-5, 5e-3]),
            (("synMechParams", "nACh_IS3", "tau2"), [120.0, 320.0]),
        ]
    )

    no_ms_windows, ms_windows = build_vip_protocol_windows(
        transient=500.0,
        inter_burst_isi=200.0,
        no_ms_cycles=NO_MS_CYCLES,
        ms_cycles=MS_CYCLES,
        inter_phase_gap=INTER_PHASE_GAP,
    )

    batch = Batch(
        cfgFile=str(BASE_DIR / "cfg.py"),
        netParamsFile=str(BASE_DIR / "netParams.py"),
        params=params,
    )
    batch.batchLabel = "vip_optuna_theta_gate"
    batch.saveFolder = str(BASE_DIR / "batch_runs" / batch.batchLabel)
    batch.method = "optuna"

    batch.initCfg = OrderedDict(
        [
            ("vipBatchProtocol", True),
            ("vipBatchNoMsCycles", NO_MS_CYCLES),
            ("vipBatchMsCycles", MS_CYCLES),
            ("vipBatchInterPhaseGap", INTER_PHASE_GAP),
            ("enableDefaultAnalysis", False),
            ("recordTraces", {}),
            ("saveJson", True),
            ("savePickle", False),
            ("saveDataInclude", ["simData", "simConfig"]),
        ]
    )

    batch.optimCfg = {
        "fitnessFunc": vip_theta_fitness,
        "fitnessFuncArgs": {
            "vip_gids": build_vip_gid_range(pyr_cells=1, olm_cells=1, vip_cells=1),
            "no_ms_windows": no_ms_windows,
            "ms_windows": ms_windows,
            "target_spikes_per_cycle": TARGET_SPIKES_PER_CYCLE,
            "no_ms_weight": 25.0,
            "ms_weight": 5.0,
            "outside_weight": 100.0,
            "missing_vip_penalty": 1e6,
        },
        "maxiters": MAX_TRIALS,
        "maxiter_wait": 2000,
        "time_sleep": 5,
        "maxFitness": 1e9,
        "direction": "minimize",
    }

    batch.runCfg = {
        "type": "mpi_direct",
        "script": "init.py",
        "folder": str(BASE_DIR),
        "nodes": 1,
        "coresPerNode": 1,
        "sleepInterval": 1.0,
        "mpiCommand": MPI_COMMAND,
        "nrnCommand": NRN_COMMAND,
        "executor": "/bin/bash",
    }

    return batch


def main():
    batch = build_vip_optuna_batch()
    batch.run()


if __name__ == "__main__":
    main()
