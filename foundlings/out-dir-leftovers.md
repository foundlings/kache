# Build-script runs over an existing OUT_DIR

Cargo reruns a stale build script without emptying `OUT_DIR`. Kache recorded a
run only if `OUT_DIR` was empty when the script started, so every rerun of a
script that writes into `OUT_DIR` was refused with
`refused|build-script run not recorded: it ran over an existing OUT_DIR`.

## Change

`src/build_script.rs`: `prepare_out_dir` runs before the script. With
`KACHE_BUILD_SCRIPT_CLEAN_OUT_DIR=1` (or `true`) it empties a non-empty
`OUT_DIR` and the run is recorded. A hit already empties `OUT_DIR` before
restoring, so a run recorded from an emptied `OUT_DIR` is exactly the state a
hit replays. Recording a directory diff instead would restore files without the
leftovers the script may have read, which a hit never provides.

Still refused, each with its own reason: switch off (reason names the switch);
`OUT_DIR` outside Cargo's `build/<unit>/out` layout; a directory that cannot be
emptied. Links inside `OUT_DIR` are removed, never followed. Everything the
record step already refuses is unchanged: undeclared or changed inputs, link
paths that leave `OUT_DIR` and the roots, non-UTF-8 stdout, size caps.

Not caught: a script that needs its own earlier output to succeed (it now sees
a clean `OUT_DIR`, as on a clean build and after a hit).
`KACHE_BUILD_SCRIPT_HERMETIC` is a different feature (shared sealed `OUT_DIR`
per key) and is unrelated to this refusal.

## Enable

Set the variable where Cargo runs, for example in `~/.cargo/config.toml`:

```toml
[env]
KACHE_BUILD_SCRIPT_CLEAN_OUT_DIR = "1"
```

## Verify

Count refusals in `~/Library/Caches/kache/events.jsonl` before and after:

```sh
rg -c 'it ran over an existing OUT_DIR' ~/Library/Caches/kache/events.jsonl
rg 'it ran over an existing OUT_DIR' ~/Library/Caches/kache/events.jsonl --no-filename -o | sort | uniq -c
```

After the switch is on and the scripts rerun twice, the count stops growing,
`kache stats --full` shows `build_script_run` for `noun-generated-manifest`
as `miss` then `local_hit`, and the remaining refusal text, if any, names a
specific cause. Tests: `cargo test --lib -- a_rerun_over_leftovers
the_switch_does_not_clear clearing_out_dir_leftovers`.
