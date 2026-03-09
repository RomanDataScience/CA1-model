#!/usr/bin/env python3

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def _is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False


def load_trace(path: Path):
    # Supports both:
    # 1) HOC Vector.printf style:
    #    line 1: label:...
    #    line 2: row count
    #    line 3+: time value
    # 2) Plain two-column data from line 1
    with path.open("r", encoding="utf-8") as f:
        first = f.readline().strip()
        second = f.readline().strip()

    label = "value"
    skiprows = 0
    if first.lower().startswith("label:"):
        label = first.split(":", 1)[1] or "value"
        skiprows = 2
    elif not (_is_number(first.split()[0] if first.split() else "") and _is_number(second.split()[0] if second.split() else "")):
        skiprows = 1

    data = np.loadtxt(path, skiprows=skiprows)
    data = np.atleast_2d(data)
    if data.ndim != 2 or data.shape[1] < 2:
        raise ValueError(f"Unexpected format in {path}")
    return data[:, 0], data[:, 1], label


def plot_trace(txt_file: Path):
    t, y, label = load_trace(txt_file)

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    ax.plot(t, y, linewidth=1.1)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel(label)
    ax.set_title(txt_file.stem)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()

    out_png = txt_file.with_name(f"{txt_file.stem}_time_vs_y.png")
    fig.savefig(out_png)
    plt.close(fig)
    print(f"Saved: {out_png}")


def main():
    base = Path(__file__).resolve().parent
    input_files = sorted(base.glob("*.txt"))
    if not input_files:
        raise FileNotFoundError(f"No .txt files found in {base}")

    for txt in input_files:
        plot_trace(txt)


if __name__ == "__main__":
    main()
