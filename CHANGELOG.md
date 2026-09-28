# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.1] - 2026-09-28

First release published to PyPI, as `altissimo-shippo-tracking`. The import
name is unchanged (`altissimo.shippo_tracking`).

### Fixed

- `ShippoTrackingDetail` uses the tracking number as its Firestore document ID
  when no `id` is given. The validator meant to do this was never registered,
  so records saved without an explicit `id` got a random document ID, which
  `get_tracking_detail`/`delete_tracking_detail` couldn't find, and re-saving
  created duplicates. `ShippoService` always passed `id` explicitly, so records
  saved through it were not affected.

### Changed

- The distribution is renamed from `shippo-tracking` to
  `altissimo-shippo-tracking`.
- The `firestore` extra depends on `altissimo-firedantic>=0.22.4,<0.23`, the
  Altissimo fork of firedantic, replacing upstream `firedantic`. It is still
  imported as `firedantic`, so don't install upstream `firedantic` alongside it.
- Package metadata moved to the standard PEP 621 `[project]` table, with the
  licence declared as an SPDX expression.

### Added

- Integration tests for `ShippoRepo` against the Firestore emulator, run in CI.
- A publish workflow that uploads tagged releases (`v*`) to PyPI, and the
  current branch to TestPyPI when run by hand, through Trusted Publishing.

[Unreleased]: https://github.com/altissimo-hq/shippo-tracking/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/altissimo-hq/shippo-tracking/releases/tag/v0.2.1
