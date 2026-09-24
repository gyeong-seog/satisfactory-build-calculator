# Code signing policy

## Status and provider

The project has applied for sponsored open-source code signing. Current release `v0.1.0` is unsigned; signed releases will be identified explicitly on their GitHub Release page after the application is approved.

Free code signing provided by [SignPath.io](https://about.signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).

## Team roles

- Committer and reviewer: [@gyeong-seog](https://github.com/gyeong-seog)
- Signing approver: [@gyeong-seog](https://github.com/gyeong-seog)

The project currently has one maintainer. Contributions from other people must be reviewed before merge. These roles will be updated if the maintainer team changes.

## Build and approval policy

- Release binaries must be built by GitHub Actions from this public repository and its checked-in build workflow.
- Only artifacts derived from a version tag in this repository may be submitted for release signing.
- Every signing request requires manual approval by the signing approver.
- Product name and version metadata are enforced in release binaries.
- SHA-256 checksums and GitHub build provenance attestations are published with releases.
- Unsigned and signed binaries must be labeled accurately; an unsigned binary must never be presented as signed.

## Privacy

This program does not transfer information to other networked systems. It stores only local interface settings on the user's device. See the full [Privacy Policy](PRIVACY.md).

## Verification

After signed releases become available, users can inspect the Windows Authenticode signature in the file properties or verify it with:

```powershell
signtool verify /pa /v SatisfactoryBuildCalculator.exe
```
