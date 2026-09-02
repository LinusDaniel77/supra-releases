# Supra by Silvia AI — public release notes

Release notes for [Supra](https://supra.silviaai.dev), the local-first AI mechanical engineer.

Customer installers are not public repository assets. Sign in through the
[Supra account portal](https://supra.silviaai.dev/account.html); an active
entitlement grants a short-lived download URL for the correct platform.

Supra's core CAD runtime runs locally and can use a user's own model-provider
credentials. Identity, subscriptions, device activation, protected downloads,
updates, and explicitly enabled cloud features are server-authorized. The
application source is developed in a private repository; this public repository
contains notes and build workflows, never customer binaries or update manifests.

The manual **Build macOS installer** workflow uses GitHub's standard native Mac runners,
checks out the private source with a read-only repository-scoped deploy key, executes Supra's
runtime self-test, verifies the DMG, and records its SHA-256 digest. Mac builds require a
Developer ID Application certificate and Apple notarization credentials; the workflow refuses
to continue unless `codesign`, `stapler`, and Gatekeeper accept the packaged app. When the
operator explicitly selects `publish`, the verified DMG goes to entitlement-gated private
storage—not a public GitHub release.
