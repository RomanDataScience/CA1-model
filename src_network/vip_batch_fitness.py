def build_vip_gid_range(pyr_cells=1, olm_cells=1, vip_cells=1):
    vip_gid_start = int(pyr_cells) + int(olm_cells)
    vip_gid_stop = vip_gid_start + int(vip_cells)
    return list(range(vip_gid_start, vip_gid_stop))


def build_vip_protocol_windows(
    transient,
    inter_burst_isi,
    no_ms_cycles,
    ms_cycles,
    inter_phase_gap,
):
    no_ms_windows = [
        (
            transient + cycle_index * inter_burst_isi,
            transient + (cycle_index + 1) * inter_burst_isi,
        )
        for cycle_index in range(int(no_ms_cycles))
    ]

    ms_block_start = transient + int(no_ms_cycles) * inter_burst_isi + inter_phase_gap
    ms_windows = [
        (
            ms_block_start + cycle_index * inter_burst_isi,
            ms_block_start + (cycle_index + 1) * inter_burst_isi,
        )
        for cycle_index in range(int(ms_cycles))
    ]
    return no_ms_windows, ms_windows


def _extract_vip_spike_times(simData, vip_gids):
    spike_times = simData.get("spkt", [])
    spike_gids = simData.get("spkid", [])
    vip_gid_set = {int(gid) for gid in vip_gids}
    return [float(time) for time, gid in zip(spike_times, spike_gids) if int(gid) in vip_gid_set]


def _count_spikes_in_windows(spike_times, windows):
    return [
        sum(window_start <= spike_time < window_stop for spike_time in spike_times)
        for window_start, window_stop in windows
    ]


def _count_spikes_outside_windows(spike_times, windows):
    return sum(
        not any(window_start <= spike_time < window_stop for window_start, window_stop in windows)
        for spike_time in spike_times
    )


def summarize_vip_theta_response(
    simData,
    vip_gids,
    no_ms_windows,
    ms_windows,
    target_spikes_per_cycle=4,
    no_ms_weight=25.0,
    ms_weight=5.0,
    outside_weight=100.0,
    missing_vip_penalty=1e6,
):
    vip_spike_times = _extract_vip_spike_times(simData, vip_gids)
    no_ms_counts = _count_spikes_in_windows(vip_spike_times, no_ms_windows)
    ms_counts = _count_spikes_in_windows(vip_spike_times, ms_windows)
    outside_spikes = _count_spikes_outside_windows(vip_spike_times, list(no_ms_windows) + list(ms_windows))

    if not vip_spike_times and target_spikes_per_cycle > 0:
        return {
            "loss": float(missing_vip_penalty),
            "vip_total_spikes": 0,
            "outside_spikes": 0,
            "mean_no_ms_spikes": 0.0,
            "mean_ms_spikes": 0.0,
            "no_ms_counts": no_ms_counts,
            "ms_counts": ms_counts,
        }

    no_ms_penalty = no_ms_weight * sum(count ** 2 for count in no_ms_counts)
    ms_penalty = ms_weight * sum((count - target_spikes_per_cycle) ** 2 for count in ms_counts)
    outside_penalty = outside_weight * outside_spikes

    return {
        "loss": float(no_ms_penalty + ms_penalty + outside_penalty),
        "vip_total_spikes": len(vip_spike_times),
        "outside_spikes": int(outside_spikes),
        "mean_no_ms_spikes": float(sum(no_ms_counts) / len(no_ms_counts)) if no_ms_counts else 0.0,
        "mean_ms_spikes": float(sum(ms_counts) / len(ms_counts)) if ms_counts else 0.0,
        "no_ms_counts": no_ms_counts,
        "ms_counts": ms_counts,
    }


def combine_vip_phase_summaries(
    no_ms_summary,
    ms_summary,
    target_spikes_per_cycle=4,
    ms_gain_weight=20.0,
):
    mean_no_ms_spikes = float(no_ms_summary.get("mean_no_ms_spikes", 0.0))
    mean_ms_spikes = float(ms_summary.get("mean_ms_spikes", 0.0))
    firing_rate_gain = mean_ms_spikes - mean_no_ms_spikes
    gain_penalty = ms_gain_weight * max(0.0, target_spikes_per_cycle - firing_rate_gain) ** 2
    total_loss = float(no_ms_summary["loss"] + ms_summary["loss"] + gain_penalty)

    return {
        "loss": total_loss,
        "loss_ms_off": float(no_ms_summary["loss"]),
        "loss_ms_on": float(ms_summary["loss"]),
        "gain_penalty": float(gain_penalty),
        "firing_rate_gain": float(firing_rate_gain),
        "vip_spikes_ms_off": int(no_ms_summary["vip_total_spikes"]),
        "vip_spikes_ms_on": int(ms_summary["vip_total_spikes"]),
        "outside_spikes_ms_off": int(no_ms_summary["outside_spikes"]),
        "outside_spikes_ms_on": int(ms_summary["outside_spikes"]),
        "mean_spikes_per_cycle_ms_off": mean_no_ms_spikes,
        "mean_spikes_per_cycle_ms_on": mean_ms_spikes,
    }


def vip_theta_fitness(
    simData,
    vip_gids,
    no_ms_windows,
    ms_windows,
    target_spikes_per_cycle=4,
    no_ms_weight=25.0,
    ms_weight=5.0,
    outside_weight=100.0,
    missing_vip_penalty=1e6,
):
    summary = summarize_vip_theta_response(
        simData=simData,
        vip_gids=vip_gids,
        no_ms_windows=no_ms_windows,
        ms_windows=ms_windows,
        target_spikes_per_cycle=target_spikes_per_cycle,
        no_ms_weight=no_ms_weight,
        ms_weight=ms_weight,
        outside_weight=outside_weight,
        missing_vip_penalty=missing_vip_penalty,
    )
    return float(summary["loss"])
