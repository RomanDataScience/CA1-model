# `arm64/`

This folder contains generated NEURON mechanism build products for Apple Silicon.

## What These Files Are

Running `nrnivmodl mechanisms` on an Apple Silicon machine produces:

- generated C sources such as `*.c`
- object files such as `*.o`
- the `special` executable
- shared libraries such as `libnrnmech.dylib`
- an auxiliary `.libs/` directory

These files are not hand-maintained source code. The editable source lives in `mechanisms/`.

## How The Repo Uses This Folder

- single-cell utilities search here first when loading compiled mechanisms
- tests also probe this folder for `libnrnmech.dylib`
- NEURON can use the generated `special` binary and shared library directly

## When To Rebuild

Rebuild this folder when:

- any `.mod` file changes
- you switch NEURON versions
- you move between architectures
- loading compiled mechanisms starts failing

Typical rebuild command:

```bash
nrnivmodl mechanisms
```
