#!/usr/bin/env python3

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def load_series(path: Path) -> np.ndarray:
    values = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                values.append(float(s.split()[0]))
            except ValueError:
                continue
    if not values:
        raise ValueError(f"No numeric data found in {path}")
    return np.asarray(values, dtype=float)


def main():
    base = Path(__file__).resolve().parent
    t_path = base / "time.txt"
    v_path = base / "v.txt"

    if not t_path.exists() or not v_path.exists():
        raise FileNotFoundError("Expected lasttxt/time.txt and lasttxt/v.txt")

    t = load_series(t_path)
    v = load_series(v_path)

    n = min(t.size, v.size)
    if n == 0:
        raise ValueError("No overlapping samples between time and voltage data")
    if t.size != v.size:
        print(f"Warning: length mismatch (time={t.size}, v={v.size}); plotting first {n} points")

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    ax.plot(t[:n], v[:n], linewidth=1.1)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Voltage (mV)")
    ax.set_title("time.txt vs v.txt")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()

    out_png = base / "time_vs_v_from_time_v_txt.png"
    fig.savefig(out_png)
    plt.close(fig)
    print(f"Saved: {out_png}")


if __name__ == "__main__":
    main()
