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


def apply_derived_config(cfg):
    cfg.thetaBurstStart = cfg.Transient
    cfg.duration = cfg.Transient + cfg.thetaCycles * cfg.thetaInterBurstISI + 200.0

    cfg.thetaSpikeTimes = [
        cfg.thetaBurstStart + burst * cfg.thetaInterBurstISI + spike * cfg.thetaIntraBurstISI
        for burst in range(cfg.thetaCycles)
        for spike in range(cfg.thetaSpikesPerBurst)
    ]

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

    cfg.MSISI = 1000.0 / cfg.MSRateHz
    cfg.MSPhaseRef = cfg.thetaBurstStart - cfg.MSLeadBeforeTheta
    cfg.MSIstart = cfg.MSPhaseRef % cfg.MSISI
    cfg.MS_train = [
        cfg.MSIstart + spike * cfg.MSISI
        for spike in range(int((cfg.duration - cfg.MSIstart) / cfg.MSISI) + 1)
    ]

    cfg.simLabel = (
        f"{cfg.simLabelBase}"
        f"_Control{cfg.applyControlPC2B}"
        f"_VIPx{cfg.factorSynVIP}"
        f"_GLU{cfg.PYROLMweight}"
        f"_GABAOLM{cfg.OLMPYRweight}"
        f"_GABAVIP{cfg.VIPOLMweight}"
        f"_Achinput{cfg.nMSweight}"
    )

    time_range = [cfg.Transient - 50.0, cfg.duration - 200.0]
    record_exclude = set(cfg.recordExcludePops)
    cfg.recordCells = [(pop, 0) for pop in cfg.allPops if pop not in record_exclude]

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
