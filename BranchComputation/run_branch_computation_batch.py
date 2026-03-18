import argparse
import csv
import importlib
import json
import os
import sys
import textwrap
from pathlib import Path

import matplotlib
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.patches import Circle

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("NEURON_MODULE_OPTIONS", "-nogui")
_mpl_config_dir = Path(os.environ.get("TMPDIR", "/tmp")) / "matplotlib-BranchComputation"
_mpl_config_dir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_mpl_config_dir))

matplotlib.use("Agg")
import matplotlib.pyplot as plt


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_REFORMATED = REPO_ROOT / "src_reformated"
if str(SRC_REFORMATED) not in sys.path:
    sys.path.insert(0, str(SRC_REFORMATED))


DEFAULT_INTENSITY_SCALES = [round(value, 6) for value in np.linspace(0.25, 1.5, 10)]
DEFAULT_DT = 1e-2
DEFAULT_CVODE_ATOL = 1e-6


sim = None
cfg = None
refresh_cfg = None


def _parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run a PC2B single-cell branch-computation sweep using the existing theta "
            "stimulation protocol, varying the number of active SC/PP branches and "
            "the input intensity."
        )
    )
    parser.add_argument(
        "--output-dir",
        default=str((REPO_ROOT / "BranchComputation" / "output").resolve()),
        help="Destination folder for run outputs and batch summaries.",
    )
    parser.add_argument(
        "--cell-file",
        default=str((REPO_ROOT / "cells" / "PC2B_new.json").resolve()),
        help=(
            "PC2B cell JSON to use. Defaults to PC2B_new.json, which keeps dendritic "
            "ICAN in proximal trunk sections."
        ),
    )
    parser.add_argument(
        "--connection-counts",
        nargs="+",
        type=int,
        default=None,
        help=(
            "Requested SC and PP synaptic-connection counts to sweep. If omitted, "
            "the script uses 1..max over the existing theta target-site lists."
        ),
    )
    parser.add_argument(
        "--intensity-scales",
        nargs="+",
        type=float,
        default=DEFAULT_INTENSITY_SCALES,
        help=(
            "Multipliers applied to the baseline PC2B theta synaptic strength "
            "(cfg.factorSynPYR). Defaults to 10 values from 0.25x to 1.5x."
        ),
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=12345,
        help="Seed used for reproducible random site-connection draws.",
    )
    parser.add_argument(
        "--upstate-delta-mv",
        type=float,
        default=7.5,
        help="Somatic depolarization above baseline used to detect the up state.",
    )
    parser.add_argument(
        "--morphology-projection",
        choices=sorted(PROJECTION_AXES),
        default="xz",
        help="Projection used for the morphology input plot (default: xz).",
    )
    parser.add_argument(
        "--dt",
        type=float,
        default=DEFAULT_DT,
        help="Simulation dt and recordStep for this batch (default: 1e-2).",
    )
    parser.add_argument(
        "--cvode-atol",
        type=float,
        default=DEFAULT_CVODE_ATOL,
        help="CVode absolute tolerance for this batch (default: 1e-6).",
    )
    parser.add_argument(
        "--upstate-smooth-ms",
        type=float,
        default=5.0,
        help="Moving-average window for the soma voltage before thresholding.",
    )
    parser.add_argument(
        "--upstate-min-duration-ms",
        type=float,
        default=20.0,
        help="Minimum duration required for an up-state segment to count.",
    )
    parser.add_argument(
        "--upstate-merge-gap-ms",
        type=float,
        default=20.0,
        help="Merge gaps shorter than this when stitching up-state segments.",
    )
    parser.add_argument(
        "--ican-threshold-fraction",
        type=float,
        default=0.1,
        help=(
            "Fraction of the peak summed inward dendritic ICAN used to estimate "
            "ICAN-active duration."
        ),
    )
    parser.add_argument(
        "--save-netpyne-json",
        action="store_true",
        help="Also ask NetPyNE to save its standard JSON output for each run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned sweep configuration and exit without running simulations.",
    )
    return parser.parse_args()


def _load_netparams_module():
    if "netParams" in sys.modules:
        return importlib.reload(sys.modules["netParams"])
    return importlib.import_module("netParams")


def _bootstrap_simulation_imports():
    global sim, cfg, refresh_cfg
    if sim is not None:
        return sim, cfg, refresh_cfg

    from netpyne import sim as netpyne_sim
    from cfg import cfg as sim_cfg, refresh_cfg as refresh_cfg_fn

    sim = netpyne_sim
    cfg = sim_cfg
    refresh_cfg = refresh_cfg_fn
    return sim, cfg, refresh_cfg


def _restrict_to_pc2b_only(netparams):
    keep_pops = {"PC2B", "SC", "PP"}
    keep_cell_params = {"PC2B"}
    keep_conn_prefixes = ("SC->PC2B_", "PP->PC2B_")

    for pop_name in list(netparams.popParams.keys()):
        if pop_name not in keep_pops:
            del netparams.popParams[pop_name]

    for cell_name in list(netparams.cellParams.keys()):
        if cell_name not in keep_cell_params:
            del netparams.cellParams[cell_name]

    for conn_name in list(netparams.connParams.keys()):
        if not conn_name.startswith(keep_conn_prefixes):
            del netparams.connParams[conn_name]

    for subconn_name in list(netparams.subConnParams.keys()):
        del netparams.subConnParams[subconn_name]

    return netparams


def _load_cell_definition(cell_path):
    with Path(cell_path).expanduser().resolve().open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _sections_with_ican(cell_def):
    sections = []
    for sec_name, sec_data in cell_def.get("secs", {}).items():
        mechs = sec_data.get("mechs", {})
        if sec_name != "soma" and ("ican" in mechs or "ican_PYR" in mechs):
            sections.append(sec_name)
    return sections


def _extract_unique_sections(site_specs):
    unique_sections = []
    seen = set()
    for sec_name, *_rest in site_specs:
        if sec_name in seen:
            continue
        seen.add(sec_name)
        unique_sections.append(sec_name)
    return unique_sections


def _ordered_random_sample(items, count, rng):
    if count <= 0:
        return []
    if count > len(items):
        raise ValueError(f"Cannot sample {count} items from a pool of size {len(items)}.")
    chosen_indices = sorted(int(index) for index in rng.choice(len(items), size=count, replace=False))
    return [items[index] for index in chosen_indices]


def _filter_sites_by_sections(site_specs, active_sections):
    active_sections = set(active_sections)
    return [site for site in site_specs if site[0] in active_sections]


def _site_to_dict(site):
    sec_name, loc, nmda_mult = site
    return {
        "sec": str(sec_name),
        "loc": float(loc),
        "nmda_mult": float(nmda_mult),
    }


def _group_sites_by_section(site_specs):
    grouped = {}
    for sec_name, loc, nmda_mult in site_specs:
        group = grouped.setdefault(
            str(sec_name),
            {"sec": str(sec_name), "locs": [], "nmda_mults": []},
        )
        loc_value = float(loc)
        nmda_value = float(nmda_mult)
        if loc_value not in group["locs"]:
            group["locs"].append(loc_value)
        if nmda_value not in group["nmda_mults"]:
            group["nmda_mults"].append(nmda_value)

    for group in grouped.values():
        group["locs"].sort()
        group["nmda_mults"].sort()

    return list(grouped.values())


def _grouped_site_lines(label, grouped_sites):
    if not grouped_sites:
        return [f"{label}: none"]

    lines = [f"{label}:"]
    for group in grouped_sites:
        locs = ", ".join(f"{loc:.1f}" for loc in group["locs"])
        nmda_mults = ", ".join(f"{value:.1f}" for value in group["nmda_mults"])
        lines.append(f"  {group['sec']} @ loc [{locs}]  nmda x[{nmda_mults}]")
    return lines


def _sorted_connection_counts(connection_counts, max_available):
    if connection_counts is None:
        return list(range(1, max_available + 1))

    unique_counts = sorted({int(value) for value in connection_counts})
    if not unique_counts:
        raise ValueError("At least one connection count must be provided.")
    if unique_counts[0] <= 0:
        raise ValueError("Connection counts must be positive integers.")
    if unique_counts[-1] > max_available:
        raise ValueError(
            f"Requested connection_count {unique_counts[-1]} exceeds the available "
            f"theta target-site count of {max_available}."
        )
    return unique_counts


def _build_random_connection_draws(
    sc_sites_all,
    pp_sites_all,
    connection_counts,
    random_seed,
):
    rng = np.random.default_rng(random_seed)
    draws = []
    for draw_index, connection_count in enumerate(connection_counts, start=1):
        sc_sites = _ordered_random_sample(sc_sites_all, connection_count, rng)
        pp_sites = _ordered_random_sample(pp_sites_all, connection_count, rng)
        draws.append(
            {
                "draw_index": draw_index,
                "connection_count": int(connection_count),
                "sc_sites": [list(site) for site in sc_sites],
                "pp_sites": [list(site) for site in pp_sites],
            }
        )

    return draws


def _sorted_intensity_scales(scales):
    unique_scales = sorted({float(value) for value in scales})
    if not unique_scales:
        raise ValueError("At least one intensity scale must be provided.")
    if unique_scales[0] <= 0.0:
        raise ValueError("Intensity scales must be positive.")
    return unique_scales


def _apply_solver_settings(sim_cfg, dt, cvode_atol):
    dt = float(dt)
    cvode_atol = float(cvode_atol)
    if dt <= 0.0:
        raise ValueError("dt must be positive.")
    if cvode_atol <= 0.0:
        raise ValueError("cvode_atol must be positive.")

    sim_cfg.dt = dt
    sim_cfg.recordStep = dt
    sim_cfg.cvode_active = True
    sim_cfg.cvode_atol = cvode_atol


def _trace_key_sort_key(key):
    suffix = str(key).split("_")[-1]
    if suffix.isdigit():
        return (0, int(suffix))
    return (1, str(key))


def _extract_first_trace(trace_store):
    if trace_store is None:
        return None
    if isinstance(trace_store, dict):
        if not trace_store:
            return None
        first_key = sorted(trace_store, key=_trace_key_sort_key)[0]
        trace_store = trace_store[first_key]
    array = np.asarray(trace_store, dtype=float)
    if array.size == 0:
        return None
    return array


def _moving_average(values, window_size):
    if window_size <= 1 or values.size == 0:
        return values.copy()
    kernel = np.ones(window_size, dtype=float) / float(window_size)
    return np.convolve(values, kernel, mode="same")


def _compute_inward_ican(ican_matrix):
    inward_matrix = np.maximum(-np.asarray(ican_matrix, dtype=float), 0.0)
    if inward_matrix.ndim != 2:
        inward_matrix = np.reshape(inward_matrix, (0, 0))
    total_inward_trace = np.sum(inward_matrix, axis=0) if inward_matrix.size else np.zeros(
        inward_matrix.shape[1] if inward_matrix.ndim == 2 else 0,
        dtype=float,
    )
    return inward_matrix, total_inward_trace


def _plot_theta_spike_lines(ax, theta_spike_times):
    for spike_time in theta_spike_times:
        ax.axvline(float(spike_time), color="#cfd8dc", linewidth=0.6, alpha=0.35, zorder=0)


PROJECTION_AXES = {
    "xy": (0, 1),
    "xz": (0, 2),
    "yz": (1, 2),
}


def _line_width_from_diam(diameter):
    return max(0.5, min(4.0, float(diameter) * 0.35))


def _section_pt3d_points(cell_def, sec_name):
    section = cell_def.get("secs", {}).get(sec_name, {})
    geom = section.get("geom", {})
    points = geom.get("pt3d")
    if not isinstance(points, list):
        return []
    return [point for point in points if isinstance(point, list) and len(point) >= 3]


def _section_average_diameter(cell_def, sec_name):
    section = cell_def.get("secs", {}).get(sec_name, {})
    geom = section.get("geom", {})
    diameter = geom.get("diam")
    if isinstance(diameter, (int, float)):
        return float(diameter)
    if isinstance(diameter, list) and diameter:
        return float(np.mean([float(value) for value in diameter]))

    points = _section_pt3d_points(cell_def, sec_name)
    diameters = [float(point[3]) for point in points if len(point) >= 4]
    if diameters:
        return float(np.mean(diameters))
    return 1.0


def _build_morphology_geometry(cell_def, projection):
    axis_a, axis_b = PROJECTION_AXES[projection]
    segments = []
    widths = []
    soma_circles = []

    for sec_name in cell_def.get("secs", {}):
        points = _section_pt3d_points(cell_def, sec_name)
        if len(points) < 2:
            continue

        if sec_name.lower() == "soma":
            center = points[len(points) // 2]
            soma_circles.append(
                (
                    (float(center[axis_a]), float(center[axis_b])),
                    max(0.5, _section_average_diameter(cell_def, sec_name) / 2.0),
                )
            )

        for start, end in zip(points, points[1:]):
            start_xy = (float(start[axis_a]), float(start[axis_b]))
            end_xy = (float(end[axis_a]), float(end[axis_b]))
            point_diams = []
            if len(start) >= 4:
                point_diams.append(float(start[3]))
            if len(end) >= 4:
                point_diams.append(float(end[3]))
            diameter = (
                float(np.mean(point_diams))
                if point_diams
                else _section_average_diameter(cell_def, sec_name)
            )
            segments.append((start_xy, end_xy))
            widths.append(_line_width_from_diam(diameter))

    return segments, widths, soma_circles


def _interpolate_section_point(cell_def, sec_name, loc):
    points = _section_pt3d_points(cell_def, sec_name)
    if not points:
        return None
    if len(points) == 1:
        return [float(points[0][0]), float(points[0][1]), float(points[0][2])]

    cumulative = [0.0]
    for start, end in zip(points, points[1:]):
        dx = float(end[0]) - float(start[0])
        dy = float(end[1]) - float(start[1])
        dz = float(end[2]) - float(start[2])
        cumulative.append(cumulative[-1] + float(np.sqrt(dx * dx + dy * dy + dz * dz)))

    total_length = cumulative[-1]
    if total_length <= 0.0:
        return [float(points[0][0]), float(points[0][1]), float(points[0][2])]

    target = max(0.0, min(float(loc), 1.0)) * total_length
    for index in range(1, len(cumulative)):
        if cumulative[index] < target:
            continue
        segment_length = cumulative[index] - cumulative[index - 1]
        if segment_length <= 0.0:
            return [float(points[index][0]), float(points[index][1]), float(points[index][2])]
        fraction = (target - cumulative[index - 1]) / segment_length
        start = points[index - 1]
        end = points[index]
        return [
            float(start[dim]) + fraction * (float(end[dim]) - float(start[dim]))
            for dim in range(3)
        ]

    last = points[-1]
    return [float(last[0]), float(last[1]), float(last[2])]


def _project_xyz(point_xyz, projection):
    axis_a, axis_b = PROJECTION_AXES[projection]
    return (float(point_xyz[axis_a]), float(point_xyz[axis_b]))


def _save_morphology_inputs_figure(
    output_path,
    cell_def,
    active_sc_sites,
    active_pp_sites,
    projection="xz",
):
    segments, widths, soma_circles = _build_morphology_geometry(cell_def, projection=projection)
    figure, axis = plt.subplots(figsize=(8, 10), constrained_layout=True)

    if segments:
        collection = LineCollection(
            segments,
            linewidths=widths,
            colors="#1f2937",
            capstyle="round",
            joinstyle="round",
            zorder=1,
        )
        axis.add_collection(collection)

    for center, radius in soma_circles:
        axis.add_patch(
            Circle(
                center,
                radius=radius,
                facecolor="#cbd5e1",
                edgecolor="#1f2937",
                linewidth=1.0,
                zorder=2,
            )
        )

    def _scatter_sites(site_dicts, color, marker, label, size):
        x_values = []
        y_values = []
        for site in site_dicts:
            point_xyz = _interpolate_section_point(cell_def, site["sec"], site["loc"])
            if point_xyz is None:
                continue
            x_value, y_value = _project_xyz(point_xyz, projection)
            x_values.append(x_value)
            y_values.append(y_value)
        if x_values:
            axis.scatter(
                x_values,
                y_values,
                c=color,
                marker=marker,
                s=size,
                label=label,
                edgecolors="black",
                linewidths=0.5,
                zorder=4,
            )

    _scatter_sites(active_sc_sites, color="#1d4ed8", marker="o", label="SC input", size=42)
    _scatter_sites(active_pp_sites, color="#dc2626", marker="s", label="PP input", size=42)

    axis.autoscale()
    axis.margins(0.08)
    axis.set_aspect("equal", adjustable="datalim")
    axis.grid(False)
    axis.set_xlabel(f"{projection[0].upper()} (um)")
    axis.set_ylabel(f"{projection[1].upper()} (um)")
    axis.set_title(f"PC2B morphology with sampled SC/PP sites ({projection})")
    axis.legend(loc="upper left", fontsize=8)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=250, bbox_inches="tight")
    plt.close(figure)
    return str(Path(output_path).resolve())


def _plot_window_limits(time, theta_spike_times, lead_ms=200.0):
    time = np.asarray(time, dtype=float)
    theta_spike_times = np.asarray(theta_spike_times, dtype=float)
    if time.size == 0:
        return None, None

    if theta_spike_times.size:
        start_ms = max(float(time[0]), float(np.min(theta_spike_times)) - float(lead_ms))
    else:
        start_ms = float(time[0])
    end_ms = float(time[-1])
    return start_ms, end_ms


def _plot_soma_voltage_axis(
    ax,
    time,
    soma_voltage,
    theta_spike_times,
    soma_spike_times,
    up_state_summary,
):
    ax.plot(time, soma_voltage, color="#0b4f6c", linewidth=1.2)
    _plot_theta_spike_lines(ax, theta_spike_times)
    x_start, x_end = _plot_window_limits(time, theta_spike_times)
    if x_start is not None:
        ax.set_xlim(x_start, x_end)

    baseline_mv = up_state_summary["baseline_mv"]
    threshold_mv = up_state_summary["threshold_mv"]
    ax.axhline(baseline_mv, color="#7a7a7a", linestyle="--", linewidth=0.9, label="baseline")
    ax.axhline(threshold_mv, color="#c0392b", linestyle="--", linewidth=0.9, label="up-state threshold")

    if up_state_summary["start_ms"] is not None and up_state_summary["end_ms"] is not None:
        ax.axvspan(
            up_state_summary["start_ms"],
            up_state_summary["end_ms"],
            color="#f4d35e",
            alpha=0.25,
            label="main up-state window",
        )

    soma_spike_times = np.asarray(soma_spike_times, dtype=float)
    if soma_spike_times.size:
        spike_voltages = np.interp(soma_spike_times, time, soma_voltage)
        ax.scatter(
            soma_spike_times,
            spike_voltages,
            s=18,
            color="#c0392b",
            zorder=3,
            label="somatic spikes",
        )

    ax.set_ylabel("V_soma (mV)")
    ax.set_xlabel("Time (ms)")
    ax.set_title("Somatic voltage")
    ax.grid(alpha=0.2)
    ax.legend(loc="upper right", fontsize=8)


def _plot_total_ican_axis(
    ax,
    time,
    inward_total_ican,
    theta_spike_times,
    ican_summary,
):
    ax.plot(time, inward_total_ican, color="#8e5a2b", linewidth=1.2)
    _plot_theta_spike_lines(ax, theta_spike_times)
    x_start, x_end = _plot_window_limits(time, theta_spike_times)
    if x_start is not None:
        ax.set_xlim(x_start, x_end)
    ax.axhline(
        ican_summary["threshold"],
        color="#b23a48",
        linestyle="--",
        linewidth=0.9,
        label="ICAN threshold",
    )
    ax.set_ylabel("Summed inward ICAN")
    ax.set_xlabel("Time (ms)")
    ax.set_title("Summed dendritic ICAN")
    ax.grid(alpha=0.2)
    ax.legend(loc="upper right", fontsize=8)


def _plot_ican_heatmap_axis(
    ax,
    time,
    inward_ican_matrix,
    dendritic_sections,
    theta_spike_times,
):
    if inward_ican_matrix.size == 0:
        ax.axis("off")
        ax.text(0.5, 0.5, "No dendritic ICAN traces", ha="center", va="center")
        return None

    image = ax.imshow(
        inward_ican_matrix,
        aspect="auto",
        origin="lower",
        extent=[float(time[0]), float(time[-1]), -0.5, len(dendritic_sections) - 0.5],
        cmap="inferno",
    )
    _plot_theta_spike_lines(ax, theta_spike_times)
    x_start, x_end = _plot_window_limits(time, theta_spike_times)
    if x_start is not None:
        ax.set_xlim(x_start, x_end)

    tick_step = max(1, int(np.ceil(len(dendritic_sections) / 12)))
    tick_indices = list(range(0, len(dendritic_sections), tick_step))
    ax.set_yticks(tick_indices)
    ax.set_yticklabels([dendritic_sections[index] for index in tick_indices], fontsize=8)
    ax.set_ylabel("Dendritic section")
    ax.set_xlabel("Time (ms)")
    ax.set_title("Dendritic ICAN heatmap")
    return image


def _build_summary_text(
    draw_index,
    connection_count,
    intensity_scale,
    factor_syn_pyr,
    theta_ampa_weight,
    theta_nmda_weight,
    active_sc_sites_grouped,
    active_pp_sites_grouped,
    up_state_summary,
    ican_summary,
    activated_ican_summary,
):
    lines = [
        f"draw_index: {draw_index}",
        f"requested connection_count: {connection_count}",
        f"intensity_scale: {intensity_scale:.2f}",
        f"factorSynPYR: {factor_syn_pyr:.6f}",
        f"theta AMPA wt: {theta_ampa_weight:.6g}",
        f"theta NMDA wt: {theta_nmda_weight:.6g}",
        f"stimulated SC sections: {len(active_sc_sites_grouped)}",
        f"stimulated PP sections: {len(active_pp_sites_grouped)}",
        "",
        "Up state:",
        f"  duration: {up_state_summary['duration_ms']:.2f} ms",
        f"  total duration: {up_state_summary['total_duration_ms']:.2f} ms",
        f"  start/end: {up_state_summary['start_ms']} / {up_state_summary['end_ms']}",
        f"  spikes in main window: {up_state_summary['spike_count']}",
        f"  peak V: {up_state_summary['peak_voltage_mv']:.2f} mV",
        "",
        "Dendritic ICAN:",
        f"  duration: {ican_summary['duration_ms']:.2f} ms",
        f"  peak total inward: {ican_summary['peak_total_inward_ican']:.6f}",
        f"  peak section: {ican_summary['peak_section']}",
        f"  peak section value: {ican_summary['peak_section_value']:.6f}",
        f"  activated sections: {activated_ican_summary['section_count']}",
        f"  active section list: {', '.join(activated_ican_summary['sections']) or 'none'}",
        "",
        "Active site rule:",
        "  This run samples N SC theta sites and N PP theta sites",
        "  at random from the already-targeted theta site lists.",
        "  Because the sampling unit is the site, SC loc values can",
        "  vary independently across 0.2, 0.5, and 0.8 where defined.",
        "",
    ]
    lines.extend(_grouped_site_lines("SC active sites", active_sc_sites_grouped))
    lines.append("")
    lines.extend(_grouped_site_lines("PP active sites", active_pp_sites_grouped))
    return "\n".join(lines)


def _wrap_multiline_text(text, width):
    wrapped_lines = []
    for raw_line in text.splitlines():
        if not raw_line:
            wrapped_lines.append("")
            continue
        stripped_line = raw_line.lstrip(" ")
        indent = raw_line[: len(raw_line) - len(stripped_line)]
        wrapped_lines.append(
            textwrap.fill(
                stripped_line,
                width=width,
                initial_indent=indent,
                subsequent_indent=indent,
                break_long_words=False,
                replace_whitespace=False,
            )
        )
    return "\n".join(wrapped_lines)


def _save_soma_voltage_figure(
    output_path,
    time,
    soma_voltage,
    theta_spike_times,
    soma_spike_times,
    up_state_summary,
):
    fig, ax = plt.subplots(figsize=(12, 4.5))
    _plot_soma_voltage_axis(
        ax=ax,
        time=time,
        soma_voltage=soma_voltage,
        theta_spike_times=theta_spike_times,
        soma_spike_times=soma_spike_times,
        up_state_summary=up_state_summary,
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    return str(Path(output_path).resolve())


def _save_total_ican_figure(
    output_path,
    time,
    inward_total_ican,
    theta_spike_times,
    ican_summary,
):
    fig, ax = plt.subplots(figsize=(12, 4.5))
    _plot_total_ican_axis(
        ax=ax,
        time=time,
        inward_total_ican=inward_total_ican,
        theta_spike_times=theta_spike_times,
        ican_summary=ican_summary,
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    return str(Path(output_path).resolve())


def _save_ican_heatmap_figure(
    output_path,
    time,
    inward_ican_matrix,
    dendritic_sections,
    theta_spike_times,
):
    fig, ax = plt.subplots(figsize=(12, 7))
    image = _plot_ican_heatmap_axis(
        ax=ax,
        time=time,
        inward_ican_matrix=inward_ican_matrix,
        dendritic_sections=dendritic_sections,
        theta_spike_times=theta_spike_times,
    )
    if image is not None:
        colorbar = fig.colorbar(image, ax=ax, pad=0.01)
        colorbar.set_label("Inward ICAN (-itrpm4)")
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    return str(Path(output_path).resolve())


def _save_summary_panel_figure(
    output_path,
    time,
    soma_voltage,
    soma_spike_times,
    theta_spike_times,
    up_state_summary,
    inward_total_ican,
    inward_ican_matrix,
    dendritic_sections,
    ican_summary,
    activated_ican_summary,
    draw_index,
    connection_count,
    intensity_scale,
    factor_syn_pyr,
    theta_ampa_weight,
    theta_nmda_weight,
    active_sc_sites_grouped,
    active_pp_sites_grouped,
):
    fig, axes = plt.subplots(
        2,
        2,
        figsize=(16, 10),
        gridspec_kw={"height_ratios": [1.0, 1.2], "width_ratios": [1.3, 1.0]},
    )
    ax_soma = axes[0, 0]
    ax_ican = axes[0, 1]
    ax_heatmap = axes[1, 0]
    ax_text = axes[1, 1]

    _plot_soma_voltage_axis(
        ax=ax_soma,
        time=time,
        soma_voltage=soma_voltage,
        theta_spike_times=theta_spike_times,
        soma_spike_times=soma_spike_times,
        up_state_summary=up_state_summary,
    )
    _plot_total_ican_axis(
        ax=ax_ican,
        time=time,
        inward_total_ican=inward_total_ican,
        theta_spike_times=theta_spike_times,
        ican_summary=ican_summary,
    )
    image = _plot_ican_heatmap_axis(
        ax=ax_heatmap,
        time=time,
        inward_ican_matrix=inward_ican_matrix,
        dendritic_sections=dendritic_sections,
        theta_spike_times=theta_spike_times,
    )
    if image is not None:
        colorbar = fig.colorbar(image, ax=ax_heatmap, pad=0.01)
        colorbar.set_label("Inward ICAN (-itrpm4)")

    ax_text.axis("off")
    summary_text = _build_summary_text(
        draw_index=draw_index,
        connection_count=connection_count,
        intensity_scale=intensity_scale,
        factor_syn_pyr=factor_syn_pyr,
        theta_ampa_weight=theta_ampa_weight,
        theta_nmda_weight=theta_nmda_weight,
        active_sc_sites_grouped=active_sc_sites_grouped,
        active_pp_sites_grouped=active_pp_sites_grouped,
        up_state_summary=up_state_summary,
        ican_summary=ican_summary,
        activated_ican_summary=activated_ican_summary,
    )
    ax_text.text(
        0.0,
        1.0,
        _wrap_multiline_text(summary_text, width=58),
        ha="left",
        va="top",
        family="monospace",
        fontsize=9,
    )

    fig.suptitle(
        (
            f"Branch computation summary: draw={draw_index}, "
            f"N={connection_count}, intensity={intensity_scale:.2f}"
        ),
        fontsize=14,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    return str(Path(output_path).resolve())


def _boolean_segments(mask):
    segments = []
    start = None
    for index, active in enumerate(mask):
        if active and start is None:
            start = index
        elif not active and start is not None:
            segments.append([start, index - 1])
            start = None
    if start is not None:
        segments.append([start, len(mask) - 1])
    return segments


def _merge_segments(segments, max_gap_samples):
    if not segments:
        return []
    merged = [segments[0]]
    for start, stop in segments[1:]:
        previous = merged[-1]
        if start - previous[1] - 1 <= max_gap_samples:
            previous[1] = stop
        else:
            merged.append([start, stop])
    return merged


def _summarize_up_state(
    time,
    soma_voltage,
    spike_times,
    stim_start_ms,
    record_step_ms,
    delta_mv,
    smooth_ms,
    min_duration_ms,
    merge_gap_ms,
):
    time = np.asarray(time, dtype=float)
    soma_voltage = np.asarray(soma_voltage, dtype=float)
    spike_times = np.asarray(spike_times, dtype=float)

    baseline_mask = time < stim_start_ms
    if np.any(baseline_mask):
        baseline_mv = float(np.median(soma_voltage[baseline_mask]))
    else:
        baseline_mv = float(np.median(soma_voltage))

    smooth_samples = max(1, int(round(smooth_ms / record_step_ms)))
    smoothed_voltage = _moving_average(soma_voltage, smooth_samples)
    threshold_mv = baseline_mv + float(delta_mv)

    post_stim_mask = time >= stim_start_ms
    candidate_mask = np.zeros_like(smoothed_voltage, dtype=bool)
    candidate_mask[post_stim_mask] = smoothed_voltage[post_stim_mask] >= threshold_mv
    segments = _boolean_segments(candidate_mask)
    merged_segments = _merge_segments(
        segments,
        max_gap_samples=max(0, int(round(merge_gap_ms / record_step_ms))),
    )

    valid_segments = []
    for start_idx, end_idx in merged_segments:
        duration_ms = float(time[end_idx] - time[start_idx]) if end_idx >= start_idx else 0.0
        if duration_ms >= min_duration_ms:
            valid_segments.append((start_idx, end_idx, duration_ms))

    total_duration_ms = float(sum(segment[2] for segment in valid_segments))
    if not valid_segments:
        return {
            "baseline_mv": baseline_mv,
            "threshold_mv": threshold_mv,
            "start_ms": None,
            "end_ms": None,
            "duration_ms": 0.0,
            "total_duration_ms": 0.0,
            "peak_voltage_mv": float(np.max(soma_voltage)) if soma_voltage.size else None,
            "mean_voltage_mv": None,
            "area_above_threshold_mv_ms": 0.0,
            "spike_count": 0,
            "spike_times_ms": [],
        }

    best_start_idx, best_end_idx, best_duration_ms = max(valid_segments, key=lambda item: item[2])
    segment_voltage = soma_voltage[best_start_idx : best_end_idx + 1]
    segment_time = time[best_start_idx : best_end_idx + 1]
    segment_spike_mask = (spike_times >= time[best_start_idx]) & (spike_times <= time[best_end_idx])
    segment_spike_times = spike_times[segment_spike_mask]

    if segment_voltage.size > 1:
        area_above_threshold = float(
            np.trapz(np.maximum(segment_voltage - threshold_mv, 0.0), x=segment_time)
        )
    else:
        area_above_threshold = 0.0

    return {
        "baseline_mv": baseline_mv,
        "threshold_mv": threshold_mv,
        "start_ms": float(time[best_start_idx]),
        "end_ms": float(time[best_end_idx]),
        "duration_ms": float(best_duration_ms),
        "total_duration_ms": total_duration_ms,
        "peak_voltage_mv": float(np.max(segment_voltage)),
        "mean_voltage_mv": float(np.mean(segment_voltage)),
        "area_above_threshold_mv_ms": area_above_threshold,
        "spike_count": int(segment_spike_times.size),
        "spike_times_ms": segment_spike_times.tolist(),
    }


def _summarize_dendritic_ican(
    time,
    ican_matrix,
    stim_start_ms,
    threshold_fraction,
):
    time = np.asarray(time, dtype=float)
    ican_matrix = np.asarray(ican_matrix, dtype=float)

    if ican_matrix.size == 0:
        return {
            "peak_total_inward_ican": 0.0,
            "auc_total_inward_ican": 0.0,
            "duration_ms": 0.0,
            "threshold": 0.0,
            "peak_section": None,
            "peak_section_value": 0.0,
        }

    inward_matrix, total_inward_trace = _compute_inward_ican(ican_matrix)
    peak_total = float(np.max(total_inward_trace)) if total_inward_trace.size else 0.0
    threshold = peak_total * float(threshold_fraction)

    post_stim_mask = time >= stim_start_ms
    active_mask = np.zeros_like(total_inward_trace, dtype=bool)
    active_mask[post_stim_mask] = total_inward_trace[post_stim_mask] >= threshold
    active_segments = _boolean_segments(active_mask)

    duration_ms = 0.0
    for start_idx, end_idx in active_segments:
        duration_ms += float(time[end_idx] - time[start_idx]) if end_idx >= start_idx else 0.0

    if total_inward_trace.size > 1:
        auc = float(np.trapz(total_inward_trace[post_stim_mask], x=time[post_stim_mask]))
    else:
        auc = 0.0

    section_peaks = np.max(inward_matrix, axis=1)
    peak_section_index = int(np.argmax(section_peaks))

    return {
        "peak_total_inward_ican": peak_total,
        "auc_total_inward_ican": auc,
        "duration_ms": duration_ms,
        "threshold": threshold,
        "peak_section_index": peak_section_index,
        "peak_section_value": float(section_peaks[peak_section_index]),
    }


def _summarize_activated_ican_sections(
    inward_ican_matrix,
    dendritic_sections,
    threshold_fraction,
):
    inward_ican_matrix = np.asarray(inward_ican_matrix, dtype=float)
    dendritic_sections = list(dendritic_sections)

    if inward_ican_matrix.size == 0 or not dendritic_sections:
        return {
            "section_count": 0,
            "threshold": 0.0,
            "sections": [],
            "section_peaks": {},
        }

    section_peaks = np.max(inward_ican_matrix, axis=1)
    global_peak = float(np.max(section_peaks)) if section_peaks.size else 0.0
    threshold = global_peak * float(threshold_fraction)
    active_indices = [
        index for index, peak_value in enumerate(section_peaks) if float(peak_value) >= threshold
    ]
    active_sections = [dendritic_sections[index] for index in active_indices]

    return {
        "section_count": len(active_sections),
        "threshold": threshold,
        "sections": active_sections,
        "section_peaks": {
            dendritic_sections[index]: float(section_peaks[index]) for index in range(len(dendritic_sections))
        },
    }


def _pearson_correlation(x_values, y_values):
    x_values = np.asarray(x_values, dtype=float)
    y_values = np.asarray(y_values, dtype=float)
    if x_values.size < 2 or y_values.size < 2:
        return None
    if np.allclose(x_values, x_values[0]) or np.allclose(y_values, y_values[0]):
        return None
    return float(np.corrcoef(x_values, y_values)[0, 1])


def _ranks(values):
    values = np.asarray(values, dtype=float)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(values) + 1, dtype=float)
    return ranks


def _spearman_correlation(x_values, y_values):
    if len(x_values) < 2 or len(y_values) < 2:
        return None
    return _pearson_correlation(_ranks(x_values), _ranks(y_values))


def _build_record_traces(dendritic_ican_sections):
    record_traces = {
        "V_soma": {"sec": "soma", "loc": 0.5, "var": "v", "conds": {"pop": "PC2B"}},
    }
    for sec_name in dendritic_ican_sections:
        record_traces[f"I_ican_{sec_name}"] = {
            "sec": sec_name,
            "loc": 0.5,
            "mech": "ican",
            "var": "itrpm4",
            "conds": {"pop": "PC2B"},
        }
    return record_traces


def _run_single_simulation(
    args,
    sim_module,
    sim_cfg,
    refresh_cfg_fn,
    cell_def,
    draw_index,
    connection_count,
    intensity_scale,
    active_sc_sites_input,
    active_pp_sites_input,
    dendritic_ican_sections,
    base_theta_sc_sites,
    base_theta_pp_sites,
    base_factor_syn_pyr,
):
    if hasattr(sim_module, "net"):
        sim_module.clearAll()

    theta_sc_sites = [tuple(site) for site in active_sc_sites_input]
    theta_pp_sites = [tuple(site) for site in active_pp_sites_input]
    active_sc_sites = [_site_to_dict(site) for site in theta_sc_sites]
    active_pp_sites = [_site_to_dict(site) for site in theta_pp_sites]
    active_sc_sections = _extract_unique_sections(theta_sc_sites)
    active_pp_sections = _extract_unique_sections(theta_pp_sites)
    active_sc_sites_grouped = _group_sites_by_section(theta_sc_sites)
    active_pp_sites_grouped = _group_sites_by_section(theta_pp_sites)

    run_label = f"n_{connection_count:02d}_draw_{draw_index:02d}_intensity_{intensity_scale:.2f}".replace(
        ".", "p"
    )
    run_dir = Path(args.output_dir).expanduser().resolve() / "runs" / run_label
    run_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = run_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    sim_cfg._batchtk_label_pointer = None
    sim_cfg._batchtk_path_pointer = None
    sim_cfg.vipBatchProtocol = False
    sim_cfg.enableDefaultAnalysis = False
    sim_cfg.applyControlPC2B = False
    sim_cfg.PYROLMweight = 0.0
    sim_cfg.OLMPYRweight = 0.0
    sim_cfg.VIPOLMweight = 0.0
    sim_cfg.nMSweight = 0.0
    sim_cfg.PYRFile = str(Path(args.cell_file).expanduser().resolve())
    sim_cfg.factorSynPYR = float(base_factor_syn_pyr) * float(intensity_scale)
    sim_cfg.saveFolder = str(run_dir)
    sim_cfg.simLabelBase = "BranchComputation"

    refresh_cfg_fn(sim_cfg)
    _apply_solver_settings(sim_cfg, dt=args.dt, cvode_atol=args.cvode_atol)
    sim_cfg.saveFolder = str(run_dir)
    sim_cfg.thetaScSites = list(theta_sc_sites)
    sim_cfg.thetaPpSites = list(theta_pp_sites)
    sim_cfg.thetaAMPAWeightPYR = (
        sim_cfg.thetaSynScalePYR * sim_cfg.thetaAMPAUnitWeight * sim_cfg.factorSynPYR
    )
    sim_cfg.thetaNMDAWeightPYR = (
        sim_cfg.thetaSynScalePYR * sim_cfg.thetaNMDAUnitWeight * sim_cfg.factorSynPYR
    )
    sim_cfg.allPops = ["PC2B", "SC", "PP"]
    sim_cfg.recordExcludePops = ["SC", "PP"]
    sim_cfg.recordCells = [("PC2B", 0)]
    sim_cfg.recordTraces = _build_record_traces(dendritic_ican_sections)
    sim_cfg.saveJson = bool(args.save_netpyne_json)
    sim_cfg.savePickle = False
    sim_cfg.simLabel = (
        f"BranchComp_ControlFalse_N{connection_count:02d}_draw{draw_index:02d}_"
        f"intensity{intensity_scale:.2f}".replace(".", "p")
    )

    netparams_module = _load_netparams_module()
    restricted_netparams = _restrict_to_pc2b_only(netparams_module.netParams)

    sim_module.initialize(simConfig=sim_cfg, netParams=restricted_netparams)
    sim_module.net.createPops()
    sim_module.net.createCells()
    sim_module.net.connectCells()
    sim_module.net.addStims()
    sim_module.setupRecording()
    sim_module.runSim()
    sim_module.gatherData()

    sim_data = sim_module.allSimData if hasattr(sim_module, "allSimData") else sim_module.simData
    time = np.asarray(sim_data.get("t", []), dtype=float)
    soma_voltage = _extract_first_trace(sim_data.get("V_soma"))
    if time.size == 0 or soma_voltage is None:
        raise RuntimeError(f"Missing recorded time or soma voltage for run {run_label}.")

    spike_times = np.asarray(sim_data.get("spkt", []), dtype=float)
    spike_gids = np.asarray(sim_data.get("spkid", []), dtype=int)
    soma_gid = 0
    soma_spike_times = spike_times[spike_gids == soma_gid] if spike_times.size else np.asarray([])

    dendritic_traces = []
    available_sections = []
    for sec_name in dendritic_ican_sections:
        trace = _extract_first_trace(sim_data.get(f"I_ican_{sec_name}"))
        if trace is None:
            continue
        dendritic_traces.append(trace)
        available_sections.append(sec_name)

    if dendritic_traces:
        common_length = min(len(time), len(soma_voltage), *(len(trace) for trace in dendritic_traces))
        time = time[:common_length]
        soma_voltage = soma_voltage[:common_length]
        dendritic_matrix = np.vstack([np.asarray(trace[:common_length], dtype=float) for trace in dendritic_traces])
    else:
        common_length = min(len(time), len(soma_voltage))
        time = time[:common_length]
        soma_voltage = soma_voltage[:common_length]
        dendritic_matrix = np.zeros((0, common_length), dtype=float)
    inward_ican_matrix, inward_total_ican = _compute_inward_ican(dendritic_matrix)

    up_state_summary = _summarize_up_state(
        time=time,
        soma_voltage=soma_voltage,
        spike_times=soma_spike_times,
        stim_start_ms=float(sim_cfg.thetaBurstStart),
        record_step_ms=float(sim_cfg.recordStep),
        delta_mv=float(args.upstate_delta_mv),
        smooth_ms=float(args.upstate_smooth_ms),
        min_duration_ms=float(args.upstate_min_duration_ms),
        merge_gap_ms=float(args.upstate_merge_gap_ms),
    )
    ican_summary = _summarize_dendritic_ican(
        time=time,
        ican_matrix=dendritic_matrix,
        stim_start_ms=float(sim_cfg.thetaBurstStart),
        threshold_fraction=float(args.ican_threshold_fraction),
    )
    if available_sections and "peak_section_index" in ican_summary:
        ican_summary["peak_section"] = available_sections[ican_summary["peak_section_index"]]
    else:
        ican_summary["peak_section"] = None
    activated_ican_summary = _summarize_activated_ican_sections(
        inward_ican_matrix=inward_ican_matrix,
        dendritic_sections=available_sections,
        threshold_fraction=float(args.ican_threshold_fraction),
    )

    soma_voltage_plot = _save_soma_voltage_figure(
        output_path=plots_dir / "soma_voltage.png",
        time=time,
        soma_voltage=soma_voltage,
        theta_spike_times=sim_cfg.thetaSpikeTimes,
        soma_spike_times=soma_spike_times,
        up_state_summary=up_state_summary,
    )
    total_ican_plot = _save_total_ican_figure(
        output_path=plots_dir / "summed_dendritic_ican.png",
        time=time,
        inward_total_ican=inward_total_ican,
        theta_spike_times=sim_cfg.thetaSpikeTimes,
        ican_summary=ican_summary,
    )
    ican_heatmap_plot = _save_ican_heatmap_figure(
        output_path=plots_dir / "dendritic_ican_heatmap.png",
        time=time,
        inward_ican_matrix=inward_ican_matrix,
        dendritic_sections=available_sections,
        theta_spike_times=sim_cfg.thetaSpikeTimes,
    )
    morphology_inputs_plot = _save_morphology_inputs_figure(
        output_path=plots_dir / "morphology_inputs.png",
        cell_def=cell_def,
        active_sc_sites=active_sc_sites,
        active_pp_sites=active_pp_sites,
        projection=str(args.morphology_projection),
    )
    summary_panel_plot = _save_summary_panel_figure(
        output_path=plots_dir / "summary_panel.png",
        time=time,
        soma_voltage=soma_voltage,
        soma_spike_times=soma_spike_times,
        theta_spike_times=sim_cfg.thetaSpikeTimes,
        up_state_summary=up_state_summary,
        inward_total_ican=inward_total_ican,
        inward_ican_matrix=inward_ican_matrix,
        dendritic_sections=available_sections,
        ican_summary=ican_summary,
        activated_ican_summary=activated_ican_summary,
        draw_index=draw_index,
        connection_count=connection_count,
        intensity_scale=intensity_scale,
        factor_syn_pyr=float(sim_cfg.factorSynPYR),
        theta_ampa_weight=float(sim_cfg.thetaAMPAWeightPYR),
        theta_nmda_weight=float(sim_cfg.thetaNMDAWeightPYR),
        active_sc_sites_grouped=active_sc_sites_grouped,
        active_pp_sites_grouped=active_pp_sites_grouped,
    )

    np.savez_compressed(
        run_dir / "traces.npz",
        time_ms=time,
        soma_v_mv=soma_voltage,
        soma_spike_times_ms=soma_spike_times,
        dendritic_ican_sections=np.asarray(available_sections),
        dendritic_ican_itrpm4_matrix=dendritic_matrix,
    )

    result = {
        "run_label": run_label,
        "run_dir": str(run_dir),
        "trace_file": str((run_dir / "traces.npz").resolve()),
        "netpyne_json": (
            str((run_dir / f"{sim_cfg.simLabel}_data.json").resolve())
            if args.save_netpyne_json
            else None
        ),
        "cell_file": str(Path(args.cell_file).expanduser().resolve()),
        "draw_index": int(draw_index),
        "connection_count": int(connection_count),
        "intensity_scale": float(intensity_scale),
        "factorSynPYR": float(sim_cfg.factorSynPYR),
        "dt": float(sim_cfg.dt),
        "recordStep": float(sim_cfg.recordStep),
        "cvode_atol": float(sim_cfg.cvode_atol),
        "thetaAMPAWeightPYR": float(sim_cfg.thetaAMPAWeightPYR),
        "thetaNMDAWeightPYR": float(sim_cfg.thetaNMDAWeightPYR),
        "active_sc_sections": list(active_sc_sections),
        "active_pp_sections": list(active_pp_sections),
        "active_sc_sites": active_sc_sites,
        "active_pp_sites": active_pp_sites,
        "active_sc_sites_grouped": active_sc_sites_grouped,
        "active_pp_sites_grouped": active_pp_sites_grouped,
        "stimulated_sc_connection_count": len(theta_sc_sites),
        "stimulated_pp_connection_count": len(theta_pp_sites),
        "stimulated_sc_section_count": len(active_sc_sections),
        "stimulated_pp_section_count": len(active_pp_sections),
        "active_sc_site_count": len(theta_sc_sites),
        "active_pp_site_count": len(theta_pp_sites),
        "theta_spike_times_ms": list(sim_cfg.thetaSpikeTimes),
        "soma_spike_count": int(soma_spike_times.size),
        "up_state": up_state_summary,
        "dendritic_ican": ican_summary,
        "activated_ican": activated_ican_summary,
        "plots": {
            "morphology_inputs": morphology_inputs_plot,
            "soma_voltage": soma_voltage_plot,
            "summed_dendritic_ican": total_ican_plot,
            "dendritic_ican_heatmap": ican_heatmap_plot,
            "summary_panel": summary_panel_plot,
        },
    }

    with (run_dir / "run_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)

    if args.save_netpyne_json:
        sim_module.saveData()

    if hasattr(sim_module, "net"):
        sim_module.clearAll()

    return result


def _build_batch_summary(results, intensity_scales):
    overall_connection_count_pearson = _pearson_correlation(
        [row["connection_count"] for row in results],
        [row["up_state"]["duration_ms"] for row in results],
    )
    overall_connection_count_spearman = _spearman_correlation(
        [row["connection_count"] for row in results],
        [row["up_state"]["duration_ms"] for row in results],
    )
    overall_pearson = _pearson_correlation(
        [row["activated_ican"]["section_count"] for row in results],
        [row["up_state"]["duration_ms"] for row in results],
    )
    overall_spearman = _spearman_correlation(
        [row["activated_ican"]["section_count"] for row in results],
        [row["up_state"]["duration_ms"] for row in results],
    )

    per_intensity = []
    for intensity_scale in intensity_scales:
        rows = [row for row in results if np.isclose(row["intensity_scale"], intensity_scale)]
        per_intensity.append(
            {
                "intensity_scale": float(intensity_scale),
                "pearson_duration_vs_connection_count": _pearson_correlation(
                    [row["connection_count"] for row in rows],
                    [row["up_state"]["duration_ms"] for row in rows],
                ),
                "spearman_duration_vs_connection_count": _spearman_correlation(
                    [row["connection_count"] for row in rows],
                    [row["up_state"]["duration_ms"] for row in rows],
                ),
                "pearson_duration_vs_activated_ican_section_count": _pearson_correlation(
                    [row["activated_ican"]["section_count"] for row in rows],
                    [row["up_state"]["duration_ms"] for row in rows],
                ),
                "spearman_duration_vs_activated_ican_section_count": _spearman_correlation(
                    [row["activated_ican"]["section_count"] for row in rows],
                    [row["up_state"]["duration_ms"] for row in rows],
                ),
                "mean_duration_ms": float(
                    np.mean([row["up_state"]["duration_ms"] for row in rows])
                ),
                "max_duration_ms": float(
                    np.max([row["up_state"]["duration_ms"] for row in rows])
                ),
                "mean_activated_ican_section_count": float(
                    np.mean([row["activated_ican"]["section_count"] for row in rows])
                ),
            }
        )

    return {
        "overall_duration_vs_connection_count": {
            "pearson": overall_connection_count_pearson,
            "spearman": overall_connection_count_spearman,
        },
        "overall_duration_vs_activated_ican_section_count": {
            "pearson": overall_pearson,
            "spearman": overall_spearman,
        },
        "per_intensity": per_intensity,
    }


def _write_summary_csv(path, results):
    fieldnames = [
        "run_label",
        "draw_index",
        "connection_count",
        "intensity_scale",
        "factorSynPYR",
        "thetaAMPAWeightPYR",
        "thetaNMDAWeightPYR",
        "stimulated_sc_connection_count",
        "stimulated_pp_connection_count",
        "stimulated_sc_section_count",
        "stimulated_pp_section_count",
        "active_sc_site_count",
        "active_pp_site_count",
        "activated_ican_section_count",
        "soma_spike_count",
        "up_state_start_ms",
        "up_state_end_ms",
        "up_state_duration_ms",
        "up_state_total_duration_ms",
        "up_state_peak_voltage_mv",
        "up_state_area_above_threshold_mv_ms",
        "up_state_spike_count",
        "peak_total_inward_ican",
        "auc_total_inward_ican",
        "dendritic_ican_duration_ms",
        "peak_ican_section",
        "trace_file",
        "morphology_inputs_plot",
        "summary_panel_plot",
    ]
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(
                {
                    "run_label": row["run_label"],
                    "draw_index": row["draw_index"],
                    "connection_count": row["connection_count"],
                    "intensity_scale": row["intensity_scale"],
                    "factorSynPYR": row["factorSynPYR"],
                    "thetaAMPAWeightPYR": row["thetaAMPAWeightPYR"],
                    "thetaNMDAWeightPYR": row["thetaNMDAWeightPYR"],
                    "stimulated_sc_connection_count": row["stimulated_sc_connection_count"],
                    "stimulated_pp_connection_count": row["stimulated_pp_connection_count"],
                    "stimulated_sc_section_count": row["stimulated_sc_section_count"],
                    "stimulated_pp_section_count": row["stimulated_pp_section_count"],
                    "active_sc_site_count": row["active_sc_site_count"],
                    "active_pp_site_count": row["active_pp_site_count"],
                    "activated_ican_section_count": row["activated_ican"]["section_count"],
                    "soma_spike_count": row["soma_spike_count"],
                    "up_state_start_ms": row["up_state"]["start_ms"],
                    "up_state_end_ms": row["up_state"]["end_ms"],
                    "up_state_duration_ms": row["up_state"]["duration_ms"],
                    "up_state_total_duration_ms": row["up_state"]["total_duration_ms"],
                    "up_state_peak_voltage_mv": row["up_state"]["peak_voltage_mv"],
                    "up_state_area_above_threshold_mv_ms": row["up_state"][
                        "area_above_threshold_mv_ms"
                    ],
                    "up_state_spike_count": row["up_state"]["spike_count"],
                    "peak_total_inward_ican": row["dendritic_ican"]["peak_total_inward_ican"],
                    "auc_total_inward_ican": row["dendritic_ican"]["auc_total_inward_ican"],
                    "dendritic_ican_duration_ms": row["dendritic_ican"]["duration_ms"],
                    "peak_ican_section": row["dendritic_ican"]["peak_section"],
                    "trace_file": row["trace_file"],
                    "morphology_inputs_plot": row["plots"]["morphology_inputs"],
                    "summary_panel_plot": row["plots"]["summary_panel"],
                }
            )


def main():
    args = _parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    sim_module, sim_cfg, refresh_cfg_fn = _bootstrap_simulation_imports()
    sim_cfg.PYRFile = str(Path(args.cell_file).expanduser().resolve())
    refresh_cfg_fn(sim_cfg)
    _apply_solver_settings(sim_cfg, dt=args.dt, cvode_atol=args.cvode_atol)

    cell_def = _load_cell_definition(args.cell_file)
    dendritic_ican_sections = _sections_with_ican(cell_def)
    if not dendritic_ican_sections:
        raise ValueError(
            f"No dendritic ICAN sections were found in {Path(args.cell_file).expanduser().resolve()}."
        )

    base_theta_sc_sites = list(sim_cfg.thetaScSites)
    base_theta_pp_sites = list(sim_cfg.thetaPpSites)
    sc_unique_sections = _extract_unique_sections(base_theta_sc_sites)
    pp_unique_sections = _extract_unique_sections(base_theta_pp_sites)

    max_connection_count = min(len(base_theta_sc_sites), len(base_theta_pp_sites))
    connection_counts = _sorted_connection_counts(args.connection_counts, max_available=max_connection_count)
    random_connection_draws = _build_random_connection_draws(
        sc_sites_all=base_theta_sc_sites,
        pp_sites_all=base_theta_pp_sites,
        connection_counts=connection_counts,
        random_seed=int(args.random_seed),
    )
    intensity_scales = _sorted_intensity_scales(args.intensity_scales)
    base_factor_syn_pyr = float(sim_cfg.factorSynPYR)

    batch_config = {
        "output_dir": str(output_dir),
        "cell_file": str(Path(args.cell_file).expanduser().resolve()),
        "connection_counts": connection_counts,
        "intensity_scales": intensity_scales,
        "random_seed": int(args.random_seed),
        "morphology_projection": str(args.morphology_projection),
        "dt": float(args.dt),
        "recordStep": float(args.dt),
        "cvode_atol": float(args.cvode_atol),
        "sc_target_sections_all": sc_unique_sections,
        "pp_target_sections_all": pp_unique_sections,
        "sc_target_sites_all": [_site_to_dict(site) for site in base_theta_sc_sites],
        "pp_target_sites_all": [_site_to_dict(site) for site in base_theta_pp_sites],
        "max_connection_count": max_connection_count,
        "random_connection_draws": random_connection_draws,
        "dendritic_ican_section_count": len(dendritic_ican_sections),
        "dendritic_ican_sections": dendritic_ican_sections,
        "base_factorSynPYR": base_factor_syn_pyr,
        "base_thetaScSites": base_theta_sc_sites,
        "base_thetaPpSites": base_theta_pp_sites,
        "thetaBurstStart_ms": float(sim_cfg.thetaBurstStart),
        "thetaSpikeTimes_ms": list(sim_cfg.thetaSpikeTimes),
    }

    with (output_dir / "batch_config.json").open("w", encoding="utf-8") as handle:
        json.dump(batch_config, handle, indent=2, sort_keys=True)

    if args.dry_run:
        print(json.dumps(batch_config, indent=2, sort_keys=True))
        return

    results = []
    total_runs = len(random_connection_draws) * len(intensity_scales)
    run_index = 0
    for draw in random_connection_draws:
        for intensity_scale in intensity_scales:
            run_index += 1
            print(
                f"[{run_index}/{total_runs}] running connection_count={draw['connection_count']}, "
                f"intensity_scale={intensity_scale:.2f}"
            )
            results.append(
                _run_single_simulation(
                    args=args,
                    sim_module=sim_module,
                    sim_cfg=sim_cfg,
                    refresh_cfg_fn=refresh_cfg_fn,
                    cell_def=cell_def,
                    draw_index=draw["draw_index"],
                    connection_count=draw["connection_count"],
                    intensity_scale=intensity_scale,
                    active_sc_sites_input=draw["sc_sites"],
                    active_pp_sites_input=draw["pp_sites"],
                    dendritic_ican_sections=dendritic_ican_sections,
                    base_theta_sc_sites=base_theta_sc_sites,
                    base_theta_pp_sites=base_theta_pp_sites,
                    base_factor_syn_pyr=base_factor_syn_pyr,
                )
            )

    correlations = _build_batch_summary(results, intensity_scales=intensity_scales)
    batch_summary = {
        "batch_config": batch_config,
        "correlations": correlations,
        "results": results,
    }

    with (output_dir / "batch_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(batch_summary, handle, indent=2, sort_keys=True)
    _write_summary_csv(output_dir / "batch_summary.csv", results)

    print(json.dumps(correlations, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
