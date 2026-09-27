# Nila Assistant

**Your models. Your computer. Your assistant's name.**

[![Windows build](https://github.com/nadeemmhdm/nila-assistant/actions/workflows/windows.yml/badge.svg)](https://github.com/nadeemmhdm/nila-assistant/actions/workflows/windows.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A Windows x64 local AI assistant powered by llama.cpp, with model management,
streaming chat, encrypted optional memory, and downloadable offline speech voices.
**Nila is the project name; choose your personal assistant's name during setup.**

**Version 0.2.0 — preview.** No Ollama or cloud inference API is required.

[Source ZIP](https://github.com/nadeemmhdm/nila-assistant/archive/refs/heads/main.zip) ·
[Windows builds](https://github.com/nadeemmhdm/nila-assistant/actions/workflows/windows.yml) ·
[Issues](https://github.com/nadeemmhdm/nila-assistant/issues) · [Security](SECURITY.md)

## Features

| Area | Included |
| --- | --- |
| Models | Download starter models or direct GGUF URLs; import, select, load, unload and delete |
| Chat | Token streaming in Nila desktop Chat and enhanced CLI; native llama.cpp interfaces remain available |
| Memory | Bounded recent exchanges and up to 50 explicit saved facts; inspect, forget, clear |
| Persistence | Opt-in Windows CurrentUser DPAPI encryption for saved Nila chat/facts |
| Speech | Incremental sentence/phrase playback while generation continues; stop speech independently |
| Voices | Download English Amy/ Lessac and Malayalam Meera Piper voices |
| Settings | Context, CPU threads, batches, loading mode, warmup, startup loading, reply limit, memory capacity and speech rate |
| Local API | Loopback binding and a random session API key; no shell/file tools enabled |

## Install and start

### Windows executable

Open a **successful Windows build** from the builds link above. Download its
`LocalAssistant-Windows-x64` artifact, extract the inner ZIP, and run **Setup.cmd**.
The executable includes the launcher runtime. Optional Piper speech may install
Python 3.12 separately. GitHub Actions artifact downloads require GitHub sign-in.

### Source ZIP

Extract the source ZIP and double-click **Setup.cmd**. The setup script detects
Python with Tkinter, offers a per-user Python installation through winget if needed,
and creates a desktop shortcut. Core chat needs no third-party Python packages.

1. **Setup:** enter an assistant name and save it.
2. Install the llama.cpp runtime.
3. **Models:** review the model card/license, then download or import a single-file GGUF.
4. **Setup:** select it and click **Load model → Nila Chat**.
5. **Chat:** type a message; output appears as it is generated.
6. Use **Unload model** to release model memory.

For an 8 GB CPU laptop, begin with a small quantized model, 2,048 context tokens and
short replies. Model ability, Malayalam quality and speed vary by hardware/model.

### Download and setup using PowerShell

Run in a folder where you want to extract the source:

```powershell
Invoke-WebRequest 'https://github.com/nadeemmhdm/nila-assistant/archive/refs/heads/main.zip' -OutFile 'nila-assistant.zip'
Expand-Archive '.\nila-assistant.zip' -DestinationPath '.\nila-source'
& '.\nila-source\nila-assistant-main\Setup.cmd'
```

Or from a source checkout with Python installed:

```powershell
python main.py setup --name "Nila" --model small
python main.py chat
```

This downloads the pinned Windows CPU runtime and the small starter model. Existing
matching model downloads are reused by setup. Replace `small` with `balanced` or a
public direct GGUF URL. Internet is needed for initial software/model/voice downloads.

## Memory and user data

Nila Chat keeps recent exchanges in RAM. **Persistence is OFF by default.** Enable
**Save encrypted memory between sessions** in Settings to retain facts and conversation
history. The encrypted `memory.dpapi` file is bound to your Windows account; there is
no plaintext fallback if encryption/decryption fails.

- **Memory → Add memory fact:** explicitly choose what should be remembered.
- **Forget selected fact:** remove one fact.
- **Clear all Nila memory:** remove facts and history.
- **New chat:** clear conversation history but preserve facts.
- **Remembered exchanges:** limits recent complete user/assistant pairs (default 12).
- **Saved memory cap:** limits serialized memory payload (default 256 KB).
- **Include conversation and facts:** controls whether stored context is sent to the model;
  it is separate from persistence.

Older conversation pairs are dropped when they exceed the configured capacity or the
active model's token budget. The current prompt is token-counted using llama.cpp's
chat template and tokenizer. Saved facts are never silently discarded to fit a prompt;
if facts/current input are too long, shorten them or increase context and reload.

Settings, model/voice files and assistant name are not encrypted. Nila memory encryption
does not protect against software running as your Windows account or a compromised OS.
Clear removes the app's file; it is not forensic secure erasure of disks/backups.
Diagnostic server logs are OFF by default and may contain sensitive information if enabled.
No response audio files are written; synthesis and playback use RAM.

**Native Web UI history is separate browser storage, not DPAPI-encrypted Nila memory.**
Memory and auto-speech integration apply to Nila Chat and the enhanced CLI, not to the
upstream native Web UI or native CLI. Clear/export native browser data there separately.

## Offline speech

1. Open **Voice → Install speech engine**. This installs optional Piper 1.8.0 into
   an isolated local Python environment. Review the GPL dependency notice below.
2. Select a voice, open its model card/license, then **Download selected voice**.
3. Click **Use selected voice** and **Test voice**.
4. Unload the model if necessary. In Settings, enable **Speak while generating** and Save.
5. Reload the model and use Nila Chat.

| Voice ID | Language |
| --- | --- |
| `en_US-amy-low` | English |
| `en_US-lessac-medium` | English |
| `ml_IN-meera-medium` | Malayalam |

Choose the appropriate voice yourself; automatic language switching is not implemented.
English voices are not a substitute for a Malayalam voice. Audio begins when a sentence
or bounded phrase arrives and has been synthesized, not literally on the first token.
The voice worker remains loaded between sentences. It skips fenced code and reasoning
fields, preserves sentence order, and stops speech if its bounded queue falls behind.
Use **Stop speech only** to stop playback without cancelling the text response.

TTS competes with inference for CPU/RAM. Streaming improves perceived responsiveness;
it does not guarantee higher model tokens/second. Lower maximum reply tokens/history,
use a smaller model, or disable speech when generation speed matters most.

## CLI reference

Use `.\LocalAssistant.exe` instead of `python main.py` for the standalone build.
Close the GUI before running a separate CLI process; an OS-held lock prevents concurrent
managers from modifying the same data.

```powershell
python main.py setup --name "Nila" --model small --speech --voice ml_IN-meera-medium
python main.py models
python main.py download balanced
python main.py import "C:\Models\my-model.gguf"
python main.py chat --model "my-model.gguf" --speak
python main.py settings list
python main.py settings set context 4096
python main.py settings set persist_memory true
python main.py memory add "Prefer Malayalam answers."
python main.py memory list
python main.py memory forget 1
python main.py memory clear
python main.py voice list
python main.py voice install
python main.py voice download ml_IN-meera-medium
python main.py voice use ml_IN-meera-medium
python main.py voice test
python main.py voice delete en_US-amy-low
python main.py delete "my-model.gguf"
python main.py web
python main.py native-chat
```

Inside enhanced `chat`: `/quit`, `/new`, `/remember FACT`, `/memory`, `/forget NUMBER`,
`/clear`, `/unload`, `/load FILENAME`, `/stop-speech`. Ctrl+C during generation cancels
and unloads the model; partial responses are not committed to memory. The GUI's
**Stop generation + speech** also unloads the model to interrupt native inference.

`load --model FILENAME` holds a model in the foreground until Enter. `web` also opens
the native browser UI and prints its temporary API key. Paste that key into the native
UI's API-key setting. Keys change every load and are not persisted in Nila configuration.
Do not expose the server publicly or share its session key.

## Loading and initialization settings

Settings are validated and must be saved with the model unloaded in the GUI.
Defaults: at most 4 CPU threads, context 2,048, batch/micro-batch 128, mmap loading,
warmup enabled, one loaded model, 512 reply tokens, 300-second load timeout.

`mmap` lets the OS map model files; `none` selects loading without that mode. Changing
context/loading settings requires a reload. Autoload is optional and starts only an
already-selected local model. No models/voices are downloaded on ordinary app startup.
The low-memory preset uses shorter replies/history; it is not a hardware benchmark.

## Limitations and troubleshooting

- Windows x64 Intel/AMD only; CPU inference. No voice input/wake word in this release.
- Single-file GGUF text models only; no split weights, projectors or non-GGUF formats.
- Gated/private models must be downloaded independently and imported.
- Downloads are atomic but not resumable. Failed/incomplete files are removed.
- Runtime ZIP uses a pinned SHA-256. Custom model and voice downloads use HTTPS and
  basic validation, not publisher-verified checksums. Use trusted sources.
- Speech installation requires internet/PyPI and Python with compatible wheels.
- DLL errors: check the official Microsoft Visual C++ x64 runtime.
- Load failure: try a smaller compatible model, adjust timeout, or temporarily enable
  diagnostic logs. Do not publicly share unredacted logs.
- Port busy: choose a free local port and reload.
- Wrong browser name: reset its saved system-message setting and start a new conversation.

Program: `%LOCALAPPDATA%\Programs\LocalAssistant`.
Data: `%LOCALAPPDATA%\LocalAssistant` (override with `LOCAL_ASSISTANT_HOME`).
To uninstall, close the app and delete program/shortcut. Remove data separately only
when you intend to remove downloaded models, voices, speech environment and memory.

## Development and validation

```powershell
python -m unittest discover -s tests -v
python -m pip install pyinstaller==6.16.0
python -m PyInstaller --noconfirm --clean --onefile --name LocalAssistant --add-data "runtime.json;." --add-data "speech_worker.py;." --add-data "voice_setup.ps1;." main.py
```

The Windows workflow runs unit tests (including actual DPAPI roundtrip), installer
syntax checks and EXE smoke testing. Its separate integration job downloads a small
model and English/Malayalam voices, verifies unauthorized API calls are rejected,
streams a real reply, reloads encrypted memory and synthesizes in-memory WAV audio.
Check the workflow result for the specific commit; code presence does not mean a test passed.
Manual installation, physical speaker playback and performance on an 8 GB laptop still
need real-user validation. No production security-audit claim is made.

Contributions: [CONTRIBUTING.md](CONTRIBUTING.md). Vulnerabilities: [SECURITY.md](SECURITY.md).

## License and credits

MIT-licensed launcher by [Nadeem Muhammed](https://github.com/nadeemmhdm).
[llama.cpp](https://github.com/ggml-org/llama.cpp) provides inference/native chat.
Optional [Piper](https://github.com/OHF-Voice/piper1-gpl) is GPL-3.0-or-later software
installed separately; model/voice licenses remain independent. No weights are included.
See [THIRD_PARTY.md](THIRD_PARTY.md).
