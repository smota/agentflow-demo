# Recovery exercise evidence

## Local processing interruption

Actual commands ran in the project Python3.11 environment. An intentional
`--interrupt-after 1` exited the crawler after saving Rust's1,796 occurrences.
Resume verified that source, then processed Awesome671 and Node.js591. Assembly
produced3,037 unique resources from3,058 occurrences with the original canonical
digest `6765f04bb900eaf6d868e070613d7800faf2d0bec5d5d0577a65d23dc894d5f3`.
A second resume verified all three completed sources without adding records.

The published file stayed byte-for-byte unchanged at SHA-256
`25804156edbe403dfb684556e84445c345d1b8530cb119dc613b021fc748c90b`.
Only local staging and ignored checkpoints were written. No network is used by
published-input replay; the separate live-fetch fixture tests the normal path.

After a source-qualification hardening edit, the earlier `recovery-demo` checkpoint
was actually rejected for engine mismatch. A new `recovery-final` run repeated
the interruption/resume/idempotence sequence successfully. This is deterministic
fault injection with an actual process exit—not a power-loss or OS-crash test.

## Automated boundaries

67 tests pass, including changed checkpoint, engine, raw and accepted snapshot;
concurrent writer exclusion; valid-but-unreviewed candidate rejection; invalid
run paths; timeout retries capped at3; and no blind401/403/429 retry. Fixture
tests require neither network nor local raw caches.

## Fresh-context reconstruction

Pending: after the implementation checkpoint commit, a read-only helper will
reconstruct the five-field contract from committed files and GitHub only. Parent
will freeze writes during inspection and compare its result before continuing.
