from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Iterable, Optional, Sequence

import pytest


def _require_neuron():
    try:
        from neuron import h  # type: ignore
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"NEURON not available: {exc}", allow_module_level=True)
    return h


def _require_netpyne():
    try:
        from netpyne import specs, sim  # type: ignore
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"NetPyNE not available: {exc}", allow_module_level=True)
    return specs, sim


_MECHS_LOADED: bool = False
_MECH_PATH: Optional[Path] = None


def _load_compiled_mechanisms(h, candidates: Iterable[Path]) -> Path:
    """Load one of the compiled mechanism libraries for NEURON."""

    global _MECHS_LOADED, _MECH_PATH
    if _MECHS_LOADED and _MECH_PATH is not None:
        return _MECH_PATH

    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            h.nrn_load_dll(str(candidate))
        except RuntimeError as exc:  # pragma: no cover
            msg = str(exc)
            if "already exists" not in msg and "hocobj_call error" not in msg:
                raise
        except OSError as exc:  # pragma: no cover
            pytest.skip(
                f"Compiled mechanisms found at {candidate} but failed to load: {exc}",
                allow_module_level=True,
            )
        _MECHS_LOADED = True
        _MECH_PATH = candidate
        return candidate

    pytest.skip(
        "No compiled NEURON mechanisms were found; run nrnivmodl before this test.",
        allow_module_level=True,
    )


h = _require_neuron()
specs, sim = _require_netpyne()


def remove_point_processes(cell_rule):
    """Remove 'pointps' from all sections in a NetPyNE cell rule."""

    cell_dict = json.loads(json.dumps(cell_rule))
    for sec_data in cell_dict.get("secs", {}).values():
        sec_data.pop("pointps", None)
    return cell_dict


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


def _read_float_lines(path: Path) -> list[float]:
    return [float(line.strip()) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _vector_to_list(vector) -> list[float]:
    return [float(value) for value in vector]


def _vector_from_values(values: Sequence[float]):
    vector = h.Vector(len(values))
    for index, value in enumerate(values):
        vector.x[index] = float(value)
    return vector


def _write_trace_csv(output_path: Path, time_ms: Sequence[float], values: Sequence[float], value_label: str) -> None:
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_ms", value_label])
        for time_value, trace_value in zip(time_ms, values):
            writer.writerow([f"{time_value:.12g}", f"{trace_value:.12g}"])


def _run_imported_cell_simulation(net_params):
    if hasattr(sim, "clearAll"):
        sim.clearAll()

    sim_config = specs.SimConfig()
    sim_config.duration = 16000.0
    sim_config.dt = 0.025
    sim_config.verbose = False
    sim_config.cvode_active = False
    sim_config.hParams = {"celsius": 34.0, "v_init": -70.0}

    net_params.popParams["PC2B_pop"] = {"cellType": "PC2B", "cellModel": "HH", "numCells": 1}
    sim.create(netParams=net_params, simConfig=sim_config)

    if not getattr(sim.net, "cells", None):
        raise RuntimeError("NetPyNE did not instantiate a PC2B cell.")

    cell = sim.net.cells[0]
    soma_section = _resolve_section_handle(cell.secs["soma"], "soma")

    iclamp = h.IClamp(soma_section(0.5))
    iclamp.delay = 0.0
    iclamp.dur = 1e9

    time_vec = _vector_from_values([0.0, 13000.0, 14000.0, 15000.0, 16000.0])
    amp_vec = _vector_from_values([0.09, 0.09, 0.45, 0.09, 0.09])
    amp_vec.play(iclamp._ref_amp, time_vec, 1)

    recorded_t = h.Vector()
    recorded_t.record(h._ref_t)

    recorded_v = h.Vector()
    recorded_v.record(soma_section(0.5)._ref_v)

    recorded_i = h.Vector()
    recorded_i.record(iclamp._ref_i)

    cvode = h.CVode()
    cvode.active(1)
    h.celsius = 34.0
    h.tstop = 16000.0
    h.finitialize(-70.0)
    h.fcurrent()
    cvode.re_init()
    cvode.solve(16000.0)

    # Keep references alive for the duration of the run.
    sim._sim8_refs = {
        "iclamp": iclamp,
        "time_vec": time_vec,
        "amp_vec": amp_vec,
        "recorded_t": recorded_t,
        "recorded_v": recorded_v,
        "recorded_i": recorded_i,
        "cvode": cvode,
    }

    return _vector_to_list(recorded_t), _vector_to_list(recorded_v), _vector_to_list(recorded_i)


def test_load_figure8control_hoc_and_run_imported_cell() -> None:
    """Run Figure8control.hoc, then run the equivalent protocol on the imported NetPyNE cell."""

    repo_root = Path(__file__).resolve().parents[1]
    model_dir = repo_root / "original_models" / "cholinergic_shift_generalize"
    hoc_entry = model_dir / "Figure8control.hoc"
    output_dir = repo_root / "NetPyNE_comparison" / "results" / "latest"

    assert model_dir.is_dir(), "Cholinergic shift model directory is missing."
    assert hoc_entry.is_file(), "Figure8control.hoc is missing."

    output_dir.mkdir(parents=True, exist_ok=True)

    _load_compiled_mechanisms(
        h,
        (
            repo_root / "arm64" / "libnrnmech.dylib",
            repo_root / "arm64" / ".libs" / "libnrnmech.dylib",
            repo_root / "x86_64" / "libnrnmech.dylib",
            repo_root / "x86_64" / ".libs" / "libnrnmech.dylib",
            repo_root / "x86_64" / ".libs" / "libnrnmech.so",
        ),
    )

    prev_dir = Path.cwd()
    os.chdir(model_dir)

    try:
        h.load_file(str(hoc_entry.name))

        hoc_time = _read_float_lines(model_dir / "time.txt")
        hoc_voltage = _read_float_lines(model_dir / "v.txt")
        hoc_current = _read_float_lines(model_dir / "i.txt")
        assert hoc_time, "Legacy Figure8control run did not produce time samples."
        assert len(hoc_time) == len(hoc_voltage), "Legacy Figure8control time/voltage traces differ in length."
        assert len(hoc_time) == len(hoc_current), "Legacy Figure8control time/current traces differ in length."
        _write_trace_csv(output_dir / "sim8_hoc_voltage.csv", hoc_time, hoc_voltage, "voltage_mv")
        _write_trace_csv(output_dir / "sim8_hoc_current.csv", hoc_time, hoc_current, "current_nA")

        file2 = model_dir / "Figure8control_Bis.hoc"
        net_params = specs.NetParams()
        net_params.importCellParams(
            label="PC2B",
            conds={"cellType": "PC2B", "cellModel": "HH"},
            fileName= str(file2.name),
            cellName=None,
            cellArgs=None,
            cellInstance=True,
            somaAtOrigin=True,
        )

        net_params.renameCellParamsSec(label="PC2B", oldSec="soma_0", newSec="soma")

        clean_cell = remove_point_processes(net_params.cellParams["PC2B"])
        cells_dir = repo_root / "cells"
        cells_dir.mkdir(exist_ok=True)
        out_file = cells_dir / "PC2B.json"
        with out_file.open("w", encoding="utf-8") as handle:
            json.dump(clean_cell, handle, indent=4)

        netpyne_time, netpyne_voltage, netpyne_current = _run_imported_cell_simulation(net_params)
        assert netpyne_time, "Imported NetPyNE cell simulation did not record time samples."
        assert len(netpyne_time) == len(netpyne_voltage), "NetPyNE time/voltage traces differ in length."
        assert len(netpyne_time) == len(netpyne_current), "NetPyNE time/current traces differ in length."
        _write_trace_csv(output_dir / "sim8_netpyne_voltage.csv", netpyne_time, netpyne_voltage, "voltage_mv")
        _write_trace_csv(output_dir / "sim8_netpyne_current.csv", netpyne_time, netpyne_current, "current_nA")
    finally:
        os.chdir(prev_dir)


test_load_figure8control_hoc_and_run_imported_cell()
