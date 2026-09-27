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


## Optional speech components

Piper 1.8.0 (https://github.com/OHF-Voice/piper1-gpl) is GPL-3.0-or-later.
It is installed from PyPI into a separate local Python environment and invoked by
a subprocess helper; the Windows launcher EXE does not bundle Piper or voice weights.
Piper's dependencies retain their licenses. Review those obligations before
redistributing a speech-enabled environment. The MIT license applies to this
project's own code and does not relicense its dependencies.

Voices are downloaded from https://huggingface.co/rhasspy/piper-voices.
Each download includes its MODEL_CARD; voice/dataset licenses can differ.
The catalog offers en_US-amy-low, en_US-lessac-medium and ml_IN-meera-medium.
These are general speech synthesis voices, not custom voice clones.
