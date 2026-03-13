def apply_sim_config(cfg):
    cfg.Transient = 500
    cfg.dt = 0.1
    cfg.cvode_active = True
    cfg.cvode_atol = 1e-3
    cfg.progressBar = 0
    cfg.hParams = {"v_init": -60.0, "celsius": 34.0}
    cfg.vipBatchVInit = -60.0

    cfg.verbose = False
    cfg.validateNetParams = False
    cfg.recordStep = cfg.dt
    cfg.printRunTime = 0.1
    cfg.seeds = {"conn": 4321, "stim": 1234, "loc": 4321, "cell": 4321}

    cfg.saveJson = True
    cfg.savePickle = False
    cfg.saveDataInclude = ["simData", "simConfig", "netParams"]
    cfg.recordTime = True

    cfg.saveFolder = "output_reformated"
    cfg.simLabelBase = "CA1_1"
    cfg.simLabel = cfg.simLabelBase
