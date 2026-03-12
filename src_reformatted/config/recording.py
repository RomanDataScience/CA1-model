def apply_recording_config(cfg):
    cfg.allPops = ["PC2B", "OLM", "VIP", "SC", "PP", "MS"]
    cfg.recordExcludePops = ["SC", "PP", "MS"]

    cfg.recordTraces = {
        "V_soma": {"sec": "soma", "loc": 0.5, "var": "v"},
        "I_AMPA_facil": {"synMech": "AMPA_facil", "var": "i", "conds": {"pop": "OLM"}},
        "I_GABA_VIP": {"synMech": "GABA_VIP", "var": "i", "conds": {"pop": "OLM"}},
        "I_GABA_slow": {"synMech": "GABA_slow", "var": "i", "conds": {"pop": "PC2B"}},
        "I_nAch": {"synMech": "nACh_IS3", "var": "i", "conds": {"pop": "VIP"}},
    }

    cfg.plotRasterDefaults = {"saveFig": True, "marker": "|"}
    cfg.plotSpikeHistDefaults = {"saveFig": True, "binSize": 1, "measure": "rate"}
    cfg.plotTracesDefaults = {"saveFig": True, "oneFigPer": "trace", "legend": True}
