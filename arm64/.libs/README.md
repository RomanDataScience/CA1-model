# `arm64/.libs/`

This subfolder holds the alternate shared-library output from `nrnivmodl`.

Current contents include:

- `libnrnmech.so`

Some helper code searches both `arm64/libnrnmech.dylib` and `arm64/.libs/libnrnmech.so` so the model can load regardless of how NEURON packaged the compiled library on the local machine.

Treat this folder as generated output, not source.
