# Nila Assistant

**Your models. Your computer. Your assistant's name.**

[![Windows build](https://github.com/nadeemmhdm/nila-assistant/actions/workflows/windows.yml/badge.svg)](https://github.com/nadeemmhdm/nila-assistant/actions/workflows/windows.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Nila Assistant is an open-source Windows application for managing local GGUF models
and chatting through llama.cpp. **Nila is the project name; you choose your personal
assistant's name during setup.**

**Status:** v0.1.0 preview. Core tests are available; full Windows installation and
real-model smoke testing must be completed before calling a release production-ready.

[Download source ZIP](https://github.com/nadeemmhdm/nila-assistant/archive/refs/heads/main.zip) ·
[Windows builds](https://github.com/nadeemmhdm/nila-assistant/actions/workflows/windows.yml) ·
[Report a bug](https://github.com/nadeemmhdm/nila-assistant/issues) ·
[Security policy](SECURITY.md)

## Overview

An open-source local AI launcher. Choose your assistant's name during setup.
Download or import a single-file GGUF model, then chat through the native
**llama.cpp CLI or llama.cpp Web UI**. No Ollama, cloud inference API, API key,
voice mode, computer control, or agent tools are part of this release.

## Easy setup (source ZIP)

1. Extract the entire ZIP to a folder.
2. Double-click **Setup.cmd**. It installs the launcher for your Windows user
   and creates a desktop shortcut. If needed, it offers to install Python 3.12
   via Windows Package Manager. No pip packages are needed to run the source.
3. In the setup screen, enter **any assistant name** and click **Save assistant name**.
4. Click **Install llama.cpp runtime** (internet required once).
5. Open **Models**. Review a starter model's card/license and download it,
   or choose **Import existing GGUF**. Imports copy the file; the original is retained.
6. Return to **Setup & Chat**, select your model, and open **Web Chat** or **CLI Chat**.
7. **Unload model / Stop chat** releases model memory. Keep the manager open during chat.

Windows x64 Intel/AMD only. Python 3.10+ with Tkinter is supported. CPU-only defaults:
4 or fewer threads, 2,048 context tokens, batch 128, one active model.
8 GB RAM can be used with small quantized models; usable capacity depends on
Windows, other apps, the model and context length. Large models are not automatically
made compatible with limited RAM. Model language quality varies, including Malayalam.

## Native chat and the assistant name

The launcher passes your chosen identity through `-sys` to llama-cli, and
`systemMessage` in a generated UI config to llama-server. It also sets the model
alias to your name. Models can still fail to follow a system prompt.

The Web UI uses upstream llama.cpp branding and browser storage. Its saved user
preferences can override server defaults. After a rename, start a new chat. If an
old identity persists, use **Settings → Copy assistant identity prompt** in this
launcher and paste it into the native Web UI's system-message settings.

Web conversations are stored by the native UI in your browser, not GitHub. Use
its export feature for backups. CLI transcript persistence is not provided by
this launcher. Clearing browser data can remove chats. Changing the local port
changes the browser origin and therefore the visible history.

## Model management

- Starter catalog with links to model cards.
- Public HTTPS direct GGUF download URLs (including Hugging Face resolve URLs).
- Existing local single-file GGUF imports.
- Select / launch / unload / delete a managed model.
- Download progress, cancellation, disk-space checks and atomic file installation.
- Runtime SHA-256 verification. Custom model downloads are checked for GGUF magic
  and transfer completeness; their computed hash is recorded, but **not authenticated
  against the model publisher**. Only llama.cpp can validate full model compatibility.
- Failed downloads are removed; resume is not implemented in v0.1.
- Gated/private models: download them yourself according to their terms, then import.
- Split/sharded GGUF, vision projectors and non-GGUF weights are not supported.

Internet is needed for installing Python/runtime and downloading models. Once
installed, the launcher makes no network request when opening CLI chat; browser
chat communicates with the local llama-server on `127.0.0.1`. Optional native Web UI
integrations should remain disabled for offline use. No server tool flags are enabled.

## CLI

From a source checkout with Python installed:

```powershell
python main.py setup
python main.py models
python main.py import "C:\Models\my-model.gguf"
python main.py chat
python main.py web
python main.py download "https://huggingface.co/OWNER/REPO/resolve/main/MODEL.gguf"
python main.py delete "my-model.gguf"
```

For a built executable replace `python main.py` with `.\LocalAssistant.exe`.
Run without arguments to open the desktop manager. Exit CLI chat using the native
CLI controls or close its console. An OS-held lock prevents multiple managers from modifying the same data directory.
Close the desktop manager before using a CLI management command.

## Storage and uninstall

Program: `%LOCALAPPDATA%\Programs\LocalAssistant`.
Data/models/runtime/logs: `%LOCALAPPDATA%\LocalAssistant`.
For development/tests, `LOCAL_ASSISTANT_HOME` overrides the data directory.
To uninstall, close the app, delete the program folder and desktop shortcut.
Delete the data folder separately only if you want to remove downloaded models/settings.
Browser chat data must be removed separately in browser settings.

## GitHub publishing and executable builds

Source is maintained at https://github.com/nadeemmhdm/nila-assistant. Do not commit model weights,
runtime binaries, chat data or your local config. The `.gitignore` covers common cases.
The included workflow runs tests on Windows, parses the installer, builds a standalone
`LocalAssistant.exe` and uploads a ZIP artifact. That executable requires no separate
Python installation, but still downloads llama.cpp and your chosen model at setup.

After pushing: open **Actions → Windows build and tests → completed run → Artifacts**.
Download `LocalAssistant-Windows-x64`, extract its inner ZIP, then run Setup.cmd.
For easy public downloads without an Actions login, attach the inner ZIP and SHA256.txt
to a GitHub Release after Windows smoke testing. No Release has been published yet.

Developer build:

```powershell
python -m unittest discover -s tests -v
python -m pip install pyinstaller==6.16.0
python -m PyInstaller --noconfirm --clean --onefile --name LocalAssistant --add-data "runtime.json;." main.py
```

## Troubleshooting

- Runtime download error: check internet access to GitHub release downloads.
- DLL error: install the Microsoft Visual C++ x64 runtime from Microsoft's official site.
- Slow/out-of-memory: choose a smaller model, close other apps, lower context size.
- Port busy: change the port in Settings, then reopen Web Chat.
- Server exits: inspect `%LOCALAPPDATA%\LocalAssistant\server.log`.
- Invalid model: ensure a direct GGUF URL, not a model card HTML page.
- Python absent and winget unavailable: install official Python x64 with Tcl/Tk, rerun Setup.cmd.
- Corporate PowerShell restrictions: follow your administrator's policy; source can also
  run with `python main.py` without running the installer.

## Validation status

Core automated tests run in the development environment with mocked downloads and
processes. Real model inference, native Web UI, Windows installer execution and the
Windows executable build still require a Windows smoke test. This is a preview,
not a claim of production validation.

## Windows smoke-test checklist

- Clean Windows user: Setup.cmd detects/installs Python and creates shortcut.
- Save an English or Malayalam name; restart and confirm it persists.
- Install runtime, download a small GGUF and check download failure/cancel recovery.
- Open Web Chat and ask its name; confirm real generated response and new-chat history.
- Unload, open CLI, ask its name, and exit; verify no leftover llama process.
- Import a model from a path with spaces; switch models and delete the managed copy.
- Disconnect internet; test both chat modes again.
- Test the Actions-built exe on a machine without Python.

MIT licensed launcher. Third-party runtime and models retain their own licenses.
See THIRD_PARTY.md.


## Contributing

Bug reports and focused pull requests are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md)
for development and validation steps. Report security vulnerabilities privately as
explained in [SECURITY.md](SECURITY.md), not in public issues.

## Credits

Created and maintained by [Nadeem Muhammed](https://github.com/nadeemmhdm).
Inference and native chat interfaces are provided by the independent
[llama.cpp](https://github.com/ggml-org/llama.cpp) project.
