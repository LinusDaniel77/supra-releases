# Supra by Silvia AI — public beta releases

Release artifacts for [Supra](https://supra.silviaai.dev), the local-first AI
mechanical engineer.

The current free beta requires no Supra account, subscription, entitlement, or
device activation. Versioned Windows and macOS installers, updater metadata,
release notes, and SHA-256 checksums are public release assets.

Supra's CAD runtime runs locally and can use the user's own model-provider
credentials. The application source is developed in a private repository; this
public repository contains the public release workflows and artifacts.

The Windows workflow checks out the private source with a repository-scoped,
read-only deploy key, assembles and self-tests the runtime, verifies the NSIS
installer and updater manifest, records a checksum, and publishes the assets.

The macOS workflow builds natively for Apple silicon and Intel, self-tests the
packaged application, verifies the DMG container, and records a checksum. The
current beta DMGs are not Developer ID signed or Apple-notarized, so macOS may
require Control-click → Open on first launch.
