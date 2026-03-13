def apply_stimuli_config(cfg):
    cfg.thetaCycles = 5
    cfg.thetaInterBurstISI = 200.0
    cfg.thetaIntraBurstISI = 10.0
    cfg.thetaSpikesPerBurst = 5
    cfg.thetaDelay = 0.1
    cfg.thetaTailBuffer = 200.0

    cfg.vipBatchProtocol = False
    cfg.vipBatchNoMsCycles = 5
    cfg.vipBatchMsCycles = 5
    cfg.vipBatchInterPhaseGap = cfg.thetaInterBurstISI
    cfg.vipBatchTargetSpikesPerCycle = 4
    cfg.vipBatchMsGainWeight = 20.0

    cfg.vipScTargetSecs = [
        "radTprox",
        "radTmed",
        "radTdist1",
        "radTdist2",
        "radTdist3",
        "rad_thick1",
        "rad_medium1",
        "rad_thin1a",
        "rad_thin1b",
        "rad_thick2",
    ]
    cfg.vipPpTargetSecs = [
        "lm_thick1",
        "lm_medium1",
        "lm_thin1a",
        "lm_thin1b",
        "lm_thick2",
        "lm_medium2",
        "lm_thin2a",
        "lm_thin2b",
        "lmM1",
        "lmt1",
    ]
    cfg.vipInputLoc = 0.5
    cfg.nVipScInputs = len(cfg.vipScTargetSecs)
    cfg.nVipPpInputs = len(cfg.vipPpTargetSecs)

    cfg.SC = 1
    cfg.PP = 1

    cfg.nMS = 1
    cfg.nMSweight = 6e-4
    cfg.nMSinputs = 4
    cfg.MSRateHz = 10.0
    cfg.MSLeadBeforeTheta = 20.0
