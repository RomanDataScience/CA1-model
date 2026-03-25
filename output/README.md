# `output/`

This is the default output folder for the standard full-network run launched by `src/init.py`.

## Expected Contents

Depending on the active analysis settings, a run can write:

- `*_data.json`
- raster plots
- spike histograms
- trace plots
- any extra figures emitted by NetPyNE analysis

`PlotSynConn.py` writes its images to a `syn_contacts/` subfolder under the current save folder, which may also be this directory.

The folder is empty in the current snapshot, which simply means no default full-network run has been saved here yet.
