# Local Fuzzing

This project has two [Atheris](https://github.com/google/atheris) fuzz targets:

- `fuzzers/jsonpatchx_fuzzer.py`
- `fuzzers/jsonpatchx_custom_backend_fuzzer.py`

## Prerequisites

- `uv` is installed.
- You already ran `uv sync`.
- Use Python 3.13 for fuzzing
  ([Atheris only supports Py3.11-13](https://pypi.org/project/atheris/))

## One-time setup for fuzzing

Install the fuzz-only dependency group (defined in `pyproject.toml`):

```bash
uv sync --python 3.13 --group fuzz
```

## Run fuzzers locally

Run commands from the repository root.

Prepare scratch directories (do not write generated corpus back into the
repository):

```bash
mkdir -p /tmp/jsonpatchx_artifacts
mkdir -p /tmp/jsonpatchx_corpus_f1 /tmp/jsonpatchx_corpus_f2
cp fuzzers/corpus/jsonpatchx_fuzzer/seed_* /tmp/jsonpatchx_corpus_f1/
cp fuzzers/corpus/jsonpatchx_custom_backend_fuzzer/seed_* /tmp/jsonpatchx_corpus_f2/
```

Run the core RFC6902 fuzzer for 10 minutes:

```bash
uv run --python 3.13 python -m fuzzers.jsonpatchx_fuzzer \
  -max_total_time=600 \
  -dict=fuzzers/jsonpatchx_fuzzer.dict \
  -artifact_prefix=/tmp/jsonpatchx_artifacts/ \
  /tmp/jsonpatchx_corpus_f1
```

Run the custom backend fuzzer for 10 minutes:

```bash
uv run --python 3.13 python -m fuzzers.jsonpatchx_custom_backend_fuzzer \
  -max_total_time=600 \
  -dict=fuzzers/jsonpatchx_custom_backend_fuzzer.dict \
  -artifact_prefix=/tmp/jsonpatchx_artifacts/ \
  /tmp/jsonpatchx_corpus_f2
```

## Useful flags

- `-max_total_time=SECONDS`: stop after a fixed duration.
- `-runs=N`: run a fixed number of inputs (useful for a quick smoke check).
- `-dict=...`: improves mutation quality using known tokens/ops.
- `-artifact_prefix=DIR/`: where crash/leak artifacts are written.
- last argument: mutable corpus directory (use `/tmp/...` for local runs).

## Notes

- On macOS, `atheris` can fail to build with Apple Clang because it does not
  ship `libFuzzer`. If that happens, use an LLVM Clang toolchain or run fuzzing
  in the ClusterFuzzLite Docker environment.
- Quick macOS fix with Homebrew LLVM:

```bash
brew install llvm
export CLANG_BIN="$(brew --prefix llvm)/bin/clang"
uv sync --python 3.13 --group fuzz
```

- If a crash is found, libFuzzer writes a reproducer file (for example
  `crash-*`).
- Re-run with that file to reproduce:

```bash
uv run --python 3.13 python -m fuzzers.jsonpatchx_fuzzer crash-...
```

- If you accidentally wrote generated files into `fuzzers/corpus/`, clean them:

```bash
find fuzzers/corpus -type f ! -name 'seed_*' -delete
```

## [ClusterFuzzLite](https://google.github.io/clusterfuzzlite/) CI workflows

This repository uses three workflows so PR signal is fast, while deeper fuzzing
still happens regularly:

1. PR workflow: `.github/workflows/cflite_pr.yml`
   - `sanitizer: address`, `mode: code-change`, `fuzz-seconds: 300`
   - `keep-unaffected-fuzz-targets: false`
   - Why: fail quickly on bugs introduced by the PR without spending CI time on
     unchanged areas.
2. Weekly batch workflow: `.github/workflows/cflite_weekly.yml`
   - `sanitizer: address`, `mode: batch`, `fuzz-seconds: 3600`
   - `keep-unaffected-fuzz-targets: true`
   - Why: whole-repo exploration to catch issues that PR-focused fuzzing can
     miss.
3. Weekly coverage workflow: `.github/workflows/cflite_coverage.yml`
   - `sanitizer: coverage`, `mode: coverage`
   - `keep-unaffected-fuzz-targets: true`
   - Why: maintain baseline coverage data used by ClusterFuzzLite code-change
     comparisons.
