from __future__ import annotations

try:
    import matplotlib

    matplotlib.use("Agg")

    from matplotlib import pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.patches import Circle

    HAS_MATPLOTLIB = True
except ModuleNotFoundError:
    matplotlib = None
    plt = None
    LineCollection = None
    Circle = None
    HAS_MATPLOTLIB = False

try:
    from PIL import Image, ImageDraw

    HAS_PILLOW = True
except ModuleNotFoundError:
    Image = None
    ImageDraw = None
    HAS_PILLOW = False

import argparse
import json
import math
import os
import tempfile
from collections import defaultdict
from pathlib import Path

RUNTIME_CACHE_DIR = Path(tempfile.gettempdir()) / "singleCellSuite-cache"
RUNTIME_CACHE_DIR.mkdir(parents=True, exist_ok=True)
MPL_CACHE_DIR = RUNTIME_CACHE_DIR / "matplotlib"
MPL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE_DIR))
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIR))

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CELLS_DIR = PROJECT_ROOT / "cells"
PROJECTION_AXES = {
    "xy": (0, 1),
    "xz": (0, 2),
    "yz": (1, 2),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load a cell JSON from cells/ and save its geometry as a PNG."
    )
    parser.add_argument(
        "cell",
        help="Cell name (for example PC2B or PC2B.json) or a direct path to a JSON file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output PNG path. Defaults to <cell>_geometry.png in the current directory.",
    )
    parser.add_argument(
        "--projection",
        choices=sorted(PROJECTION_AXES),
        default="xy",
        help="Projection used when the cell has pt3d coordinates (default: xy).",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="PNG resolution in dots per inch (default: 300).",
    )
    parser.add_argument(
        "--figsize",
        nargs=2,
        metavar=("WIDTH", "HEIGHT"),
        type=float,
        default=(8.0, 8.0),
        help="Figure size in inches (default: 8 8).",
    )
    parser.add_argument(
        "--title",
        help="Optional plot title. Defaults to the cell file stem plus the render mode.",
    )
    parser.add_argument(
        "--swap-axes",
        action="store_true",
        help="Swap the plotted x and y axes in the output image.",
    )
    parser.add_argument(
        "--flip-x",
        action="store_true",
        help="Mirror the plotted x axis in the output image.",
    )
    return parser


def resolve_cell_path(raw_value: str) -> Path:
    raw_path = Path(raw_value).expanduser()
    candidates = [raw_path, PROJECT_ROOT / raw_path]

    if raw_path.suffix != ".json":
        candidates.extend(
            [
                CELLS_DIR / raw_value,
                CELLS_DIR / f"{raw_value}.json",
                PROJECT_ROOT / f"{raw_value}.json",
            ]
        )

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()

    searched = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"Could not find cell model '{raw_value}'. Checked: {searched}")


def load_cell_model(cell_path: Path) -> dict:
    with cell_path.open("r", encoding="utf-8") as handle:
        model = json.load(handle)

    if not isinstance(model, dict) or "secs" not in model or not isinstance(model["secs"], dict):
        raise ValueError(f"{cell_path} is not a valid cell model JSON with a top-level 'secs' object.")

    return model


def numeric(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def section_points(section: dict) -> list[list[float]]:
    geom = section.get("geom", {})
    points = geom.get("pt3d")
    if not isinstance(points, list):
        return []
    return [point for point in points if isinstance(point, list) and len(point) >= 3]


def section_length(section: dict) -> float:
    geom = section.get("geom", {})
    length = numeric(geom.get("L"), default=-1.0)
    if length > 0:
        return length

    points = section_points(section)
    if len(points) < 2:
        return 1.0

    total = 0.0
    for start, end in zip(points, points[1:]):
        dx = numeric(end[0]) - numeric(start[0])
        dy = numeric(end[1]) - numeric(start[1])
        dz = numeric(end[2]) - numeric(start[2])
        total += math.sqrt(dx * dx + dy * dy + dz * dz)
    return total or 1.0


def section_diameter(section: dict) -> float:
    geom = section.get("geom", {})
    diameter = numeric(geom.get("diam"), default=-1.0)
    if diameter > 0:
        return diameter

    points = section_points(section)
    if not points:
        return 1.0

    diameters = [numeric(point[3], default=1.0) for point in points if len(point) >= 4]
    if diameters:
        return sum(diameters) / len(diameters)
    return 1.0


def line_width(diameter: float) -> float:
    return max(0.5, min(4.0, diameter * 0.35))


def swap_xy(point: tuple[float, float]) -> tuple[float, float]:
    return (numeric(point[1]), numeric(point[0]))


def swap_geometry(
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
    soma_circles: list[tuple[tuple[float, float], float]],
) -> tuple[list[tuple[tuple[float, float], tuple[float, float]]], list[tuple[tuple[float, float], float]]]:
    swapped_segments = [(swap_xy(start), swap_xy(end)) for start, end in segments]
    swapped_soma_circles = [(swap_xy(center), radius) for center, radius in soma_circles]
    return swapped_segments, swapped_soma_circles


def flip_x(point: tuple[float, float]) -> tuple[float, float]:
    return (-numeric(point[0]), numeric(point[1]))


def flip_x_geometry(
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
    soma_circles: list[tuple[tuple[float, float], float]],
) -> tuple[list[tuple[tuple[float, float], tuple[float, float]]], list[tuple[tuple[float, float], float]]]:
    flipped_segments = [(flip_x(start), flip_x(end)) for start, end in segments]
    flipped_soma_circles = [(flip_x(center), radius) for center, radius in soma_circles]
    return flipped_segments, flipped_soma_circles


def has_complete_pt3d(sections: dict[str, dict]) -> bool:
    return all(len(section_points(section)) >= 2 for section in sections.values())


def build_pt3d_geometry(sections: dict[str, dict], projection: str) -> tuple[list[tuple], list[float], list[tuple]]:
    axis_a, axis_b = PROJECTION_AXES[projection]
    segments: list[tuple] = []
    widths: list[float] = []
    soma_circles: list[tuple] = []

    for name, section in sections.items():
        points = section_points(section)
        if not points:
            continue

        if name.lower() == "soma":
            center = points[len(points) // 2]
            soma_circles.append(
                (
                    (numeric(center[axis_a]), numeric(center[axis_b])),
                    max(0.5, section_diameter(section) / 2.0),
                )
            )

        for start, end in zip(points, points[1:]):
            start_xy = (numeric(start[axis_a]), numeric(start[axis_b]))
            end_xy = (numeric(end[axis_a]), numeric(end[axis_b]))
            point_widths = []
            if len(start) >= 4:
                point_widths.append(numeric(start[3], default=section_diameter(section)))
            if len(end) >= 4:
                point_widths.append(numeric(end[3], default=section_diameter(section)))
            diameter = sum(point_widths) / len(point_widths) if point_widths else section_diameter(section)
            segments.append((start_xy, end_xy))
            widths.append(line_width(diameter))

    return segments, widths, soma_circles


def section_sort_key(name: str) -> tuple[int, str]:
    lower_name = name.lower()
    if "ori" in lower_name or "axon" in lower_name:
        return (0, lower_name)
    if lower_name == "soma":
        return (1, lower_name)
    return (2, lower_name)


def infer_branch_sign(name: str, parent_sign: int | None = None) -> int:
    lower_name = name.lower()

    if lower_name == "soma":
        return 0
    if "ori" in lower_name or "axon" in lower_name:
        return -1
    if "rad" in lower_name or "trunk" in lower_name or "lm" in lower_name or "apic" in lower_name:
        return 1
    if parent_sign is not None and parent_sign != 0:
        return parent_sign
    return 1


def build_schematic_geometry(sections: dict[str, dict]) -> tuple[list[tuple], list[float], list[tuple]]:
    parents: dict[str, str] = {}
    children: dict[str, list[str]] = defaultdict(list)

    for name, section in sections.items():
        topol = section.get("topol") or {}
        parent = topol.get("parentSec")
        if isinstance(parent, str) and parent in sections:
            parents[name] = parent
            children[parent].append(name)

    for name in children:
        children[name].sort(key=section_sort_key)

    roots = sorted((name for name in sections if name not in parents), key=section_sort_key)
    if not roots:
        roots = sorted(sections.keys(), key=section_sort_key)

    leaf_counts: dict[str, int] = {}

    def count_leaves(name: str) -> int:
        if name in leaf_counts:
            return leaf_counts[name]
        node_children = children.get(name, [])
        if not node_children:
            leaf_counts[name] = 1
        else:
            leaf_counts[name] = sum(count_leaves(child) for child in node_children)
        return leaf_counts[name]

    for root in roots:
        count_leaves(root)

    raw_x: dict[str, float] = {}
    next_leaf_position = 0

    def assign_x(name: str) -> None:
        nonlocal next_leaf_position
        node_children = children.get(name, [])
        if not node_children:
            raw_x[name] = float(next_leaf_position)
            next_leaf_position += 1
            return

        for child in node_children:
            assign_x(child)
        raw_x[name] = sum(raw_x[child] for child in node_children) / len(node_children)

    for root in roots:
        assign_x(root)

    min_x = min(raw_x.values())
    max_x = max(raw_x.values())
    center_x = (min_x + max_x) / 2.0

    nonzero_lengths = [section_length(section) for section in sections.values() if section_length(section) > 0]
    average_length = sum(nonzero_lengths) / len(nonzero_lengths) if nonzero_lengths else 20.0
    horizontal_spacing = max(15.0, min(80.0, average_length * 0.6))

    y_coords: dict[str, float] = {}
    branch_signs: dict[str, int] = {}

    def assign_y(name: str, parent: str | None = None) -> None:
        if parent is None:
            branch_signs[name] = infer_branch_sign(name)
            if name.lower() == "soma":
                y_coords[name] = 0.0
            else:
                y_coords[name] = branch_signs[name] * section_length(sections[name])
        else:
            sign = infer_branch_sign(name, branch_signs[parent])
            branch_signs[name] = sign
            y_coords[name] = y_coords[parent] + sign * section_length(sections[name])

        for child in children.get(name, []):
            assign_y(child, name)

    for root in roots:
        assign_y(root)

    x_coords = {
        name: (position - center_x) * horizontal_spacing
        for name, position in raw_x.items()
    }

    segments: list[tuple] = []
    widths: list[float] = []
    soma_circles: list[tuple] = []

    for name, section in sections.items():
        if name.lower() == "soma":
            radius = max(section_diameter(section), section_length(section)) / 2.0
            soma_circles.append(((x_coords[name], y_coords[name]), max(2.0, radius)))
            continue

        parent = parents.get(name)
        if parent is None:
            start = (x_coords[name], 0.0)
        else:
            start = (x_coords[parent], y_coords[parent])
        end = (x_coords[name], y_coords[name])
        segments.append((start, end))
        widths.append(line_width(section_diameter(section)))

    if not soma_circles and roots:
        first_root = roots[0]
        soma_circles.append(((x_coords[first_root], 0.0), 3.0))

    return segments, widths, soma_circles


def render_plot(
    cell_path: Path,
    output_path: Path,
    segments: list[tuple],
    widths: list[float],
    soma_circles: list[tuple],
    mode: str,
    projection: str,
    swap_axes: bool,
    figsize: tuple[float, float],
    dpi: int,
    title: str | None,
) -> None:
    if HAS_MATPLOTLIB:
        render_plot_matplotlib(
            cell_path=cell_path,
            output_path=output_path,
            segments=segments,
            widths=widths,
            soma_circles=soma_circles,
            mode=mode,
            projection=projection,
            swap_axes=swap_axes,
            figsize=figsize,
            dpi=dpi,
            title=title,
        )
        return

    if HAS_PILLOW:
        render_plot_pillow(
            cell_path=cell_path,
            output_path=output_path,
            segments=segments,
            widths=widths,
            soma_circles=soma_circles,
            mode=mode,
            projection=projection,
            swap_axes=swap_axes,
            figsize=figsize,
            dpi=dpi,
            title=title,
        )
        return

    raise RuntimeError(
        "No plotting backend available. Install either matplotlib or Pillow to generate PNG geometry plots."
    )


def active_backend_name() -> str:
    if HAS_MATPLOTLIB:
        return "matplotlib"
    if HAS_PILLOW:
        return "Pillow"
    return "none"


def render_plot_matplotlib(
    cell_path: Path,
    output_path: Path,
    segments: list[tuple],
    widths: list[float],
    soma_circles: list[tuple],
    mode: str,
    projection: str,
    swap_axes: bool,
    figsize: tuple[float, float],
    dpi: int,
    title: str | None,
) -> None:
    figure, axis = plt.subplots(figsize=figsize, constrained_layout=True)

    if segments:
        collection = LineCollection(
            segments,
            linewidths=widths,
            colors="#0f172a",
            capstyle="round",
            joinstyle="round",
        )
        axis.add_collection(collection)

    for center, radius in soma_circles:
        soma = Circle(center, radius=radius, facecolor="#94a3b8", edgecolor="#0f172a", linewidth=1.0)
        axis.add_patch(soma)

    axis.autoscale()
    axis.margins(0.08)
    axis.set_aspect("equal", adjustable="datalim")
    axis.grid(False)

    if mode == "pt3d":
        axis_a, axis_b = projection
        if swap_axes:
            axis_a, axis_b = axis_b, axis_a
        axis.set_xlabel(f"{axis_a.upper()} (um)")
        axis.set_ylabel(f"{axis_b.upper()} (um)")
        default_title = f"{cell_path.stem} geometry ({projection})"
    else:
        if swap_axes:
            axis.set_xlabel("Path length from root (um)")
            axis.set_ylabel("Branch spread (um)")
        else:
            axis.set_xlabel("Branch spread (um)")
            axis.set_ylabel("Path length from root (um)")
        default_title = f"{cell_path.stem} geometry (schematic)"

    axis.set_title(title or default_title)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(figure)


def render_plot_pillow(
    cell_path: Path,
    output_path: Path,
    segments: list[tuple],
    widths: list[float],
    soma_circles: list[tuple],
    mode: str,
    projection: str,
    swap_axes: bool,
    figsize: tuple[float, float],
    dpi: int,
    title: str | None,
) -> None:
    plot_title = title or (
        f"{cell_path.stem} geometry ({projection})" if mode == "pt3d" else f"{cell_path.stem} geometry (schematic)"
    )

    pixel_width = max(400, int(figsize[0] * dpi))
    pixel_height = max(400, int(figsize[1] * dpi))
    margin = max(30, int(min(pixel_width, pixel_height) * 0.08))
    title_band = 32

    xs: list[float] = []
    ys: list[float] = []
    for start, end in segments:
        xs.extend([numeric(start[0]), numeric(end[0])])
        ys.extend([numeric(start[1]), numeric(end[1])])
    for center, radius in soma_circles:
        cx = numeric(center[0])
        cy = numeric(center[1])
        rr = numeric(radius)
        xs.extend([cx - rr, cx + rr])
        ys.extend([cy - rr, cy + rr])

    if not xs or not ys:
        raise RuntimeError(f"{cell_path} did not contain any drawable geometry.")

    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)

    span_x = max(max_x - min_x, 1.0)
    span_y = max(max_y - min_y, 1.0)
    drawable_width = max(1, pixel_width - 2 * margin)
    drawable_height = max(1, pixel_height - 2 * margin - title_band)
    scale = min(drawable_width / span_x, drawable_height / span_y)

    x_offset = margin + (drawable_width - span_x * scale) / 2.0
    y_offset = margin + title_band + (drawable_height - span_y * scale) / 2.0

    def to_pixels(point: tuple[float, float]) -> tuple[int, int]:
        x_value = x_offset + (numeric(point[0]) - min_x) * scale
        y_value = y_offset + (max_y - numeric(point[1])) * scale
        return (int(round(x_value)), int(round(y_value)))

    image = Image.new("RGB", (pixel_width, pixel_height), color="white")
    draw = ImageDraw.Draw(image)

    if plot_title:
        draw.text((margin, margin // 2), plot_title, fill="#0f172a")

    for (start, end), width in zip(segments, widths):
        draw.line([to_pixels(start), to_pixels(end)], fill="#0f172a", width=max(1, int(round(width * scale * 0.12))))

    for center, radius in soma_circles:
        cx, cy = to_pixels(center)
        radius_px = max(2, int(round(numeric(radius) * scale)))
        bbox = [(cx - radius_px, cy - radius_px), (cx + radius_px, cy + radius_px)]
        draw.ellipse(bbox, fill="#94a3b8", outline="#0f172a", width=1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        cell_path = resolve_cell_path(args.cell)
        model = load_cell_model(cell_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    output_path = args.output or Path.cwd() / f"{cell_path.stem}_geometry.png"
    sections = model["secs"]

    if has_complete_pt3d(sections):
        segments, widths, soma_circles = build_pt3d_geometry(sections, args.projection)
        mode = "pt3d"
    else:
        segments, widths, soma_circles = build_schematic_geometry(sections)
        mode = "schematic"

    if not segments and not soma_circles:
        parser.error(f"{cell_path} did not contain any drawable geometry.")

    if args.swap_axes:
        segments, soma_circles = swap_geometry(segments, soma_circles)
    if args.flip_x:
        segments, soma_circles = flip_x_geometry(segments, soma_circles)

    try:
        render_plot(
            cell_path=cell_path,
            output_path=output_path,
            segments=segments,
            widths=widths,
            soma_circles=soma_circles,
            mode=mode,
            projection=args.projection,
            swap_axes=args.swap_axes,
            figsize=tuple(args.figsize),
            dpi=args.dpi,
            title=args.title,
        )
    except RuntimeError as exc:
        parser.error(str(exc))

    transforms = []
    if args.swap_axes:
        transforms.append("swapped x/y axes")
    if args.flip_x:
        transforms.append("flipped x axis")
    transform_note = f" with {', '.join(transforms)}" if transforms else ""
    print(f"Saved {mode} geometry plot{transform_note} to {output_path.resolve()} using {active_backend_name()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
