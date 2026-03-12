def apply_synapse_config(cfg):
    cfg.thetaSynScale = 1.2
    cfg.thetaAMPAUnitWeight = 0.00156
    cfg.thetaNMDAUnitWeight = 0.000882
    cfg.factorSynPYR = 0.208
    cfg.factorSynVIP = 1.0

    cfg.PYROLMweight = 5e-3
    cfg.OLMPYRweight = 1e-2
    cfg.VIPOLMweight = 1e-2

    cfg.synsPerConnPYROLM = 2
    cfg.synsPerConnOLMPYR = 8
    cfg.synsPerConnVIPOLM = 3

    cfg.delayPYROLM = 1.1
    cfg.delayOLMPYR = 1.1
    cfg.delayVIPOLM = 0.7

    cfg.synMechParams = {
        "AMPA": {
            "mod": "Exp2Syn",
            "tau1": 0.5,
            "tau2": 1.0,
            "e": 0.0,
        },
        "NMDA": {
            "mod": "nmdanet",
            "Alpha": 0.35,
            "Beta": 0.035,
        },
        "GABA_slow": {
            "mod": "Exp2Syn",
            "tau1": 2.0,
            "tau2": 20.0,
            "e": -75,
        },
        "AMPA_facil": {
            "mod": "Exp2Syn",
            "tau1": 0.5,
            "tau2": 3.0,
            "e": 0.0,
        },
        "GABA_VIP": {
            "mod": "Exp2Syn",
            "tau1": 0.3,
            "tau2": 15.0,
            "e": -80,
        },
        "nACh_IS3": {
            "mod": "Exp2Syn",
            "tau1": 40.0,
            "tau2": 222.0,
            "e": 0.0,
        },
    }
