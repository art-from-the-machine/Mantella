# Mantella on macOS (Apple Silicon): FAQ

This page describes a working setup of Skyrim Special Edition + Mantella on an Apple Silicon Mac.
The game runs under Wine. The Mantella server runs natively on macOS from this repository.
It was tested on an M4 Pro with Skyrim SE 1.6.1170 and Mantella v0.14, using
[SkyrimMT](https://github.com/HorrorPills/skyrimmt) (Wine + DXMT) as the game launcher.

`scripts/macos/setup_mantella_mac.sh` automates the server side. The game side (game version,
SKSE, mods) still has to be done by hand. See [Is it easy to do yourself?](#is-it-easy-to-do-yourself)

---

## Is it possible?

Yes. NPCs hear you through your Mac's microphone, answer through an LLM, speak with Piper voices,
remember earlier conversations, and run in-game actions (follow, attack, trade, emotes and so on).

| Feature | Works on macOS? | How |
|---|---|---|
| Speech-to-text | Yes | Local Whisper (`faster-whisper`, CPU) or Moonshine, natively on macOS |
| LLM | Yes | Any API-based service (OpenAI, OpenRouter, ...). A local LLM server on the Mac works too |
| Text-to-speech (Piper) | Yes | The mod's Windows `piper.exe` runs through Wine, in a separate Wine prefix |
| Actions, memories, web UI (`http://localhost:4999/ui`) | Yes | Same as on Windows |
| Vision | Yes | Captures the main display with `mss`. Terminal needs Screen Recording permission |
| Lip sync (`.lip` files) | No | Needs FaceFXWrapper + FonixData under Wine. Not done yet; set `lip_generation = Disabled` |
| XTTS / xVASynth | Not tested | Both are Windows/NVIDIA-oriented |
| The mod's bundled `Mantella.exe` inside the game's Wine bottle | No (for voice) | See the next question |

## Why not just run the bundled Mantella.exe under Wine with the game?

It starts, and typed conversations work, but **the microphone doesn't**. macOS grants microphone access per
app. Game wrappers such as SkyrimMT don't declare `NSMicrophoneUsageDescription`, so anything they launch,
Wine and `Mantella.exe` included, gets silence without any prompt or error. Some launchers also kill their
wineserver when the game exits, which would take Mantella down with it.

Running the server from **Terminal** avoids both problems. macOS asks once whether Terminal may use the
microphone, and the server runs independently of the game. The mod still talks to it over
`http://localhost:4999` as usual. The bundled `Mantella.exe` has to be **switched off** (renamed). Otherwise
the mod starts it, and it takes port 4999.

## What do I need?

**Hardware / OS**
- An Apple Silicon Mac (M1 or later). 16 GB RAM is comfortable. Whisper `small` uses about 1 GB.
- About 6 GB free for the Python packages and Piper voices (the voices are 4 GB and ship with the mod).

**Game side (under Wine)**
- A Wine setup that runs Skyrim SE with SKSE. Tested with **SkyrimMT**. CrossOver should work the same way
  (not tested). Whisky is no longer maintained.
- **Skyrim SE 1.6.1170.** Mantella v0.14's SKSE plugins (`MantellaDialogue`, `MantellaLauncher`,
  `MantellaSubtitles`, `SKSE_HTTP`) are built for 1.6.1170. If Steam has updated you to 1.7.x, they don't
  load and nothing reaches the server. SkyrimMT can download and pin 1.6.1170 (Game tab → Skyrim version).
  Saves from 1.7.x may not load on 1.6.1170.
- Mods, **each in its 1.6.1170 build**:
  - SKSE64 **2.2.6** (skse.silverlock.org, "Anniversary Edition" build for 1.6.1170)
  - Address Library for SKSE Plugins (the all-in-one build covers 1.6.1170)
  - PapyrusUtil **4.6** (the 4.8 build targets 1.7)
  - SkyUI (for the MCM menu) and UIExtensions (for typing to NPCs)
  - Mantella **v0.14** (Nexus Mods, Skyrim SE mod 98631). Make sure `Mantella.esp` is enabled
  - If you use SSE Engine Fixes: the 1.6.1170 build (7.0.20). In SkyrimMT, its preloader `d3dx9_42.dll`
    has to deploy next to `SkyrimSE.exe` (put it in the mod's `__root__/` folder)
- With SkyrimMT, press **Deploy** after every mod change. Without it, mods aren't copied into the game.

**Mac side (native)**
- [Homebrew](https://brew.sh), with `portaudio` (pyaudio is built against it)
- **Python 3.11** (`brew install python@3.11` or `uv python install 3.11`). The pinned packages need it
- Git (`xcode-select --install`). [uv](https://docs.astral.sh/uv/) is optional and makes installs faster
- Wine for Piper: SkyrimMT's bundled Wine (`~/Games/skyrim/wine/bin/wine`) is used if present. Otherwise any
  `wine` on your PATH, or set `MANTELLA_WINE`
- An API key for your LLM service

## How do I set it up?

### 1. Game side (manual)
Install the game and the mods listed above. Launch the game once with SKSE and check that the SKSE log
lists the Mantella plugins as loaded, with no version errors.

### 2. Server side (the script)
```bash
git clone https://github.com/art-from-the-machine/Mantella.git   # or your fork with this guide
cd Mantella
scripts/macos/setup_mantella_mac.sh                          # dry run: reports only, changes nothing
scripts/macos/setup_mantella_mac.sh --apply --recommended-settings   # asks before each change
```
Options: `--skyrim-data DIR` (the deployed `Data` folder; SkyrimMT's default is found automatically),
`--wine PATH`, `--wine-prefix DIR`, `--launcher PATH`, `--port N`, `--yes`, `--skip-deps`, `--restore-exe`
(undo the rename). Run with `--help` for the full list. The script is idempotent: it skips steps that are already done.

What the script does:
1. Checks for macOS on arm64, git, Homebrew, Python 3.11 and `portaudio`. It offers to `brew install` the last two.
2. Creates `.venv` with Python 3.11 and installs `requirements-mac.txt`. That file is `requirements.txt` without
   `pywin32`, plus `playsound==1.2.2` + `pyobjc-framework-Cocoa` (newer playsound doesn't build on macOS),
   `setuptools<82`, and `mss` / `opencv-python-headless` for vision.
3. Installs **Moonshine** the way that works on macOS. Installing it through the pinned git URL fails, so the
   script clones it with `GIT_LFS_SKIP_SMUDGE=1` (the LFS model files are not needed, because the mod ships
   the models) and installs it with `--no-build-isolation`, so its `setup.py` uses the venv's `setuptools<82`.
4. Finds the Skyrim `Data` folder and checks for `Mantella.esp`, `Sound/Voice/Mantella.esp` (Mantella validates
   the folder by it), the SKSE plugins, Piper and the Moonshine models.
5. Renames `Mantella.exe` to `Mantella.exe.disabled-mac-native` in the deployed `MantellaSoftware` folder and,
   for SkyrimMT, in the mod's source folder. Press Deploy in SkyrimMT afterwards.
6. Creates a **separate Wine prefix for Piper** (default `~/Games/mantella-wine`). It isn't the game's prefix,
   so closing the game (which can kill the game's wineserver) never kills Piper mid-sentence.
7. Writes the macOS paths into `~/Documents/My Games/Mantella/config.ini`, after making a backup:
   `game = Skyrim`, `skyrim_mod_folder`, `piper_folder`, `moonshine_folder`, `lip_generation = Disabled`.
   With `--recommended-settings` it also writes the settings below. It refuses to edit the file while
   something is listening on the server port.
8. Writes a `Start Mantella.command` launcher (default on your Desktop). It starts the server in Terminal,
   points Piper at Wine (`MANTELLA_WINE`, `MANTELLA_WINEPREFIX`) and appends the output to `terminal.log`.

The script **does not** touch API keys. It only tells you where the key goes:
`<repo>/GPT_SECRET_KEY.txt` (first line, then `chmod 600`). The file is gitignored.

### 3. Doing it by hand instead
```bash
brew install portaudio python@3.11
python3.11 -m venv .venv
.venv/bin/pip install "setuptools<82" wheel
CFLAGS="-I$(brew --prefix)/include" LDFLAGS="-L$(brew --prefix)/lib" .venv/bin/pip install -r requirements-mac.txt
GIT_LFS_SKIP_SMUDGE=1 git clone --filter=blob:none https://github.com/usefulsensors/moonshine.git vendor/moonshine
GIT_LFS_SKIP_SMUDGE=1 git -C vendor/moonshine checkout 2f6282347950c8d711bd7319287babb87ec5a92d
.venv/bin/pip install --no-build-isolation ./vendor/moonshine/moonshine-onnx
```
Then rename `Mantella.exe` in the mod, create the Piper prefix (`WINEPREFIX=~/Games/mantella-wine wine wineboot -i`),
set the config values from step 7, and start the server with `.venv/bin/python main.py` from Terminal.

### Recommended settings (what worked on a Mac)
| Setting | Value | Why |
|---|---|---|
| `stt_service` / `whisper_model_size` | `Whisper` / `small` | `base` misheard a lot. `small` on CPU is still fast on Apple Silicon |
| `stt_language` | `en` (your language) | Auto-detection turned quiet English into other languages |
| `allow_interruption` | `False` | Without headphones, the NPC's voice from the speakers is picked up as your speech |
| `custom_function_model` | `False` | With a separate tool-calling model, conversations hung after an action ("Making second LLM call") |
| `lip_generation` | `Disabled` | No lip generation on macOS yet |

## How do I play?
1. Double-click **Start Mantella.command** and keep the Terminal window open. The first start downloads the
   Whisper model. Speak once and click **Allow** when macOS asks whether Terminal may use the microphone.
2. Open `http://localhost:4999/ui` once and choose your LLM service and model.
3. Start Skyrim. Cast the Mantella spell on an NPC (or use the MCM hotkey) and talk.

## Troubleshooting

**"Adding X to conversation" and then nothing happens.** The conversation quest is stuck, usually because the
server was restarted mid-conversation. Open the console (`~`), run `stopquest MantellaConversation`, and cast the
spell again. To avoid the console next time, bind MCM → Mantella → General → "End Conversation / Remove NPC".

**The game crashes on a key press (`EXCEPTION_ACCESS_VIOLATION` in `BSWin32KeyboardDevice`).** This was seen with
several macOS keyboard layouts installed (e.g. German and Russian) and the Steam overlay on the stack. Switch to
the U.S. layout before playing, and consider disabling the Steam overlay.

**My config changes disappear.** Mantella's web UI keeps the config in memory and rewrites all of `config.ini` on any
change. Stop the server, edit the file, and start the server again. Reload any open UI tab before using it.

**The NPC hears itself / answers its own lines.** Use headphones, or set `allow_interruption = False`.

**Speech is misheard or comes out in another language.** Set `stt_language` and use Whisper `small`. If your mic is quiet,
raise the input volume in System Settings → Sound, or tune `audio_threshold`. For debugging, `save_mic_input = True`
saves what the server heard as WAV files in `~/Documents/My Games/Mantella/data/tmp/mic`.

**No microphone input at all.** System Settings → Privacy & Security → Microphone → enable Terminal. This only works if
the server was started from Terminal, not from the game's Wine bottle.

**The NPC doesn't speak (Piper error).** Check that the launcher's `MANTELLA_WINE` points to a working Wine. Test it with
`WINEPREFIX=~/Games/mantella-wine wine <MantellaSoftware>/piper/piper.exe --help`.

**Vision returns nothing.** Allow Screen Recording for Terminal. Vision captures the **main** display, so run the game
on that display.

**Startup hangs at Hugging Face checks.** After the first successful start, uncomment `export HF_HUB_OFFLINE=1` in the launcher.

**Port 4999 is in use.** Another Mantella is running, maybe the bundled `Mantella.exe` because it wasn't renamed (or a
SkyrimMT deploy restored it). Run the script again.

## Is it easy to do yourself?

It's moderate. Expect **2–4 hours** the first time, most of it on the game side:

- **Server side (about 20 minutes with the script).** Without the script, the traps are the Moonshine install
  (Git LFS + build isolation), playsound on macOS, the Wine path for Piper, and the microphone permission. Each
  one cost real debugging time once.
- **Game side (1–3 hours).** Getting Skyrim SE 1.6.1170 running under Wine, then finding the matching
  build of every SKSE plugin. Without Nexus Premium, every download is a manual click. Version mismatches (SKSE or
  PapyrusUtil built for 1.7) fail silently, so check the SKSE logs.
- **Tuning (30 minutes).** Mic level, Whisper size and language, headphones.

If you already have a modded Skyrim 1.6.1170 running on your Mac, it's an evening's work. If you're starting from a
fresh Steam install that has auto-updated to 1.7.x, the downgrade is the main job.

## Code changes for macOS
- `src/tts/piper.py`: on non-Windows systems, `piper.exe` is started through Wine (`build_piper_command` /
  `find_wine`: `$MANTELLA_WINE` → SkyrimMT's bundled Wine → `wine`/`wine64` on PATH) with `WINEPREFIX` =
  `$MANTELLA_WINEPREFIX` (default `~/Games/mantella-wine`). Windows behaviour is unchanged.
- `src/image/image_manager.py`: on non-Windows systems, vision captures the main display with `mss` instead of
  logging "Vision LLM is supported only on Windows". Windows behaviour is unchanged.
- `requirements-mac.txt`: macOS dependency set (see above).
- Tests: `tests/tts/test_piper_wine.py`.
