#!/bin/bash
# Set up the Mantella server natively on an Apple Silicon Mac (see MACOS.md).
#
# The game (Skyrim SE 1.6.1170 + SKSE + the Mantella mod) runs under Wine, e.g. with
# SkyrimMT. This script prepares the macOS side: Python venv + dependencies, Piper (TTS)
# through Wine in its own prefix, Mantella's config.ini paths, the bundled Mantella.exe
# switched off, and a "Start Mantella.command" launcher.
#
# Dry run by default: nothing is changed until you pass --apply. Every change asks first
# unless you also pass --yes. Safe to run again: finished steps are detected and skipped.
# It never reads, writes or prints API keys.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

DRY_RUN=1
ASSUME_YES=0
SKIP_DEPS=0
RECOMMENDED=0
RESTORE_EXE=0
SKYRIM_DATA=""
WINE_BIN=""
SKYRIMMT_HOME="${SKYRIM_HOME:-$HOME/Games/skyrim}"
PIPER_PREFIX="${MANTELLA_WINEPREFIX:-$HOME/Games/mantella-wine}"
CONFIG_DIR="$HOME/Documents/My Games/Mantella"
LAUNCHER="$HOME/Desktop/Start Mantella.command"
PORT=4999
DISABLED_SUFFIX=".disabled-mac-native"
MOONSHINE_REPO="https://github.com/usefulsensors/moonshine.git"

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Prepares the native macOS Mantella server in this repository ($REPO_DIR).
Default is a dry run that only reports what it would do.

Options:
  --apply                 Make the changes (asks before each one).
  --yes                   With --apply: do not ask, accept every step.
  --skyrim-data DIR       Skyrim's deployed Data folder (contains Mantella.esp).
                          Default: SkyrimMT's \$HOME/Games/skyrim/versions/1.6.1170/Data
  --wine PATH             Wine binary for Piper. Default: SkyrimMT's bundled Wine,
                          then 'wine' / 'wine64' on PATH.
  --wine-prefix DIR       Wine prefix used only by Piper. Default: $PIPER_PREFIX
  --config-dir DIR        Mantella's user folder. Default: $CONFIG_DIR
  --launcher PATH         Where to write the launcher. Default: $LAUNCHER
  --recommended-settings  Also write the settings that worked best on a Mac
                          (Whisper small / English, no interruption, single LLM call
                          for actions). See MACOS.md.
  --port N                Mantella's server port (config: port). Default: 4999
  --skip-deps             Skip the Python venv / package steps.
  --restore-exe           Undo: rename Mantella.exe${DISABLED_SUFFIX} back to Mantella.exe.
  -h, --help              Show this help.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --apply) DRY_RUN=0 ;;
    --dry-run) DRY_RUN=1 ;;
    --yes|-y) ASSUME_YES=1 ;;
    --skyrim-data) SKYRIM_DATA="${2:?--skyrim-data needs a path}"; shift ;;
    --wine) WINE_BIN="${2:?--wine needs a path}"; shift ;;
    --wine-prefix) PIPER_PREFIX="${2:?--wine-prefix needs a path}"; shift ;;
    --config-dir) CONFIG_DIR="${2:?--config-dir needs a path}"; shift ;;
    --launcher) LAUNCHER="${2:?--launcher needs a path}"; shift ;;
    --recommended-settings) RECOMMENDED=1 ;;
    --port) PORT="${2:?--port needs a number}"; shift ;;
    --skip-deps) SKIP_DEPS=1 ;;
    --restore-exe) RESTORE_EXE=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

# ---------------------------------------------------------------- helpers
if [ -t 1 ]; then B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; N=$'\033[0m'; else B=; G=; Y=; R=; N=; fi
MANUAL_STEPS=()
WARNINGS=0

step() { printf '\n%s== %s%s\n' "$B" "$1" "$N"; }
ok()   { printf '  %sok%s    %s\n' "$G" "$N" "$1"; }
todo() { printf '  %s->%s    %s\n' "$Y" "$N" "$1"; }
warn() { printf '  %s!!%s    %s\n' "$R" "$N" "$1"; WARNINGS=$((WARNINGS + 1)); }
manual() { MANUAL_STEPS+=("$1"); }
die()  { printf '%sError:%s %s\n' "$R" "$N" "$1" >&2; exit 1; }

# confirm "question" -> 0 if the step should run (only ever true with --apply)
confirm() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '  %s[dry-run]%s would: %s\n' "$Y" "$N" "$1"
    return 1
  fi
  [ "$ASSUME_YES" -eq 1 ] && return 0
  local answer=""
  printf '  ?     %s [y/N] ' "$1"
  read -r answer </dev/tty || answer=""
  case "$answer" in y|Y|yes|YES) return 0 ;; *) echo "        skipped"; return 1 ;; esac
}

port_in_use() { lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; }

# ---------------------------------------------------------------- 1. platform
step "1. Platform and tools"
[ "$(uname -s)" = "Darwin" ] || die "This script is for macOS."
if [ "$(uname -m)" = "arm64" ]; then ok "macOS $(sw_vers -productVersion) on Apple Silicon"
else warn "Not arm64 ($(uname -m)). Only Apple Silicon was tested."; fi
[ -f "$REPO_DIR/main.py" ] && [ -f "$REPO_DIR/requirements-mac.txt" ] \
  || die "Run this from a Mantella checkout that contains requirements-mac.txt ($REPO_DIR)."
ok "Mantella checkout: $REPO_DIR"

command -v git >/dev/null 2>&1 && ok "git found" || die "git is missing. Install the Xcode command line tools: xcode-select --install"

BREW=""
if command -v brew >/dev/null 2>&1; then BREW="$(command -v brew)"; ok "Homebrew found ($("$BREW" --prefix))"
else warn "Homebrew not found (https://brew.sh). Needed for portaudio (microphone input)."; manual "Install Homebrew from https://brew.sh, then run this script again."; fi

UV=""
command -v uv >/dev/null 2>&1 && UV="$(command -v uv)" && ok "uv found (used for faster installs)"

PY311=""
if command -v python3.11 >/dev/null 2>&1; then PY311="$(command -v python3.11)"
elif [ -n "$UV" ] && "$UV" python find 3.11 >/dev/null 2>&1; then PY311="$("$UV" python find 3.11)"
elif [ -n "$BREW" ] && [ -x "$("$BREW" --prefix)/opt/python@3.11/bin/python3.11" ]; then PY311="$("$BREW" --prefix)/opt/python@3.11/bin/python3.11"; fi
if [ -n "$PY311" ]; then ok "Python 3.11: $PY311"
elif [ "$SKIP_DEPS" -eq 0 ]; then
  todo "Python 3.11 not found (Mantella v0.14 pins packages that need 3.11)"
  if [ -n "$BREW" ] && confirm "brew install python@3.11"; then
    "$BREW" install python@3.11 && PY311="$("$BREW" --prefix)/opt/python@3.11/bin/python3.11"
  else manual "Install Python 3.11: brew install python@3.11 (or: uv python install 3.11)"; fi
fi

if [ -n "$BREW" ]; then
  if "$BREW" list portaudio >/dev/null 2>&1; then ok "portaudio installed (needed to build pyaudio)"
  else
    todo "portaudio missing (pyaudio, the microphone library, is built against it)"
    confirm "brew install portaudio" && "$BREW" install portaudio
  fi
fi

# ---------------------------------------------------------------- 2. python deps
VENV="$REPO_DIR/.venv"
VPY="$VENV/bin/python"
pip_install() {
  if [ -n "$UV" ]; then "$UV" pip install --python "$VPY" "$@"; else "$VPY" -m pip install "$@"; fi
}
step "2. Python environment ($VENV)"
if [ "$SKIP_DEPS" -eq 1 ]; then
  ok "skipped (--skip-deps)"
else
  if [ -x "$VPY" ]; then
    VER="$("$VPY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
    if [ "$VER" = "3.11" ]; then ok "venv exists (Python $VER)"; else warn "venv uses Python $VER, not 3.11. Delete $VENV and run again."; fi
  elif [ -n "$PY311" ]; then
    todo "no venv yet"
    if confirm "create $VENV with $PY311"; then
      if [ -n "$UV" ]; then "$UV" venv --python "$PY311" "$VENV"; else "$PY311" -m venv "$VENV"; fi
      [ -n "$UV" ] || "$VPY" -m pip install --quiet --upgrade pip
    fi
  fi

  # Moonshine (speech-to-text) is pinned in requirements.txt as a git URL. Installing it that
  # way fails on macOS: the clone tries to download Git LFS model files, and its setup.py needs
  # setuptools<82 from the venv. So: clone without LFS, install without build isolation.
  MOON_COMMIT="$(sed -n 's/^git+https:\/\/github.com\/usefulsensors\/moonshine.git@\([0-9a-f]*\)#.*/\1/p' "$REPO_DIR/requirements.txt" | head -1)"
  MOON_DIR="$REPO_DIR/vendor/moonshine"
  if [ -d "$MOON_DIR/moonshine-onnx" ]; then ok "Moonshine source present ($MOON_DIR)"
  elif [ -n "$MOON_COMMIT" ]; then
    todo "Moonshine source missing (pinned commit ${MOON_COMMIT:0:10})"
    if confirm "clone Moonshine into vendor/moonshine without Git LFS files"; then
      mkdir -p "$REPO_DIR/vendor"
      GIT_LFS_SKIP_SMUDGE=1 git clone -q --filter=blob:none "$MOONSHINE_REPO" "$MOON_DIR"
      GIT_LFS_SKIP_SMUDGE=1 git -C "$MOON_DIR" checkout -q "$MOON_COMMIT"
    fi
  fi

  if [ -x "$VPY" ] && "$VPY" -c 'import pyaudio, faster_whisper, moonshine_onnx, gradio, fastapi, openai, mss, cv2, playsound, AppKit' >/dev/null 2>&1; then
    ok "Python packages already installed"
  else
    todo "Python packages missing or incomplete"
    if confirm "install requirements-mac.txt and Moonshine into the venv (several hundred MB)"; then
      [ -x "$VPY" ] || die "No venv at $VENV."
      BREW_PREFIX="/opt/homebrew"; [ -n "$BREW" ] && BREW_PREFIX="$("$BREW" --prefix)"
      pip_install "setuptools<82" wheel
      CFLAGS="-I$BREW_PREFIX/include" LDFLAGS="-L$BREW_PREFIX/lib" pip_install -r "$REPO_DIR/requirements-mac.txt"
      pip_install --no-build-isolation "$MOON_DIR/moonshine-onnx"
      "$VPY" -c 'import pyaudio, faster_whisper, moonshine_onnx, gradio, fastapi, openai, mss, cv2, playsound, AppKit' \
        && ok "imports work" || warn "some imports still fail, see the output above"
    fi
  fi
fi

# ---------------------------------------------------------------- 3. skyrim data
step "3. Skyrim Data folder and the Mantella mod"
if [ -z "$SKYRIM_DATA" ]; then
  DEFAULT_DATA="$SKYRIMMT_HOME/versions/1.6.1170/Data"
  if [ -d "$DEFAULT_DATA" ]; then SKYRIM_DATA="$DEFAULT_DATA"
  elif [ "$DRY_RUN" -eq 0 ] && [ "$ASSUME_YES" -eq 0 ]; then
    printf '  ?     Path to Skyrim'"'"'s Data folder (contains Mantella.esp), empty to skip: '
    read -r SKYRIM_DATA </dev/tty || SKYRIM_DATA=""
  fi
fi
MS=""
if [ -z "$SKYRIM_DATA" ]; then
  warn "Skyrim Data folder not found. Pass --skyrim-data DIR."
  manual "Re-run with --skyrim-data <Skyrim Data folder> so Piper and config.ini can be set up."
elif [ ! -d "$SKYRIM_DATA" ]; then
  warn "Not a folder: $SKYRIM_DATA"; SKYRIM_DATA=""
else
  ok "Data folder: $SKYRIM_DATA"
  [ -f "$SKYRIM_DATA/Mantella.esp" ] && ok "Mantella.esp present" \
    || { warn "Mantella.esp not in Data. Install the Mantella mod (and deploy, in SkyrimMT)."; manual "Install the Mantella mod (Nexus Mods, Skyrim SE mod 98631), enable Mantella.esp and deploy."; }
  # Mantella validates skyrim_mod_folder by this voice folder, which the mod ships
  [ -d "$SKYRIM_DATA/Sound/Voice/Mantella.esp" ] && ok "Sound/Voice/Mantella.esp present" \
    || warn "No $SKYRIM_DATA/Sound/Voice/Mantella.esp: Mantella will reject skyrim_mod_folder. Is this the folder the mod is deployed to?"
  MS="$SKYRIM_DATA/SKSE/Plugins/MantellaSoftware"
  if [ -f "$MS/piper/piper.exe" ]; then ok "Piper found: $MS/piper"
  else warn "No $MS/piper/piper.exe. Piper voices ship with the Mantella mod."; fi
  [ -d "$MS/moonshine" ] && ok "Moonshine models found: $MS/moonshine" || todo "no $MS/moonshine (only needed for stt_service = Moonshine)"
  [ -f "$SKYRIM_DATA/SKSE/Plugins/SKSE_HTTP.dll" ] || [ -f "$SKYRIM_DATA/SKSE/Plugins/MantellaDialogue.dll" ] \
    && ok "Mantella SKSE plugins present" || warn "Mantella's SKSE plugins not found under $SKYRIM_DATA/SKSE/Plugins"
fi

# ---------------------------------------------------------------- 4. Mantella.exe
step "4. Switch off the bundled Mantella.exe"
# The mod starts its own Windows Mantella.exe inside the game's Wine bottle. On macOS that copy
# cannot use the microphone and would take port 4999, so only the native server may run.
EXE_DIRS=()
EXE_CHANGED=0
[ -n "$MS" ] && EXE_DIRS+=("$MS")
if [ -d "$SKYRIMMT_HOME/mods" ]; then
  for d in "$SKYRIMMT_HOME"/mods/*/SKSE/Plugins/MantellaSoftware; do [ -d "$d" ] && EXE_DIRS+=("$d"); done
fi
if [ "${#EXE_DIRS[@]}" -eq 0 ]; then todo "no MantellaSoftware folder known (needs --skyrim-data)"; fi
for d in ${EXE_DIRS[@]+"${EXE_DIRS[@]}"}; do
  if [ "$RESTORE_EXE" -eq 1 ]; then
    if [ -f "$d/Mantella.exe$DISABLED_SUFFIX" ] && [ ! -e "$d/Mantella.exe" ]; then
      todo "disabled exe in $d"; EXE_CHANGED=1
      confirm "restore Mantella.exe in $d" && mv "$d/Mantella.exe$DISABLED_SUFFIX" "$d/Mantella.exe" && ok "restored"
    else ok "nothing to restore in $d"; fi
  elif [ -f "$d/Mantella.exe" ]; then
    todo "Mantella.exe active in $d"; EXE_CHANGED=1
    confirm "rename it to Mantella.exe$DISABLED_SUFFIX (undo with --restore-exe)" \
      && mv "$d/Mantella.exe" "$d/Mantella.exe$DISABLED_SUFFIX" && ok "disabled"
  elif [ -f "$d/Mantella.exe$DISABLED_SUFFIX" ]; then ok "already disabled in $d"
  else todo "no Mantella.exe in $d"; fi
done
if [ "$EXE_CHANGED" -eq 1 ] && [ -d "$SKYRIMMT_HOME/mods" ]; then
  manual "SkyrimMT: press Deploy after this script so the Data folder matches the mods folder (otherwise a later deploy brings Mantella.exe back)."
fi

# ---------------------------------------------------------------- 5. wine for piper
step "5. Wine for Piper (text-to-speech)"
if [ -z "$WINE_BIN" ]; then
  if [ -n "${MANTELLA_WINE:-}" ]; then WINE_BIN="$MANTELLA_WINE"
  elif [ -x "$SKYRIMMT_HOME/wine/bin/wine" ]; then WINE_BIN="$SKYRIMMT_HOME/wine/bin/wine"
  elif command -v wine >/dev/null 2>&1; then WINE_BIN="$(command -v wine)"
  elif command -v wine64 >/dev/null 2>&1; then WINE_BIN="$(command -v wine64)"; fi
fi
if [ -z "$WINE_BIN" ] || [ ! -x "$WINE_BIN" ]; then
  warn "No Wine found. Piper (piper.exe) needs Wine on macOS."
  manual "Install Wine (SkyrimMT bundles one; otherwise e.g. brew install --cask wine-stable, which needs Rosetta 2) and re-run, or pass --wine PATH."
  WINE_BIN=""
else
  ok "Wine: $WINE_BIN"
  if [ -f "$PIPER_PREFIX/system.reg" ]; then ok "Piper Wine prefix exists: $PIPER_PREFIX"
  else
    todo "Piper Wine prefix missing: $PIPER_PREFIX (kept apart from the game's prefix, so quitting the game never kills Piper)"
    if confirm "create it with wineboot (takes ~30 s)"; then
      mkdir -p "$PIPER_PREFIX"
      WINEPREFIX="$PIPER_PREFIX" WINEDEBUG=-all "$WINE_BIN" wineboot -i >/dev/null 2>&1 || true
      [ -f "$PIPER_PREFIX/system.reg" ] && ok "prefix created" || warn "wineboot did not finish; Wine will retry on first Piper start"
    fi
  fi
fi

# ---------------------------------------------------------------- 6. config.ini
step "6. Mantella config.ini ($CONFIG_DIR)"
CONFIG="$CONFIG_DIR/config.ini"
SETTINGS=()
if [ -n "$SKYRIM_DATA" ]; then
  SETTINGS+=("game=Skyrim" "skyrim_mod_folder=$SKYRIM_DATA" "piper_folder=$MS/piper" "lip_generation=Disabled")
  [ -d "$MS/moonshine" ] && SETTINGS+=("moonshine_folder=$MS/moonshine")
fi
if [ "$RECOMMENDED" -eq 1 ]; then
  SETTINGS+=("stt_service=Whisper" "whisper_model_size=small" "stt_language=en" "allow_interruption=False" "custom_function_model=False")
fi
if [ "${#SETTINGS[@]}" -eq 0 ]; then
  todo "nothing to write (no Data folder known)"
elif port_in_use; then
  warn "Something is listening on port $PORT (Mantella running?). Its web UI rewrites config.ini, so the file is left alone. Stop it and run again."
else
  # Report which keys differ; python is only used to parse/edit the INI (stdlib, isolated mode)
  CHANGES="$(python3 -I - "$CONFIG" ${SETTINGS[@]+"${SETTINGS[@]}"} <<'PY'
import re, sys, os
path, pairs = sys.argv[1], [a.split('=', 1) for a in sys.argv[2:]]
text = open(path, encoding='utf-8').read() if os.path.exists(path) else ''
for key, value in pairs:
    m = re.search(rf'(?m)^{re.escape(key)}\s*=\s*(.*)$', text)
    if not m or m.group(1).strip() != value:
        print(f"{key} = {value}")
PY
)"
  if [ -z "$CHANGES" ]; then ok "config.ini already has the macOS paths$( [ "$RECOMMENDED" -eq 1 ] && echo ' and recommended settings')"
  else
    printf '%s\n' "$CHANGES" | sed 's/^/        /'
    if confirm "write these values to $CONFIG (a backup is made first)"; then
      mkdir -p "$CONFIG_DIR"
      [ -f "$CONFIG" ] && cp "$CONFIG" "$CONFIG.bak-$(date +%Y%m%d-%H%M%S)"
      python3 -I - "$CONFIG" ${SETTINGS[@]+"${SETTINGS[@]}"} <<'PY'
import re, sys, os
path, pairs = sys.argv[1], [a.split('=', 1) for a in sys.argv[2:]]
text = open(path, encoding='utf-8').read() if os.path.exists(path) else ''
if not text.strip():
    text = '[Game]\n'  # Mantella fills in every other setting with defaults on first start
for key, value in pairs:
    line = f'{key} = {value}'
    text, n = re.subn(rf'(?m)^{re.escape(key)}\s*=.*$', lambda _m: line, text)
    if n == 0:
        text = text.rstrip('\n') + '\n' + line + '\n'  # sections do not matter to Mantella
open(path, 'w', encoding='utf-8').write(text)
PY
      ok "config.ini updated"
    fi
  fi
fi

# ---------------------------------------------------------------- 7. launcher
step "7. Launcher ($LAUNCHER)"
LAUNCHER_BODY="#!/bin/zsh
# Starts the native Mantella server for Skyrim (generated by scripts/macos/setup_mantella_mac.sh).
# Runs in Terminal, so macOS asks Terminal (not the game) for microphone / screen recording access.
cd $(printf '%q' "$REPO_DIR") || exit 1
if lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  echo \"Port $PORT is already in use (Mantella already running?).\"; read -k1 '?Press any key to close.'; exit 1
fi
printf '\\e]0;Mantella\\a'
export MANTELLA_WINE=$(printf '%q' "${WINE_BIN:-wine}")
export MANTELLA_WINEPREFIX=$(printf '%q' "$PIPER_PREFIX")
# After the first run has downloaded the speech model, uncomment to skip Hugging Face update checks:
# export HF_HUB_OFFLINE=1
LOG=$(printf '%q' "$CONFIG_DIR/terminal.log")
mkdir -p \"\${LOG:h}\"; echo \"=== \$(date) ===\" >> \"\$LOG\"
.venv/bin/python main.py 2>&1 | tee -a \"\$LOG\"
"
if [ -f "$LAUNCHER" ] && [ "$(cat "$LAUNCHER")" = "${LAUNCHER_BODY%$'\n'}" ]; then ok "launcher up to date"
else
  [ -f "$LAUNCHER" ] && todo "launcher exists but differs (a backup is made)" || todo "no launcher yet"
  if confirm "write $LAUNCHER"; then
    mkdir -p "$(dirname "$LAUNCHER")"
    [ -f "$LAUNCHER" ] && cp "$LAUNCHER" "$LAUNCHER.bak-$(date +%Y%m%d-%H%M%S)"
    printf '%s' "$LAUNCHER_BODY" > "$LAUNCHER"
    chmod +x "$LAUNCHER"
    ok "launcher written; double-click it to start Mantella"
  fi
fi

# ---------------------------------------------------------------- 8. API key (location only)
step "8. API key"
if [ -s "$REPO_DIR/GPT_SECRET_KEY.txt" ] || [ -s "$REPO_DIR/secret_keys.json" ]; then ok "a key file exists in $REPO_DIR (not read)"
else
  todo "no key file in $REPO_DIR"
  manual "Put your LLM API key (OpenAI, OpenRouter, ...) on the first line of $REPO_DIR/GPT_SECRET_KEY.txt, then: chmod 600 GPT_SECRET_KEY.txt (the file is gitignored)."
fi

# ---------------------------------------------------------------- summary
manual "Game side (see MACOS.md): Skyrim SE 1.6.1170 (not 1.7.x), SKSE 2.2.6, Address Library, PapyrusUtil 4.6, SkyUI, UIExtensions, Mantella mod v0.14 - all builds for 1.6.1170."
manual "First start: double-click the launcher, speak once, and allow Terminal to use the microphone (System Settings > Privacy & Security > Microphone). For vision, also allow Screen Recording for Terminal."
manual "Open http://localhost:$PORT/ui once Mantella runs: choose the LLM service/model. Stop the server before editing config.ini by hand."

printf '\n%s== Manual steps%s\n' "$B" "$N"
i=1
for m in "${MANUAL_STEPS[@]}"; do printf '  %d. %s\n' "$i" "$m"; i=$((i + 1)); done
if [ "$DRY_RUN" -eq 1 ]; then
  printf '\n%sDry run: nothing was changed.%s Run again with --apply to make the changes above.\n' "$Y" "$N"
fi
[ "$WARNINGS" -gt 0 ] && printf '%s%d warning(s) above.%s\n' "$R" "$WARNINGS" "$N"
exit 0
