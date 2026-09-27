# Third-party software and models

This source distribution contains our launcher, not llama.cpp or model weights.
The installer downloads the official llama.cpp Windows CPU release specified in
runtime.json and verifies the publisher's SHA-256 digest. llama.cpp is an
independent MIT-licensed project: https://github.com/ggml-org/llama.cpp
Its runtime archive and notices are preserved during extraction.

Python is separately installed for the source edition and has its own license.
A standalone executable built by the workflow bundles Python and Tcl/Tk through
PyInstaller; their applicable licensing notices and PyInstaller's bootloader
exception apply. See https://docs.python.org/3/license.html and
https://pyinstaller.org/en/stable/license.html.

Models retain their own licenses. Review the linked model card before downloading
or redistributing weights. A GGUF format or free download does not by itself
make a model open source. No model weights are included in this project.
