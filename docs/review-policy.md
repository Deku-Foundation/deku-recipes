# Recipe Review Policy

## Before a recipe is accepted

1. Confirm the source URL and pin an immutable revision.
2. Verify the source archive or repository content against an independently obtained digest.
3. Identify the applicable license and preserve required notices and source-offer obligations.
4. Review maintainership, upstream security policy, release cadence, and vulnerability history.
5. Declare runtime and build dependencies and explain optional features.
6. Inspect patches for necessity, scope, and upstreamability.
7. Build in an isolated unprivileged worker and record logs and provenance once the build system is available.
8. Test package contents, file ownership, permissions, metadata, and uninstall/upgrade behavior before promotion.

## Trust states

- **Draft:** metadata is being prepared; never consumed by release tooling.
- **Review:** awaiting source, license, build, and security checks.
- **Tested:** built and tested in a named environment; not necessarily suitable for release.
- **Approved:** reviewed for a specific channel and architecture, with evidence linked.
- **Deprecated:** should not be used for new installations; reason and replacement are documented.

The metadata-only prototype does not implement these trust states or authorize package publication. Human review and build evidence remain required.
