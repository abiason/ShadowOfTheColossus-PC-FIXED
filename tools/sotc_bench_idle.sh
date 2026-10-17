#!/usr/bin/env bash
# Idle-scene A/B benchmark through the packaged launcher (SotC.exe --play, the saved launcher
# settings). Each variant: one run of SECONDS with extra environment variables, closed with a
# normal window close (never forced: a forced kill can truncate the shader cache). Prints the mean
# FPS of the SOTC FPS windows from 60 s on. Needs show_fps on in the launcher settings.
#   tools/sotc_bench_idle.sh <port dir> <seconds> "label|VAR=1 VAR2=2" ["label|..." ...]
set -u
port=$1; seconds=$2; shift 2
for variant in "$@"; do
    label=${variant%%|*}; vars=${variant#*|}
    log="$port/user/bench_${label}.log"
    # Exported in a subshell, not through env(1): the MSYS2 env.exe dropped the Windows user
    # variables (APPDATA, USERPROFILE) and the launcher could not find its settings.
    ( cd "$port" && for v in $vars; do export "$v"; done && ./SotC.exe --play > "$log" 2>&1 & )
    sleep "$seconds"
    taskkill //IM bb-probe.exe > /dev/null 2>&1
    for _ in $(seq 1 10); do sleep 3; tasklist | grep -qi bb-probe || break; done
    if tasklist | grep -qi bb-probe; then echo "$label: did not close"; fi
    sleep 5
    python -I - "$log" "$label" <<'PY'
import re, sys
rows = [(int(m.group(2)), float(m.group(1)), int(m.group(3)))
        for line in open(sys.argv[1], encoding='utf-8', errors='replace')
        for m in [re.match(r'SOTC FPS ([\d.]+) at (\d+)s; (\d+) cmds', line)] if m]
late = [r for r in rows if r[0] >= 60]
faults = sum('Fault' in l for l in open(sys.argv[1], encoding='utf-8', errors='replace'))
if late:
    print(f'{sys.argv[2]:>14}: {sum(r[1] for r in late) / len(late):5.1f} FPS over {len(late)} windows, '
          f'{sum(r[2] for r in late) / len(late):5.0f} cmds/frame, faults {faults}')
else:
    print(f'{sys.argv[2]:>14}: no data (faults {faults})')
PY
done
