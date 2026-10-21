#!/usr/bin/env bash
# Run an already prepared SotC image using the tested Linux PS4 Pro / 60 FPS configuration.
set -euo pipefail

usage() {
    cat <<'HELP'
Usage: bash tools/sotc_linux_pro.sh [--dry-run] [--sotc-cmdline FILE] BOOT_LINKED GAME_DIR CONTENT_PROFILE [SECONDS]

Uses PS4 Pro, a 60 FPS host limit, 60 Hz vblank and SOTC_EOP_DEFER=0.
Direct memory defaults to 5376 MiB; BB_DMEM_MB can override it.
Select Performance in the game's Options > Presentation menu.
SECONDS defaults to 0 (no automatic timeout).
SOTC_USER_DIR optionally selects the user directory (default: repository/user).
The image must already include the user's audio modules for sound.
--sotc-cmdline passes a prepared SOTCCMD1 file to the loader (optional engine settings).
No preparation, compilation or submodule updates are performed.
HELP
}

dry_run=0
cmdline=
while (( $# )); do
    case $1 in
        --help|-h) usage; exit 0 ;;
        --dry-run) dry_run=1; shift ;;
        --sotc-cmdline)
            if (( $# < 2 )) || [[ -z $2 || $2 == --* ]]; then
                echo '--sotc-cmdline requires a file.' >&2
                exit 2
            fi
            cmdline=$2
            shift 2
            ;;
        --) shift; break ;;
        --*) echo "Unknown option: $1" >&2; exit 2 ;;
        *) break ;;
    esac
done
if (( $# < 3 || $# > 4 )); then
    usage >&2
    exit 2
fi

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
probe=$repo_dir/out/bb-probe
boot=$1
game=$2
content=$3
seconds=${4:-0}
user_dir=${SOTC_USER_DIR:-$repo_dir/user}

[[ $seconds =~ ^[0-9]+$ ]] || { echo 'SECONDS must be a non-negative integer.' >&2; exit 2; }
[[ -x $probe ]] || { echo "Executable not found: $probe" >&2; exit 1; }
[[ -f $boot ]] || { echo "Prepared image not found: $boot" >&2; exit 1; }
[[ -d $game ]] || { echo "Game directory not found: $game" >&2; exit 1; }
[[ -f $content ]] || { echo "Content profile not found: $content" >&2; exit 1; }
if [[ -n $cmdline && ! -f $cmdline ]]; then
    echo "Engine command line file not found: $cmdline" >&2
    exit 1
fi

settings=(
    SOTC_EOP_DEFER=0
    BB_FPS_LIMIT=60
    BB_VBLANK_HZ=60
    SOTC_FPS=1
    BB_DIRECT_MEMORY_ACCESS=0
    SOTC_NEO=1
    "BB_DMEM_MB=${BB_DMEM_MB:-5376}"
    SOTC_RB_ASYNC=0
    "BB_GPU_USER_DIR=$user_dir"
)
command=("$probe" "$boot" --app0 "$game" --content-profile "$content"
         --user "$user_dir" --timeout "$seconds")
if [[ -n $cmdline ]]; then
    command+=(--sotc-cmdline "$cmdline")
fi

if (( dry_run )); then
    printf '%q ' env "${settings[@]}" "${command[@]}"
    printf '\n'
    exit 0
fi

printf 'PS4 Pro: select Performance in Options > Presentation; host limit 60 FPS, EOP defer off.\n' >&2
exec env "${settings[@]}" "${command[@]}"
