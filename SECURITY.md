# Security policy

> This is the Supra app's security policy, published here with its installers. The files it names (`README.md`, `docs/`, `artifacts/`, `legal/`) are in Supra's private source repository; ask at the address below if you need one of them.

Supra runs model-generated code on your machine and holds your engineering work.
We would rather hear about a problem from you than from an incident.

## Reporting a vulnerability

Report it privately through GitHub's [private vulnerability reporting](https://github.com/LinusDaniel77/supra-releases/security/advisories/new) on this repository, or email **hello@silviaai.dev** with `SECURITY` in the subject. Please do not open a public issue.

Include what you need to make the issue reproducible: affected version
(Help → Supra by Silvia, or the installer filename), platform, steps, and
what an attacker gains. A proof of concept helps. **Do not include third-party
personal data or live credentials in a report** — describe where a secret is
exposed rather than pasting it.

If you believe the issue is being actively exploited, say so in the first line.
That changes our clock (see below), and we would rather over-react to a false
alarm than miss a real one.

## What we commit to

| Stage | Target |
|---|---|
| Acknowledgement that a human has read it | 2 working days |
| Initial assessment: is it real, how severe | 10 working days |
| Fix or documented mitigation for a confirmed high-severity issue | 90 days from acknowledgement |
| Credit in the release notes | On request, unless you prefer not |

We do not run a paid bounty. We will not threaten you with legal action for
good-faith research that follows this policy.

## Safe harbour

We consider security research conducted under this policy to be authorised, and
we will not pursue or support a claim against you for it, provided you:

- test only against your own installation and your own data;
- do not access, modify or exfiltrate anyone else's data;
- do not degrade the service for others, or run denial-of-service testing;
- do not use social engineering, physical attacks, or attacks on our staff or
  suppliers;
- give us a reasonable opportunity to fix the issue before publishing.

This is our position, not a licence to break third-party law, and it cannot bind
Anthropic, OpenAI, GitHub, Vercel or any other provider whose systems you might
reach through Supra. Report issues in their systems to them.

## Scope

**In scope**: the Supra desktop application and its bundled runtime, the local
backend and its localhost API, the sandbox boundary and the AST allowlist, the
updater and its release-artifact verification, credential storage, and
supra.silviaai.dev.

**Known and documented, so please do not report as new**: the subprocess sandbox
fallback is not a security boundary — that is stated in `README.md`, and Docker
mode is the boundary. Findings about *how* the fallback is selected, or about
escaping the Docker sandbox itself, are very much in scope.

**Out of scope**: anything requiring an attacker who is already running code as
your operating-system user (they can read your keys regardless, and the Terms
say so); model output quality, hallucination or an unsafe design — those are
safety reports, not vulnerabilities, and go to the same address described as
such; findings against third-party services.

## Coordinated disclosure and our reporting duties

We ask for 90 days before public disclosure, and we will usually be faster.

If a vulnerability in Supra — or in a component we ship — is **actively
exploited**, we have our own legal reporting obligations under Article 14 of the
EU Cyber Resilience Act, on a 24-hour clock, to ENISA and the relevant national
CSIRT. Those reports go to regulators, not to the public, and they do not
shorten your embargo or name you without your consent. Our internal process is
`docs/CRA-REPORTING-RUNBOOK.md`.

## What we ship, and how to check

Every release has a software bill of materials at
`artifacts/sbom/supra-sbom.cdx.json` (CycloneDX), generated from our lockfiles
plus `legal/bundled-native-components.toml`, which enumerates the native
libraries bundled inside our wheels — OCCT, GEOS, FFmpeg, OpenSSL and the rest —
that no dependency scanner sees. If you find something we ship that is not in
that file, that is itself a finding worth reporting.

Release artifacts are published with sha256 hashes at
https://github.com/LinusDaniel77/supra-releases. Obtain builds only from there
or from the official website.
