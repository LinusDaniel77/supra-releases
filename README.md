# Supra by Silvia AI - Releases

Desktop installers for [Supra](https://supra.silviaai.dev), the local-first AI mechanical engineer.

Download the latest release from the Releases tab, or use the evergreen link:

- Windows: https://github.com/LinusDaniel77/supra-releases/releases/latest/download/Supra-Setup.exe
- Mac (Apple silicon): https://github.com/LinusDaniel77/supra-releases/releases/latest/download/Supra-Setup-Mac-arm64.dmg
- Mac (Intel): https://github.com/LinusDaniel77/supra-releases/releases/latest/download/Supra-Setup-Mac-x64.dmg

Supra runs entirely on your machine and uses your own Anthropic API key. The application source is developed in a private repository; this repository hosts release binaries and notes only.

The manual **Build macOS installer** workflow uses GitHub's standard native Mac runners,
checks out the private source with a read-only repository-scoped deploy key, executes Supra's
runtime self-test, verifies the DMG, records its SHA-256 digest, and publishes only when the
operator explicitly selects the `publish` input.
