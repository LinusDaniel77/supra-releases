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
runtime self-test, verifies signing/notarization, records its digests, and publishes to private
storage only when the operator explicitly selects the `publish` input.
