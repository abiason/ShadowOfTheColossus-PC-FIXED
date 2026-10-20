#!/usr/bin/env bash
# Run an already prepared SotC image using the tested Linux PS4 Pro / 60 FPS configuration.
set -euo pipefail

usage() {
    cat <<'HELP'
Usage: bash tools/sotc_linux_pro.sh [--dry-run] BOOT_LINKED GAME_DIR CONTENT_PROFILE [SECONDS]

Uses PS4 Pro, a 60 FPS host limit, 60 Hz vblank and SOTC_EOP_DEFER=0.
Select Performance in the game's Options > Presentation menu.
SECONDS defaults to 0 (no automatic timeout).
SOTC_USER_DIR optionally selects the user directory (default: repository/user).
The image must already include the user's audio modules for sound.
No preparation, compilation or submodule updates are performed.
HELP
}

dry_run=0
if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    usage
    exit 0
fi
if [[ ${1:-} == --dry-run ]]; then
    dry_run=1
    shift
fi
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

settings=(
    SOTC_EOP_DEFER=0
    BB_FPS_LIMIT=60
    BB_VBLANK_HZ=60
    SOTC_FPS=1
    BB_DIRECT_MEMORY_ACCESS=0
    SOTC_NEO=1
    SOTC_RB_ASYNC=0
    "BB_GPU_USER_DIR=$user_dir"
)
command=("$probe" "$boot" --app0 "$game" --content-profile "$content"
         --user "$user_dir" --timeout "$seconds")

if (( dry_run )); then
    printf '%q ' env "${settings[@]}" "${command[@]}"
    printf '\n'
    exit 0
fi

printf 'PS4 Pro: select Performance in Options > Presentation; host limit 60 FPS, EOP defer off.\n' >&2
exec env "${settings[@]}" "${command[@]}"
