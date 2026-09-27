# ആദ്യം ചെയ്യേണ്ടത്

1. ZIP മുഴുവനായി Extract ചെയ്യുക.
2. `Setup.cmd` double-click ചെയ്യുക.
3. Python ഇല്ലെങ്കിൽ installation ചോദിക്കും; `Y` നൽകുക.
4. App തുറക്കുമ്പോൾ ഇഷ്ടമുള്ള assistant name നൽകി Save ചെയ്യുക.
5. `Install llama.cpp runtime` click ചെയ്യുക.
6. Models tab-ൽ നിന്ന് model download ചെയ്യുക അല്ലെങ്കിൽ existing `.gguf` import ചെയ്യുക.
7. Setup & Chat tab-ൽ model select ചെയ്ത് Web Chat / CLI Chat തുറക്കുക.
8. അവസാനിക്കുമ്പോൾ Unload ചെയ്യുക; ശേഷം app close ചെയ്യുക.

Desktop-ൽ Local Assistant shortcut ഉണ്ടാകും. ആദ്യ setup/download-ന് internet വേണം.
Download കഴിഞ്ഞാൽ local chat ഉപയോഗിക്കാം. വലിയ model എടുത്താൽ 8GB laptop slow ആകാം.

ഇത് source preview ആണ്. Ready-made Windows EXE ഇതിൽ ഉൾപ്പെടുത്തിയിട്ടില്ല.
GitHub Actions workflow വഴി EXE build ചെയ്യാം. ഇവിടെ core tests pass ആയിട്ടുണ്ട്;
Windows installation, real AI responses എന്നിവയുടെ smoke test ബാക്കിയുണ്ട്.

GitHub publish ചെയ്യാൻ ഈ folder-ന്റെ contents (hidden .github folder ഉൾപ്പെടെ)
പുതിയ repository-ൽ push ചെയ്യണം. Model files upload ചെയ്യരുത്.
