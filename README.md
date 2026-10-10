# Supra by Silvia: public beta releases

Supra is a free desktop app for Windows and Mac that turns a plain-English description of a part into parametric CAD. It asks only what it cannot build without, looks up or assumes the rest and lists every assumption, writes CadQuery code, runs it, checks the result, and hands you a STEP file and an STL along with a ledger. The ledger says what Supra measured, what it assumed, and what it could not check.

This repository holds the installers and the workflows that build them. The app's source code is private.

## Before you try it

- **It does not always deliver a part.** In our latest measured run (version 0.11.50, 8 and 9 October 2026), Supra with Sonnet 5.5 delivered **7 of 10** test prompts, including all three two-part assemblies. The three held back (a washer, a motor mount and an open-top enclosure) were each held by one check that misread the part. Every delivered part had at least one warning in its ledger. Version 0.11.52 fixes the ten problems that run found, but has not been measured yet. Read the ledger before you trust a result.
- **You need a free Supra account, and you must be 18 or older.** On first launch Supra asks you to sign in or create an account inside the app (email, password, date of birth, and a code we email you). Your designs still stay on your computer.
- **You bring your own model key and pay the provider.** Supra uses your own OpenAI or Anthropic API key; either one is enough. You pay that provider directly for every build and every chat turn.
- **It runs AI-written code on your computer.** Supra screens the generated code against an allow-list and runs it in a separate process, but that process is not a security sandbox. Use it on a computer where that is acceptable to you.
- **The checks are screens, not simulation.** Supra's load, heat, printability and fit checks are first-order screens with stated limits. They are not FEA or CFD. A qualified person must review anything that matters before it is made or used.
- **The installers are not signed.** Windows and macOS will warn you on first launch. The steps below get you past both, and the Windows note says when they cannot.

## Download

The latest release, straight from GitHub (no account needed to download):

| Platform | File |
|---|---|
| Windows 10 or 11, x64 | [Supra-Setup.exe](https://github.com/LinusDaniel77/supra-releases/releases/latest/download/Supra-Setup.exe) |
| Mac with Apple silicon, macOS 12 or later | [Supra-Setup-Mac-arm64.dmg](https://github.com/LinusDaniel77/supra-releases/releases/latest/download/Supra-Setup-Mac-arm64.dmg) |
| Mac with Intel, macOS 12 or later | [Supra-Setup-Mac-x64.dmg](https://github.com/LinusDaniel77/supra-releases/releases/latest/download/Supra-Setup-Mac-x64.dmg) |

Each installer is roughly 300 to 400 MB. The [latest release](https://github.com/LinusDaniel77/supra-releases/releases/latest) page shows the SHA-256 of every file. Each Mac `.dmg` has a `.sha256` file beside it; for Windows, `Supra-Setup-<version>.exe.sha256` covers `Supra-Setup.exe`, which is the same file under a versioned name.

## Install

### Windows

1. Run `Supra-Setup.exe`.
2. Microsoft Defender SmartScreen shows **Windows protected your PC**. Click **More info**, then **Run anyway**.
3. Follow the installer, then open Supra from the Start menu.

If **Smart App Control** is turned on (Windows 11), it blocks unsigned apps and offers no way to allow a single app. Supra cannot be installed on that PC until its installer is signed. Microsoft explains the setting in its [Smart App Control FAQ](https://support.microsoft.com/en-us/windows/security/threat-malware-protection/smart-app-control-frequently-asked-questions).

### Mac

1. Open the `.dmg` you downloaded and drag **Supra** onto the **Applications** folder. Eject the disk image afterwards, and always open Supra from Applications, not from the disk image.
2. Open Supra from Applications.
3. **On macOS 15 Sequoia or later:** macOS says it could not verify that Supra is free of malware. Click **Done** (not Move to Trash). Open **System Settings**, then **Privacy & Security**, scroll to **Security**, and click **Open Anyway** on the line about Supra. Confirm with Touch ID or your password, then click **Open Anyway** once more.
4. **On macOS 12 to 14:** Control-click **Supra** in Applications, choose **Open**, then click **Open** in the dialog.

macOS remembers your choice for that build. The Mac app carries an ad-hoc integrity seal, not an Apple Developer ID signature or notarization. Do not turn off macOS security protections to run it. The website walks through every click: [Mac first launch](https://supra.silviaai.dev/thanks/mac-arm64).

## First launch

1. Accept the Terms.
2. Sign in, or create a free account in the app.
3. In **Settings**, add your OpenAI or Anthropic API key. Supra stores it encrypted with your operating system (DPAPI on Windows, the Keychain on Mac).
4. Describe a part.

## What a build costs

You pay your model provider for every build. Measured on version 0.11.50 (8 and 9 October 2026), at each provider's published rates and including web search fees, with keys for both providers set, so each build also paid for an independent review by the other provider:

- **Sonnet 5.5:** $1.05 to $3.61 per prompt across the 10 test prompts, including the three held back, **$2.71 on average**, and $3.00 for a load-bearing bracket.
- **Opus 5.5:** $3.04 for the same bracket.
- **GPT 6 Astra:** $8.50 for the same bracket.
- **Fable 5.1:** $10.28 for the same bracket, measured on version 0.11.49 (7 October 2026); it was not measured on 0.11.50.

These are one run's figures, not a guarantee: a harder part, a longer conversation or a repair round costs more.

What pushes the cost up, all on by default: up to 8 billed web searches to research the request, an engineering concept step before the geometry (with an Anthropic model it can run more billed searches, up to 6 per model call), up to three candidate designs on harder parts, and up to three attempts per candidate.

**Supra has no spend cap or low-cost mode in the app yet.** Set a monthly spending limit in your provider's console before you start.

## What leaves your computer

Supra has **no telemetry**: it sends no analytics or usage data to us.

- **Your projects, CAD files, versions and conversations** are stored on your computer.
- **When you build or chat with Supra AI,** Supra sends your messages, any images you attach, and the engineering context it needs to the model provider you selected. Its web searches also run through that provider and are billed to you. If you entered keys for both providers, a hard build may also be sent to the other one for an independent review.
- **Your account:** creating an account sends your email, password, date of birth and an optional name to Supra's account service; signing in sends your email and password. The service also keeps your app preferences. The [Privacy Policy](https://supra.silviaai.dev/legal/privacy) covers this.
- **Update checks:** about 45 seconds after launch, and every 6 hours while it runs, Supra fetches a small update file from this repository's releases. Windows downloads and installs updates in the app, with a restart. On a Mac, a copy in Applications updates itself if your macOS account can write to it; a copy run from the disk image, or one your account cannot replace, must be updated by hand.

## Demo

A short recording of a real build, from prompt to STEP file and ledger with its real cost on screen, is being made. It will be linked here. Until then, judge Supra by the ledger of your own first build.

## Report a problem

[Open an issue](https://github.com/LinusDaniel77/supra-releases/issues/new/choose). Please include:

- the Supra version (switch to Studio and read the bottom-right corner of the window, or on a Mac choose **Supra**, then **About Supra**) and your OS;
- the model shown in the model picker beside the chat box;
- what you asked for, and what happened;
- a screenshot of the build's **Checks** tab, which shows its ledger. If the build was delivered, you can attach the full ledger instead: in Studio, click the **Exports** tab at the bottom, then **Release package**, then **Build release**. This writes `manifest.json` into Supra's data folder under `artifacts/releases`;
- if Supra crashed or hung, `backend.log`. In **Settings**, under **Data**, click **Open folder** next to **Data folder**; the log is in the `logs` folder one level up from the folder that opens.

Never paste an API key, a password or anyone else's personal data into an issue.

Security problems go privately, not in an issue: see [SECURITY.md](SECURITY.md).

## Other downloads

[Supra 0.10.0-alpha.3](https://github.com/LinusDaniel77/supra-releases/releases/tag/v0.10.0-alpha.3) is an older, separate Blender-based Windows preview. It is not the Supra app above and does not update to it.

## How releases are built

The Windows and Mac workflows in this repository build each installer from the private source, test the packaged app, record a checksum, and publish it. A separate workflow, started by hand, installs a published release on clean Windows and Mac runners and, on Windows and Apple silicon Macs, upgrades to it from the previous stable release, checking that the user's data survives; it has not been run for every release. These checks prove that an installer installs and starts. They do not prove that a build delivers a correct part.
