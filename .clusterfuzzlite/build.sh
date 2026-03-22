#!/bin/bash -eu

compile_python_fuzzer fuzzers/jsonpatchx_fuzzer.py
compile_python_fuzzer fuzzers/jsonpatchx_custom_backend_fuzzer.py

cp fuzzers/jsonpatchx_fuzzer.dict "$OUT/jsonpatchx_fuzzer.dict"
cp fuzzers/jsonpatchx_custom_backend_fuzzer.dict \
  "$OUT/jsonpatchx_custom_backend_fuzzer.dict"

zip -j "$OUT/jsonpatchx_fuzzer_seed_corpus.zip" \
  fuzzers/corpus/jsonpatchx_fuzzer/*
zip -j "$OUT/jsonpatchx_custom_backend_fuzzer_seed_corpus.zip" \
  fuzzers/corpus/jsonpatchx_custom_backend_fuzzer/*
