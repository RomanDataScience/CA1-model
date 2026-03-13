def _build_theta_sites():
    sites = []
    for index in range(6):
        sites.append((f"trunk_{10 + index}", 0.5, 1.0, "SC"))
    for index in range(6):
        sites.append((f"apic_{27 + index}", 0.5, 1.0, "SC"))
    for index in range(4):
        sites.append((f"apic_{28 + index}", 0.2, 1.0, "SC"))
    for index in range(4):
        sites.append((f"apic_{28 + index}", 0.8, 1.0, "SC"))
    for index in range(20):
        sites.append((f"apic_{40 + index}", 0.8, 2.0, "PP"))
    return sites


def _build_theta_spike_times(cycle_starts, intra_burst_isi, spikes_per_burst):
    return [
        cycle_start + spike * intra_burst_isi
        for cycle_start in cycle_starts
        for spike in range(spikes_per_burst)
    ]


def _build_cycle_windows(cycle_starts, cycle_duration):
    return [(cycle_start, cycle_start + cycle_duration) for cycle_start in cycle_starts]


def _build_ms_train(ms_start, ms_stop, ms_isi):
    spike_times = []
    spike_time = ms_start
    while spike_time <= ms_stop:
        spike_times.append(spike_time)
        spike_time += ms_isi
    spike_times.append(spike_time)
    return spike_times


def _last_theta_burst_end(cycle_starts, intra_burst_isi, spikes_per_burst):
    if not cycle_starts:
        return 0.0
    return cycle_starts[-1] + max(0, spikes_per_burst - 1) * intra_burst_isi


def apply_derived_config(cfg):
    cfg.thetaBurstStart = cfg.Transient
    cfg.thetaCycleWindows = []
    cfg.vipBatchNoMsWindows = []
    cfg.vipBatchMsWindows = []

    if getattr(cfg, "vipBatchProtocol", False):
        no_ms_cycle_starts = [
            cfg.thetaBurstStart + cycle_index * cfg.thetaInterBurstISI
            for cycle_index in range(cfg.vipBatchNoMsCycles)
        ]
        ms_block_start = (
            cfg.thetaBurstStart
            + cfg.vipBatchNoMsCycles * cfg.thetaInterBurstISI
            + cfg.vipBatchInterPhaseGap
        )
        ms_cycle_starts = [
            ms_block_start + cycle_index * cfg.thetaInterBurstISI
            for cycle_index in range(cfg.vipBatchMsCycles)
        ]

        cfg.thetaSpikeTimes = _build_theta_spike_times(
            no_ms_cycle_starts + ms_cycle_starts,
            cfg.thetaIntraBurstISI,
            cfg.thetaSpikesPerBurst,
        )
        cfg.thetaCycleWindows = _build_cycle_windows(
            no_ms_cycle_starts + ms_cycle_starts,
            cfg.thetaInterBurstISI,
        )
        cfg.vipBatchNoMsWindows = _build_cycle_windows(no_ms_cycle_starts, cfg.thetaInterBurstISI)
        cfg.vipBatchMsWindows = _build_cycle_windows(ms_cycle_starts, cfg.thetaInterBurstISI)
        cfg.duration = (
            ms_block_start
            + cfg.vipBatchMsCycles * cfg.thetaInterBurstISI
            + cfg.thetaTailBuffer
        )
        cfg.MSISI = 1000.0 / cfg.MSRateHz
        cfg.MSPhaseRef = ms_block_start - cfg.MSLeadBeforeTheta
        cfg.MSIstart = cfg.MSPhaseRef
        ms_last_burst_end = _last_theta_burst_end(
            ms_cycle_starts,
            cfg.thetaIntraBurstISI,
            cfg.thetaSpikesPerBurst,
        )
        cfg.MS_train = _build_ms_train(cfg.MSIstart, ms_last_burst_end, cfg.MSISI)
    else:
        cfg.duration = cfg.Transient + cfg.thetaCycles * cfg.thetaInterBurstISI + cfg.thetaTailBuffer
        cycle_starts = [
            cfg.thetaBurstStart + burst * cfg.thetaInterBurstISI
            for burst in range(cfg.thetaCycles)
        ]
        cfg.thetaSpikeTimes = _build_theta_spike_times(
            cycle_starts,
            cfg.thetaIntraBurstISI,
            cfg.thetaSpikesPerBurst,
        )
        cfg.thetaCycleWindows = _build_cycle_windows(cycle_starts, cfg.thetaInterBurstISI)
        cfg.MSISI = 1000.0 / cfg.MSRateHz
        cfg.MSPhaseRef = cfg.thetaBurstStart - cfg.MSLeadBeforeTheta
        cfg.MSIstart = cfg.MSPhaseRef
        theta_last_burst_end = _last_theta_burst_end(
            cycle_starts,
            cfg.thetaIntraBurstISI,
            cfg.thetaSpikesPerBurst,
        )
        cfg.MS_train = _build_ms_train(cfg.MSIstart, theta_last_burst_end, cfg.MSISI)

    cfg.thetaSites = _build_theta_sites()
    cfg.thetaScSites = [
        (sec, loc, nmda_mult)
        for sec, loc, nmda_mult, group in cfg.thetaSites
        if group == "SC"
    ]
    cfg.thetaPpSites = [
        (sec, loc, nmda_mult)
        for sec, loc, nmda_mult, group in cfg.thetaSites
        if group == "PP"
    ]

    cfg.thetaAMPAWeightPYR = cfg.thetaSynScalePYR * cfg.thetaAMPAUnitWeight * cfg.factorSynPYR
    cfg.thetaNMDAWeightPYR = cfg.thetaSynScalePYR * cfg.thetaNMDAUnitWeight * cfg.factorSynPYR
    cfg.thetaAMPAWeightVIP = cfg.thetaSynScaleVIP * cfg.thetaAMPAUnitWeight * cfg.factorSynVIP
    cfg.thetaNMDAWeightVIP = cfg.thetaSynScaleVIP * cfg.thetaNMDAUnitWeight * cfg.factorSynVIP

    cfg.simLabel = (
        f"{cfg.simLabelBase}"
        f"_Control{cfg.applyControlPC2B}"
        f"_VIPx{cfg.factorSynVIP}"
        f"_GLU{cfg.PYROLMweight}"
        f"_GABAOLM{cfg.OLMPYRweight}"
        f"_GABAVIP{cfg.VIPOLMweight}"
        f"_Achinput{cfg.nMSweight}"
    )

    time_range = [0, cfg.duration]
    record_exclude = set(cfg.recordExcludePops)
    cfg.recordCells = [(pop, 0) for pop in cfg.allPops if pop not in record_exclude]

    if getattr(cfg, "enableDefaultAnalysis", True):
        if not isinstance(getattr(cfg, "analysis", None), dict):
            cfg.analysis = {}
        cfg.analysis["plotRaster"] = {
            "include": list(cfg.allPops),
            "timeRange": time_range,
            **cfg.plotRasterDefaults,
        }
        cfg.analysis["plotSpikeHist"] = {
            "include": list(cfg.allPops),
            "timeRange": time_range,
            **cfg.plotSpikeHistDefaults,
        }
        cfg.analysis["plotTraces"] = {
            "include": list(cfg.recordCells),
            "timeRange": time_range,
            **cfg.plotTracesDefaults,
        }
    else:
        cfg.analysis = {}
