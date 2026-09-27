# Security policy

Nila Assistant is a local, single-user Windows application. Security reports are
welcome. The project is an early preview and has not undergone an independent
security audit.

## Supported versions

| Version | Security maintenance |
| --- | --- |
| Latest `main` / 0.2.x preview | Best-effort fixes |
| Older snapshots or modified forks | Upgrade or reproduce on the latest version |

There is no guaranteed response time, service-level agreement, or bug bounty.

## Reporting a vulnerability

Send a private report to **nadeem@qezvo.in** with the subject
`[Nila Assistant Security] brief summary`.
If GitHub private vulnerability reporting is enabled, the repository's Security
tab offers another private reporting route; its availability is not guaranteed.

Include:

- Affected commit/version, Windows version and relevant configuration.
- A concise description of the issue and its potential impact.
- Minimal reproduction steps or a non-destructive proof of concept.
- Redacted logs or screenshots, and any proposed mitigation.

Do not publish exploit details in public issues before coordination with the
maintainer. Do not include tokens, private chats, model access credentials,
personal files, or unnecessary personal information in a report.

The maintainer will review reports as capacity permits, request clarification
when needed, and coordinate fixes and disclosure. Please allow time for review
before public disclosure. Test only systems you own or have permission to test.

## Security boundaries

- The Web UI server binds to `127.0.0.1`; it is not designed as a public service.
  Do not expose it through port forwarding or a public reverse proxy.
- Each server load gets a random API key, passed to the child process environment.
  Nila Chat sends it as an Authorization header; it is not saved in preferences.
  Native Web UI users must enter the temporary key themselves.
- Loopback binding and a session key are not isolation from other local programs.
  Use the application only on a trusted Windows account/device.
- The launcher does not enable llama.cpp server tools or an MCP proxy. It does
  not intentionally grant the model shell or filesystem tools.
- Downloads require HTTPS. The pinned llama.cpp ZIP is verified against its
  recorded SHA-256 digest. A digest does not replace trust in the upstream publisher.
- Custom GGUF downloads are checked for transfer completeness and a GGUF header;
  their recorded hash is not checked against a publisher-provided checksum.
- Model weights are parsed by native llama.cpp code. A model file is not a
  security sandbox. Obtain models and runtime binaries from trusted sources.
- Nila saved facts/history are opt-in and encrypted using Windows CurrentUser DPAPI.
  Encryption failures do not fall back to plaintext. Same-account malware can still
  access process memory/decrypt files; this is not a sandbox. Configuration and model/voice
  files are not encrypted. Native browser history is separate and not DPAPI-protected.
- Diagnostic logs are off by default. Enabling them may record sensitive data.
  Synthesized WAV audio is kept in RAM; no audio cache files are written.
- Clear memory removes the current app file, not backups or forensic remnants.
- Source setup may install Python through winget after confirmation. The optional
  speech installer installs Piper from PyPI in a separate environment; voice models
  are downloaded from Hugging Face. These models are not sandboxed and do not yet
  have pinned publisher digests. Review model cards/licenses and trust their publishers. Runtime and
  model downloads contact their respective hosts. No cloud inference service
  or telemetry is implemented by this launcher.

## Dependencies and responsible use

llama.cpp, Python, Tcl/Tk, PyInstaller, model files and Windows have independent
security/update lifecycles. The runtime is pinned in `runtime.json`; upgrades
must update both its URL and checksum and be validated before release.

If a finding belongs to an upstream component, report it to that project's
maintainers as appropriate and notify this project if its configuration is affected.
Generated responses can be incorrect and must not be treated as trusted commands.
