# Release credential boundaries

`flutter-build.yml` now defaults to validation. Publication and credential import require an
explicit `upload-artifact: true`, the `Kukutx/Viper` repository, and `main` or a tag. All
`pull_request*` events are rejected. `flutter-ci.yml` remains read-only and passes no secrets.

Only signing-availability booleans are workflow-wide. Android keystores, Windows signing
service credentials and Apple certificates/passwords are scoped to their signing steps.
Secret values are not interpolated into shell source. Historical quoted Apple identities
are parsed as one data value without `eval`; ad-hoc identity `-` is rejected.

Apple notarization credentials are written below `runner.temp`, not the checkout, and an
`always()` cleanup removes that file. Checkouts do not persist their repository token.

The two Android distribution routes use the same pinned JDK, SDK, NDK, build tools and
API-qualified Cargo entry as native validation. They no longer patch Gradle source or
substitute debug signing for Release. F-Droid and all four NDK entry scripts retain locked
Cargo resolution and use that same cross-compilation entry.

Run `python tools/release_policy.py` and the full `tools/tests` suite to check the policy.
Mutation tests reject missing release guards, secrets in workflow/job environments and
secret interpolation in shell commands. These checks do not execute real signing.

This is credential scoping, not a claim of complete release-job isolation: historical
packaging and signing still share a job. Protected environment approvals, independently
verified signed artifacts, installer/device regression, notarization and production
rollout remain separate acceptance requirements. None is implied by unit-test success.
