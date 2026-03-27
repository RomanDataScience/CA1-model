import argparse
import importlib
import json
import os
import sys
from collections.abc import MutableMapping
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("NEURON_MODULE_OPTIONS", "-nogui")

_mpl_config_dir = Path(os.environ.get("TMPDIR", "/tmp")) / "matplotlib-src"
_mpl_config_dir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_mpl_config_dir))

import matplotlib
import optuna

matplotlib.use("Agg")

try:
    from optuna.storages.journal import JournalFileBackend, JournalStorage

    def _build_journal_storage(journal_path):
        return JournalStorage(JournalFileBackend(str(journal_path)))

except ImportError:
    from optuna.storages import JournalFileStorage, JournalStorage

    def _build_journal_storage(journal_path):
        return JournalStorage(JournalFileStorage(str(journal_path)))


REPO_ROOT = Path(__file__).resolve().parents[1]
BATCH_RUNS_DIR = REPO_ROOT / "batch_runs"
DEFAULT_STUDY_LABEL = "vip_optuna_theta_gate_v3"
DEFAULT_TRIAL_NUMBER = 74

sim = None
cfg = None
refresh_cfg = None


def _parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run the full src simulation using VIP-related parameters "
            "from one Optuna trial."
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
        help="Trial number whose parameters should be applied to the full simulation.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Destination for the full-network rerun. Defaults to <batch-dir>/full_trial_<trial>.",
    )
    return parser.parse_args()


def _resolve_batch_dir(study_label, batch_dir):
    if batch_dir is not None:
        return Path(batch_dir).expanduser().resolve()
    return (BATCH_RUNS_DIR / study_label).resolve()


def _resolve_journal_path(batch_dir, study_label):
    expected_path = batch_dir / f"{study_label}_optuna.optuna.journal.log"
    if expected_path.exists():
        return expected_path

    matches = sorted(batch_dir.glob("*.optuna.journal.log"))
    if len(matches) == 1:
        return matches[0]

    if not matches:
        raise FileNotFoundError(f"No Optuna journal found in {batch_dir}.")

    match_list = ", ".join(path.name for path in matches)
    raise FileNotFoundError(
        f"Could not infer a unique Optuna journal in {batch_dir}. "
        f"Expected {expected_path.name}; found: {match_list}"
    )


def _load_study(batch_dir, study_label):
    journal_path = _resolve_journal_path(batch_dir, study_label)
    study_name = f"{study_label}_optuna"
    storage = _build_journal_storage(journal_path)
    study = optuna.load_study(study_name=study_name, storage=storage)
    return study, journal_path


def _get_trial(study, trial_number):
    for trial in study.get_trials(deepcopy=False):
        if trial.number == trial_number:
            return trial

    available = sorted(trial.number for trial in study.get_trials(deepcopy=False))
    preview = ", ".join(str(number) for number in available[:20])
    raise ValueError(
        f"Trial {trial_number} was not found in study {study.study_name}. "
        f"Available trial numbers start with: {preview}"
    )


def _get_child(container, key):
    if isinstance(container, MutableMapping):
        return container[key]
    return getattr(container, key)


def _set_child(container, key, value):
    if isinstance(container, MutableMapping):
        container[key] = value
        return
    setattr(container, key, value)


def _set_cfg_path(target_cfg, dotted_path, value):
    parts = dotted_path.split(".")
    current = target_cfg
    for part in parts[:-1]:
        current = _get_child(current, part)
    _set_child(current, parts[-1], value)


def _bootstrap_simulation_imports():
    global sim, cfg, refresh_cfg
    if sim is not None:
        return sim, cfg, refresh_cfg

    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))

    from netpyne import sim as netpyne_sim
    from cfg import cfg as sim_cfg, refresh_cfg as refresh_cfg_fn

    sim = netpyne_sim
    cfg = sim_cfg
    refresh_cfg = refresh_cfg_fn
    return sim, cfg, refresh_cfg


def _load_netparams_module():
    if "netParams" in sys.modules:
        return importlib.reload(sys.modules["netParams"])
    return importlib.import_module("netParams")


def _apply_trial_params(target_cfg, params):
    for path, value in params.items():
        _set_cfg_path(target_cfg, path, value)


def _trial_value_payload(trial):
    if getattr(trial, "values", None) is not None:
        return list(trial.values)
    return trial.value


def _apply_trial_v_init(target_cfg):
    target_cfg.hParams["v_init"] = float(getattr(target_cfg, "vipBatchVInit", target_cfg.hParams["v_init"]))


def main():
    args = _parse_args()

    batch_dir = _resolve_batch_dir(args.study_label, args.batch_dir)
    study, journal_path = _load_study(batch_dir, args.study_label)
    trial = _get_trial(study, args.trial)

    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir is not None
        else (batch_dir / f"full_trial_{trial.number}").resolve()
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    sim_module, sim_cfg, refresh_cfg_fn = _bootstrap_simulation_imports()

    _apply_trial_params(sim_cfg, trial.params)
    sim_cfg._batchtk_label_pointer = None
    sim_cfg._batchtk_path_pointer = None
    sim_cfg.vipBatchProtocol = False
    sim_cfg.enableDefaultAnalysis = True
    sim_cfg.saveFolder = str(output_dir)
    refresh_cfg_fn(sim_cfg)
    _apply_trial_v_init(sim_cfg)
    sim_cfg.saveFolder = str(output_dir)

    if hasattr(sim_module, "net"):
        sim_module.clearAll()

    netparams_module = _load_netparams_module()
    full_netparams = netparams_module.netParams

    sim_cfg.saveFolder = str(output_dir)
    sim_cfg.simLabel = f"full_trial_{trial.number}_{sim_cfg.simLabel}"

    sim_module.initialize(simConfig=sim_cfg, netParams=full_netparams)
    sim_module.net.createPops()
    sim_module.net.createCells()
    sim_module.net.connectCells()
    sim_module.net.addStims()
    sim_module.setupRecording()
    sim_module.runSim()
    sim_module.gatherData()
    sim_module.saveData()
    sim_module.analysis.plotData()

    data_json_path = output_dir / f"{sim_cfg.simLabel}_data.json"
    summary = {
        "study_label": args.study_label,
        "study_name": study.study_name,
        "journal_path": str(journal_path),
        "trial_number": trial.number,
        "trial_state": trial.state.name,
        "trial_value": _trial_value_payload(trial),
        "trial_params": dict(trial.params),
        "output_dir": str(output_dir),
        "sim_label": sim_cfg.simLabel,
        "data_json": str(data_json_path) if data_json_path.exists() else None,
    }

    summary_path = output_dir / "full_trial_summary.json"
    with summary_path.open("w", encoding="utf-8") as summary_file:
        json.dump(summary, summary_file, indent=2, sort_keys=True)

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
