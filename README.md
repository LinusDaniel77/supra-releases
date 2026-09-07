# Supra by Silvia AI — public beta releases

Release artifacts for [Supra](https://supra.silviaai.dev), the local-first AI
mechanical engineer.

## Separate Blender-native preview

[Supra 0.10.0-alpha.2](https://github.com/LinusDaniel77/supra-releases/releases/tag/v0.10.0-alpha.2)
is a self-contained Windows x64 portable preview. Extract the entire portable ZIP
and open **Supra.exe**. No separate Blender installation or Supra account is needed:
the unmodified Blender 5.1.2 runtime is bundled privately.

It includes focused native workspaces, part/project metadata, inspection snapshots
and live bevel, pattern, mirror and mesh Boolean controls. This is **not** an
installer or the full AI CAD product: exact B-rep/STEP CAD and AI generation are
not connected. Stable 0.9.1 installers and updater manifests are unchanged.

The release includes the complete new Supra integration/launcher source, matching
Blender core and library-source archives, build instructions, preserved licenses,
checksums and a verification manifest. 29 runtime checks and 9 packaging tests pass.
It is unsigned; native visual verification and clean-machine testing are incomplete.
Read the release limitations before using it. Download page:
[Native preview](https://supra.silviaai.dev/native-preview/).

## Stable downloads

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
