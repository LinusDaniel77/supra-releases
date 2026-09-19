# Supra by Silvia AI — public beta releases

Release artifacts for [Supra](https://supra.silviaai.dev), the local-first AI
mechanical engineer.

## Separate Blender-native preview

[Supra 0.10.0-alpha.3](https://github.com/LinusDaniel77/supra-releases/releases/tag/v0.10.0-alpha.3)
is a self-contained Windows x64 portable preview. Extract the entire portable ZIP
and open **Supra.exe**. No separate Blender installation or Supra account is needed:
the unmodified Blender 5.1.2 runtime is bundled privately.

It includes focused native workspaces, part/project metadata, inspection snapshots
and live bevel, pattern, mirror and mesh Boolean controls. This is **not** an
installer or the full AI CAD product: native exact B-rep/STEP edits and mechanical
mates remain absent. An optional local connection to a separately running Supra
backend supports reviewed AI plans, Astra/Fable selection, job/evidence inspection
and derived STL previews. Backend/provider setup is not bundled, and AI requests
may incur provider charges. Held designs are never approved by importing a preview.
The native prerelease is excluded from the stable desktop updater.

The release includes the complete new Supra integration/launcher source, matching
Blender core and library-source archives, build instructions, preserved licenses,
checksums and a verification manifest. Packaged runtime checks and 23 client/packaging
tests pass; the manifest lists individual checks and the source revision.
It is unsigned; native visual verification and clean-machine testing are incomplete.
Read the limitations and download assets on the native preview release page above.

## Stable downloads

These recovery beta installers and updater assets remain publicly accessible.
The website's account and download service is managed separately in
`supra-landing`; this release repository is not proof that account onboarding,
licensing, or protected website downloads are production-ready.

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

Windows supports in-app update downloads and restart-to-install. Save your work
before restarting. The 0.11.5 Mac beta can download and stage its matching official
DMG, verify its checksum, bundle seal, identity and version, then restart to
replace a writable installed copy. Copies running from the DMG or a temporary
location retain the manual download path. Older Mac versions may need a one-time
manual update. The ad-hoc seal is an integrity check, not an Apple Developer ID
identity or notarization. Do not disable OS security protections.
