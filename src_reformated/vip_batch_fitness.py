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
    vip_spike_times = _extract_vip_spike_times(simData, vip_gids)
    if not vip_spike_times and target_spikes_per_cycle > 0:
        return float(missing_vip_penalty)

    no_ms_counts = _count_spikes_in_windows(vip_spike_times, no_ms_windows)
    ms_counts = _count_spikes_in_windows(vip_spike_times, ms_windows)
    outside_spikes = _count_spikes_outside_windows(vip_spike_times, list(no_ms_windows) + list(ms_windows))

    no_ms_penalty = no_ms_weight * sum(count ** 2 for count in no_ms_counts)
    ms_penalty = ms_weight * sum((count - target_spikes_per_cycle) ** 2 for count in ms_counts)
    outside_penalty = outside_weight * outside_spikes

    return float(no_ms_penalty + ms_penalty + outside_penalty)
