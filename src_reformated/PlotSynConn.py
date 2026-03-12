import matplotlib

matplotlib.use("Agg")

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from netpyne import sim
from netpyne.support import morphology as morph
from neuron import h

from netParams import cfg, netParams


def _pre_pop_label(conn, gid_to_pop):
    pre_gid = conn.get("preGid")
    if pre_gid is None:
        pre_label = conn.get("preLabel")
        return str(pre_label) if pre_label else "NetStim"
    return gid_to_pop.get(pre_gid, "unknown")


def _line_width_from_diam(diam):
    # Inspired by singleCellSuite/plotGeometry.py: line_width(diameter)
    return max(0.5, min(4.0, float(diam) * 0.35))


def _soma_center_xyz(cell):
    # In this project soma is expected to be named "soma" (legacy fallback: soma_0).
    if "soma" in cell.secs:
        sec_hobj = cell.secs["soma"]["hObj"]
    elif "soma_0" in cell.secs:
        sec_hobj = cell.secs["soma_0"]["hObj"]
    else:
        return None

    n3d = int(h.n3d(sec=sec_hobj))
    if n3d <= 0:
        return None

    xs = [h.x3d(i, sec=sec_hobj) for i in range(n3d)]
    ys = [h.y3d(i, sec=sec_hobj) for i in range(n3d)]
    zs = [h.z3d(i, sec=sec_hobj) for i in range(n3d)]
    return (sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs))


def _plot_syn_contacts_for_pop(post_pop, out_dir):
    post_cells = sim.getCellsList([post_pop])
    fig, _ = sim.analysis.plotShape(includePost=[post_pop], showSyns=False, saveFig=False)

    ax3d = None
    for ax in fig.axes:
        if hasattr(ax, "get_zlim3d"):
            ax3d = ax
            break
    if ax3d is None:
        fig.savefig(out_dir / f"{post_pop}_syn_contacts.png", dpi=300, bbox_inches="tight")
        plt.close(fig)
        return

    # Rotate PC2B view by -90 degrees for plotting.
    if post_pop == "PC2B":
        try:
            elev = float(getattr(ax3d, "elev", 90.0))
            azim = float(getattr(ax3d, "azim", -90.0))
            ax3d.view_init(elev=elev, azim=azim - 90.0)
        except Exception:
            pass

    # Morphology styling inspired by singleCellSuite/plotGeometry.py:
    # clamp linewidths + round caps/joints to avoid blocky soma rendering.
    for line in ax3d.lines:
        try:
            orig_lw = float(line.get_linewidth())
            new_lw = _line_width_from_diam(orig_lw)
            # Extra shrink for very thick sections (typically soma).
            if orig_lw >= 8.0:
                new_lw = max(0.4, min(1.0, new_lw * 0.25))
            line.set_linewidth(new_lw)
            line.set_solid_capstyle("round")
            line.set_solid_joinstyle("round")
            line.set_antialiased(True)
        except Exception:
            pass

    plt.figure(fig.number)
    plt.sca(ax3d)

    gid_to_pop = {cell.gid: cell.tags.get("pop", "unknown") for cell in sim.net.cells}

    pre_pops = sorted(
        {
            _pre_pop_label(conn, gid_to_pop)
            for cell in post_cells
            for conn in cell.conns
            if conn.get("sec") is not None and conn.get("loc") is not None
        }
    )

    palette = [
        "#e41a1c",
        "#377eb8",
        "#4daf4a",
        "#ff7f00",
        "#984ea3",
        "#a65628",
        "#f781bf",
        "#999999",
    ]
    color_by_pop = {pop: palette[i % len(palette)] for i, pop in enumerate(pre_pops)}
    marker_by_pop = {pop: "o" for pop in pre_pops}
    if post_pop == "PC2B":
        for pop in pre_pops:
            if str(pop).upper() == "OLM":
                marker_by_pop[pop] = "*"

    for cell in post_cells:
        for conn in cell.conns:
            sec_name = conn.get("sec")
            loc = conn.get("loc")
            if sec_name not in cell.secs or loc is None:
                continue

            pre_pop = _pre_pop_label(conn, gid_to_pop)
            sec_hobj = cell.secs[sec_name]["hObj"]
            marker = marker_by_pop.get(pre_pop, "o")
            morph.mark_locations(
                h,
                sec_hobj,
                float(loc),
                markspec=marker,
                color=color_by_pop.get(pre_pop, "#000000"),
                markersize=1.5 if marker == "*" else 1.0,
            )

    # Explicit soma position marker (high-contrast red X).
    for cell in post_cells:
        soma_xyz = _soma_center_xyz(cell)
        if soma_xyz is None:
            continue
        ax3d.scatter(
            [soma_xyz[0]],
            [soma_xyz[1]],
            [soma_xyz[2]],
            marker="^",
            s=3,
            c="tab:orange",
            linewidths=1.2,
            depthshade=False,
        )

    handles = [
        Line2D(
            [0],
            [0],
            marker=marker_by_pop.get(p, "o"),
            color="w",
            markerfacecolor=color_by_pop[p],
            label=p,
            markersize=8,
        )
        for p in pre_pops
    ]
    handles.append(
        Line2D([0], [0], marker="^", color="tab:orange", label="soma", markersize=8, linewidth=0)
    )
    if handles:
        ax3d.legend(handles=handles, loc="upper left", fontsize=8)

    # Hide axes/ticks/frame to keep morphology-only view.
    ax3d.set_axis_off()

    fig.savefig(out_dir / f"{post_pop}_syn_contacts.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main():
    out_dir = Path(cfg.saveFolder) / "syn_contacts"
    out_dir.mkdir(parents=True, exist_ok=True)

    sim.initialize(simConfig=cfg, netParams=netParams)
    sim.net.createPops()
    sim.net.createCells()
    sim.net.connectCells()
    sim.net.addStims()

    if sim.rank == 0:
        _plot_syn_contacts_for_pop("PC2B", out_dir)
        _plot_syn_contacts_for_pop("OLM", out_dir)
        _plot_syn_contacts_for_pop("VIP", out_dir)
        print(f"Saved synaptic contact plots in: {out_dir}")


if __name__ == "__main__":
    main()
