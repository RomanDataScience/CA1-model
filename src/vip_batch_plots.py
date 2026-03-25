from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def extract_recorded_trace(sim_data, trace_name="V_soma", gid=0, record_step=0.1):
    trace_block = sim_data.get(trace_name, {})
    trace_key = f"cell_{gid}"
    trace_values = trace_block.get(trace_key) if isinstance(trace_block, dict) else None

    if trace_values is None:
        return {"t": [], "y": [], "label": trace_name}

    if isinstance(trace_values, dict):
        first_key = next(iter(trace_values), None)
        trace_values = trace_values[first_key] if first_key is not None else []

    y = np.asarray(trace_values, dtype=float)
    time_values = sim_data.get("t", [])
    if len(time_values) == len(y):
        t = np.asarray(time_values, dtype=float)
    else:
        step = float(record_step)
        t = np.arange(0.0, len(y) * step, step)

    return {"t": t.tolist(), "y": y.tolist(), "label": trace_name}


def _draw_input_ticks(axis, trace_data):
    x = trace_data.get("t", [])
    y = trace_data.get("y", [])
    if not x or not y:
        return

    sc_pp_spike_times = trace_data.get("sc_pp_spike_times", [])
    ms_spike_times = trace_data.get("ms_spike_times", [])
    y_min = min(y)
    y_max = max(y)
    y_span = max(y_max - y_min, 1.0)
    sc_pp_y0 = y_max + 0.04 * y_span
    sc_pp_y1 = y_max + 0.12 * y_span
    ms_y0 = y_max + 0.16 * y_span
    ms_y1 = y_max + 0.24 * y_span

    if sc_pp_spike_times:
        axis.vlines(sc_pp_spike_times, sc_pp_y0, sc_pp_y1, colors="tab:blue", linewidth=0.8, alpha=0.8)
    if ms_spike_times:
        axis.vlines(ms_spike_times, ms_y0, ms_y1, colors="tab:orange", linewidth=1.0, alpha=0.9)

    axis.set_ylim(y_min - 0.05 * y_span, y_max + 0.30 * y_span)
    axis.text(0.01, 0.97, "SC/PP", color="tab:blue", fontsize=9, va="top", transform=axis.transAxes)
    axis.text(0.12, 0.97, "MS", color="tab:orange", fontsize=9, va="top", transform=axis.transAxes)


def save_combined_vip_trace_figure(no_ms_trace, ms_trace, output_path, ylabel="V_soma (mV)"):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(2, 1, sharex=True, figsize=(10, 6))
    phase_data = (
        ("MS off", no_ms_trace, axes[0]),
        ("MS on", ms_trace, axes[1]),
    )

    for title, trace_data, axis in phase_data:
        x = trace_data.get("t", [])
        y = trace_data.get("y", [])
        if x and y:
            axis.plot(x, y, linewidth=1.2, color="black")
            _draw_input_ticks(axis, trace_data)
        else:
            axis.text(0.5, 0.5, "Trace unavailable", ha="center", va="center", transform=axis.transAxes)
        axis.set_title(title)
        axis.set_ylabel(ylabel)

    axes[-1].set_xlabel("Time (ms)")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return str(output_path)
