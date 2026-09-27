# Contributing to Nila Assistant

Keep contributions focused on the current scope: local text chat, model management,
and straightforward Windows setup. Discuss major new features in an issue first.

## Development

1. Clone this repository and install Python 3.10+ with Tkinter on Windows x64.
2. Run `python -m unittest discover -s tests -v`.
3. Run `python main.py` to open the manager.
4. Use a separate `LOCAL_ASSISTANT_HOME` directory for development if necessary.

The launcher uses the Python standard library. PyInstaller is needed only to
build a standalone executable. See README.md and the Windows workflow.

## Pull requests

Describe the problem, the behavior change and validation performed. Add meaningful
regression tests for changed download, path-handling or process-lifecycle behavior.
Never commit model weights, runtime binaries, tokens, local settings or private chats.
Keep native llama.cpp integration and offline operation clear and documented.

Before declaring a Windows release ready, complete the README smoke-test checklist.
Do not describe mock-based tests as real model or installer validation.

For bugs, provide Windows/Python versions, the commit or release, reproduction steps,
and redacted error output. For vulnerabilities, follow SECURITY.md instead of
opening a public issue. Be respectful and constructive in project discussions.
