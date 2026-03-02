from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


V_INIT_MV = -70.0
CELSIUS_C = 34.0
TSTOP_MS = 16000.0
DT_MS = 0.025

ICLAMP_DELAY_MS = 0.0
ICLAMP_DUR_MS = 1e9
STIM_TIME_MS = (0.0, 13000.0, 14000.0, 15000.0, 16000.0)
STIM_AMP_NA = (0*0.09, 0*0.09, 0.45, 0*0.09, 0*0.09)


def _require_neuron():
    try:
        from neuron import h  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"NEURON is required to run this script: {exc}") from exc
    return h


def _require_netpyne():
    try:
        from netpyne import specs, sim  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"NetPyNE is required to run this script: {exc}") from exc
    return specs, sim


def _iter_mechanism_candidates(repo_root: Path) -> list[Path]:
    preferred = [
        repo_root / "arm64" / "libnrnmech.dylib",
        repo_root / "arm64" / ".libs" / "libnrnmech.dylib",
        repo_root / "x86_64" / "libnrnmech.dylib",
        repo_root / "x86_64" / ".libs" / "libnrnmech.dylib",
        repo_root / "x86_64" / ".libs" / "libnrnmech.so",
    ]

    seen: set[Path] = set()
    candidates: list[Path] = []

    for path in preferred:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            candidates.append(path)

    for pattern in ("**/libnrnmech.dylib", "**/libnrnmech.so"):
        for path in sorted(repo_root.glob(pattern)):
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                candidates.append(path)

    return candidates


def _load_available_mechanisms(h, repo_root: Path) -> list[Path]:
    loaded: list[Path] = []
    errors: list[str] = []

    for candidate in _iter_mechanism_candidates(repo_root):
        if not candidate.is_file():
            continue
        try:
            h.nrn_load_dll(str(candidate))
        except RuntimeError as exc:
            message = str(exc)
            if "already exists" not in message and "hocobj_call error" not in message:
                errors.append(f"{candidate}: {message}")
                continue
        except OSError as exc:
            errors.append(f"{candidate}: {exc}")
            continue
        loaded.append(candidate)

    if not loaded:
        detail = errors[0] if errors else "no compiled mechanism library was found"
        raise RuntimeError(f"Unable to load NEURON mechanisms: {detail}")

    return loaded


def _resolve_section_handle(section_data, section_name: str):
    candidates: list[object] = []

    if isinstance(section_data, dict):
        for key in ("hObj", "hSec"):
            if key in section_data:
                candidates.append(section_data[key])
    else:
        for attr_name in ("hObj", "hSec"):
            candidate = getattr(section_data, attr_name, None)
            if candidate is not None:
                candidates.append(candidate)
        candidates.append(section_data)

    for candidate in candidates:
        if candidate is None:
            continue
        if isinstance(candidate, (list, tuple)):
            if candidate and callable(candidate[0]):
                return candidate[0]
            continue
        if callable(candidate):
            return candidate

    available_keys: list[str] = []
    if isinstance(section_data, dict):
        available_keys = sorted(str(key) for key in section_data.keys())

    raise RuntimeError(
        f"Section '{section_name}' does not expose a callable NEURON Section handle. "
        f"Available keys: {available_keys or 'n/a'}"
    )


def _pick_soma_section_name(section_names: Iterable[str]) -> str:
    names = list(section_names)
    if not names:
        raise RuntimeError("The instantiated cell has no sections.")

    for matcher in (
        lambda name: name == "soma",
        lambda name: name.lower() == "soma",
        lambda name: name.lower().startswith("soma"),
        lambda name: "soma" in name.lower(),
    ):
        for name in names:
            if matcher(name):
                return name

    return names[0]


def _vector_from_values(h, values: Sequence[float]):
    vector = h.Vector(len(values))
    for index, value in enumerate(values):
        vector.x[index] = float(value)
    return vector


def _vector_to_list(vector) -> list[float]:
    return [float(value) for value in vector]


def _write_trace_csv(output_path: Path, time_ms: Sequence[float], voltage_mv: Sequence[float], current_na: Sequence[float]) -> None:
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_ms", "voltage_mv", "current_nA"])
        for time_value, voltage_value, current_value in zip(time_ms, voltage_mv, current_na):
            writer.writerow([f"{time_value:.12g}", f"{voltage_value:.12g}", f"{current_value:.12g}"])


def _plot_trace(output_path: Path, model_name: str, time_ms: Sequence[float], voltage_mv: Sequence[float], current_na: Sequence[float]) -> None:
    figure, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    axes[0].plot(time_ms, voltage_mv, linewidth=1.0, color="#1f77b4")
    axes[0].set_ylabel("Voltage (mV)")
    axes[0].set_title(f"{model_name}: Figure 8 Ramp Protocol")
    axes[0].grid(True, alpha=0.2)

    axes[1].plot(time_ms, current_na, linewidth=1.0, color="#d62728")
    axes[1].set_xlabel("Time (ms)")
    axes[1].set_ylabel("Current (nA)")
    axes[1].grid(True, alpha=0.2)

    figure.tight_layout()
    figure.savefig(output_path, dpi=200)
    plt.close(figure)


def run_model(model_name: str, cell_json: Path, output_dir: Path) -> tuple[Path, Path]:
    repo_root = Path(__file__).resolve().parents[1]

    if not cell_json.is_file():
        raise RuntimeError(f"Missing cell JSON: {cell_json}")

    h = _require_neuron()
    specs, sim = _require_netpyne()
    _load_available_mechanisms(h, repo_root)

    with cell_json.open("r", encoding="utf-8") as handle:
        cell_rule = json.load(handle)

    if "secs" not in cell_rule:
        raise RuntimeError(f"{cell_json} does not look like a NetPyNE cell rule.")

    if hasattr(sim, "clearAll"):
        sim.clearAll()

    conds = cell_rule.get("conds", {})
    cell_type = str(conds.get("cellType", model_name))
    cell_model = str(conds.get("cellModel", model_name))

    net_params = specs.NetParams()
    net_params.cellParams[model_name] = specs.Dict(cell_rule)
    net_params.popParams[f"{model_name}_pop"] = {
        "cellType": cell_type,
        "cellModel": cell_model,
        "numCells": 1,
    }

    sim_config = specs.SimConfig()
    sim_config.duration = TSTOP_MS
    sim_config.dt = DT_MS
    sim_config.verbose = False
    sim_config.cvode_active = False
    sim_config.hParams = {"celsius": CELSIUS_C, "v_init": V_INIT_MV}

    sim.create(netParams=net_params, simConfig=sim_config)

    if not getattr(sim.net, "cells", None):
        raise RuntimeError(f"NetPyNE did not instantiate the {model_name} cell.")

    cell = sim.net.cells[0]
    soma_name = _pick_soma_section_name(cell.secs.keys())
    soma_section = _resolve_section_handle(cell.secs[soma_name], soma_name)

    iclamp = h.IClamp(soma_section(0.5))
    iclamp.delay = ICLAMP_DELAY_MS
    iclamp.dur = ICLAMP_DUR_MS

    time_vec = _vector_from_values(h, STIM_TIME_MS)
    amp_vec = _vector_from_values(h, STIM_AMP_NA)
    amp_vec.play(iclamp._ref_amp, time_vec, 1)

    recorded_t = h.Vector()
    recorded_t.record(h._ref_t)

    recorded_v = h.Vector()
    recorded_v.record(soma_section(0.5)._ref_v)

    recorded_i = h.Vector()
    recorded_i.record(iclamp._ref_i)

    cvode = h.CVode()
    cvode.active(1)
    h.celsius = CELSIUS_C
    h.finitialize(V_INIT_MV)
    h.fcurrent()
    cvode.re_init()
    cvode.solve(TSTOP_MS)

    sim._single_cell_refs = {
        "iclamp": iclamp,
        "time_vec": time_vec,
        "amp_vec": amp_vec,
        "recorded_t": recorded_t,
        "recorded_v": recorded_v,
        "recorded_i": recorded_i,
        "cvode": cvode,
    }

    time_ms = _vector_to_list(recorded_t)
    voltage_mv = _vector_to_list(recorded_v)
    current_na = _vector_to_list(recorded_i)

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"{model_name}_trace.csv"
    png_path = output_dir / f"{model_name}_trace.png"

    _write_trace_csv(csv_path, time_ms, voltage_mv, current_na)
    _plot_trace(png_path, model_name, time_ms, voltage_mv, current_na)

    return csv_path, png_path


def main_for_model(model_name: str, json_name: str, argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    default_cell_json = repo_root / "cells" / json_name
    default_output_dir = Path(__file__).resolve().parent / "results"

    parser = argparse.ArgumentParser(
        description=f"Run the Figure 8 ramp protocol in NetPyNE using cells/{json_name}."
    )
    parser.add_argument(
        "--cell-json",
        type=Path,
        default=default_cell_json,
        help="Path to the NetPyNE JSON cell rule to run.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir,
        help=f"Directory where {model_name}_trace.csv and {model_name}_trace.png will be written.",
    )
    args = parser.parse_args(argv)

    try:
        csv_path, png_path = run_model(model_name, args.cell_json, args.output_dir)
    except Exception as exc:
        print(f"{model_name} run failed: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote trace CSV to: {csv_path.resolve()}")
    print(f"Wrote trace plot to: {png_path.resolve()}")
    return 0
