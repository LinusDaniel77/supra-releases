# Supra by Silvia AI — public beta releases

Release artifacts for [Supra](https://supra.silviaai.dev), the local-first AI
mechanical engineer.

## Separate Blender-native preview

[Supra 0.10.0-alpha.1](https://github.com/LinusDaniel77/supra-releases/releases/tag/v0.10.0-alpha.1)
is an experimental Windows launcher/source kit requiring a separate Blender 5.1.2
installation. It uses Blender's actual native interface and a fresh GPL-licensed
Supra extension. Complete extension source, tests, checksums and a manifest are
included. This is **not** a standalone installer or the full AI CAD product:
AI generation and exact B-rep/STEP CAD are not connected. It does not replace the
stable 0.9.1 installers or updater manifests.

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
