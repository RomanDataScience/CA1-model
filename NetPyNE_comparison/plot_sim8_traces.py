from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent / "results" / "latest"
DEFAULT_HOC_CSV = DEFAULT_RESULTS_DIR / "sim8_hoc_voltage.csv"
DEFAULT_NETPYNE_CSV = DEFAULT_RESULTS_DIR / "sim8_netpyne_voltage.csv"
DEFAULT_JSON_CSV = DEFAULT_RESULTS_DIR / "sim8_json_voltage.csv"
DEFAULT_HOC_CURRENT_CSV = DEFAULT_RESULTS_DIR / "sim8_hoc_current.csv"
DEFAULT_NETPYNE_CURRENT_CSV = DEFAULT_RESULTS_DIR / "sim8_netpyne_current.csv"
DEFAULT_JSON_CURRENT_CSV = DEFAULT_RESULTS_DIR / "sim8_json_current.csv"
DEFAULT_OUTPUT_PNG = DEFAULT_RESULTS_DIR / "sim8_voltage_overlay.png"


def _read_trace_csv(csv_path: Path, value_label: str) -> tuple[list[float], list[float]]:
    if not csv_path.is_file():
        raise FileNotFoundError(f"Missing trace CSV: {csv_path}")

    time_ms: list[float] = []
    trace_values: list[float] = []

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        expected_columns = ["time_ms", value_label]
        if reader.fieldnames != expected_columns:
            raise ValueError(
                f"Unexpected columns in {csv_path}. "
                f"Expected {expected_columns}, found {reader.fieldnames}."
            )

        for row in reader:
            time_ms.append(float(row["time_ms"]))
            trace_values.append(float(row[value_label]))

    if not time_ms:
        raise ValueError(f"Trace CSV is empty: {csv_path}")

    return time_ms, trace_values


def plot_traces(
    hoc_voltage_csv: Path,
    netpyne_voltage_csv: Path,
    json_voltage_csv: Path,
    hoc_current_csv: Path,
    netpyne_current_csv: Path,
    json_current_csv: Path,
    output_png: Path,
) -> Path:
    hoc_time_ms, hoc_voltage_mv = _read_trace_csv(hoc_voltage_csv, "voltage_mv")
    netpyne_time_ms, netpyne_voltage_mv = _read_trace_csv(netpyne_voltage_csv, "voltage_mv")
    json_time_ms, json_voltage_mv = _read_trace_csv(json_voltage_csv, "voltage_mv")
    hoc_current_time_ms, hoc_current_na = _read_trace_csv(hoc_current_csv, "current_nA")
    netpyne_current_time_ms, netpyne_current_na = _read_trace_csv(netpyne_current_csv, "current_nA")
    json_current_time_ms, json_current_na = _read_trace_csv(json_current_csv, "current_nA")

    output_png.parent.mkdir(parents=True, exist_ok=True)

    figure, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    axes[0].plot(hoc_time_ms, hoc_voltage_mv, label="HOC Figure8control", linewidth=1.0)
    axes[0].plot(
        netpyne_time_ms,
        netpyne_voltage_mv,
        label="NetPyNE imported cell",
        linewidth=1.0,
        alpha=0.85,
    )
    axes[0].plot(
        json_time_ms,
        json_voltage_mv,
        label="NetPyNE from PC2B.json",
        linewidth=1.0,
        alpha=0.85,
    )
    axes[0].set_ylabel("Voltage (mV)")
    axes[0].set_title("Figure 8 Control: HOC vs NetPyNE (Imported and JSON)")
    axes[0].legend(loc="best")
    axes[0].grid(True, alpha=0.2)

    axes[1].plot(hoc_current_time_ms, hoc_current_na, label="HOC Figure8control", linewidth=1.0)
    axes[1].plot(
        netpyne_current_time_ms,
        netpyne_current_na,
        label="NetPyNE imported cell",
        linewidth=1.0,
        alpha=0.85,
    )
    axes[1].plot(
        json_current_time_ms,
        json_current_na,
        label="NetPyNE from PC2B.json",
        linewidth=1.0,
        alpha=0.85,
    )
    axes[1].set_xlabel("Time (ms)")
    axes[1].set_ylabel("Current (nA)")
    axes[1].legend(loc="best")
    axes[1].grid(True, alpha=0.2)

    figure.tight_layout()
    figure.savefig(output_png, dpi=200)
    plt.close(figure)

    return output_png


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Plot the HOC and NetPyNE Figure 8 voltage and current traces from CSV files."
    )
    parser.add_argument(
        "--hoc-csv",
        type=Path,
        default=DEFAULT_HOC_CSV,
        help="Path to the HOC voltage CSV (columns: time_ms, voltage_mv).",
    )
    parser.add_argument(
        "--netpyne-csv",
        type=Path,
        default=DEFAULT_NETPYNE_CSV,
        help="Path to the NetPyNE voltage CSV (columns: time_ms, voltage_mv).",
    )
    parser.add_argument(
        "--hoc-current-csv",
        type=Path,
        default=DEFAULT_HOC_CURRENT_CSV,
        help="Path to the HOC current CSV (columns: time_ms, current_nA).",
    )
    parser.add_argument(
        "--netpyne-current-csv",
        type=Path,
        default=DEFAULT_NETPYNE_CURRENT_CSV,
        help="Path to the NetPyNE current CSV (columns: time_ms, current_nA).",
    )
    parser.add_argument(
        "--json-csv",
        type=Path,
        default=DEFAULT_JSON_CSV,
        help="Path to the PC2B.json voltage CSV (columns: time_ms, voltage_mv).",
    )
    parser.add_argument(
        "--json-current-csv",
        type=Path,
        default=DEFAULT_JSON_CURRENT_CSV,
        help="Path to the PC2B.json current CSV (columns: time_ms, current_nA).",
    )
    parser.add_argument(
        "--output-png",
        type=Path,
        default=DEFAULT_OUTPUT_PNG,
        help="Path where the combined overlay PNG will be written.",
    )
    args = parser.parse_args(argv)

    try:
        output_png = plot_traces(
            args.hoc_csv,
            args.netpyne_csv,
            args.json_csv,
            args.hoc_current_csv,
            args.netpyne_current_csv,
            args.json_current_csv,
            args.output_png,
        )
    except Exception as exc:
        print(f"Plotting failed: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote overlay plot to: {output_png.resolve()}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
