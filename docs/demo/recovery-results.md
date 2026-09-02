# Recovery exercise evidence

## Local processing interruption

Actual commands ran in the project Python 3.11 environment. An intentional
`--interrupt-after 1` exited the crawler after saving Rust's 1,796 occurrences.
Resume verified that source, then processed Awesome 671 and Node.js 591. Assembly
produced 3,037 unique resources from 3,058 occurrences with the original canonical
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
run paths; timeout retries capped at 3; and no blind 401/403/429 retry. Fixture
tests require neither network nor local raw caches.

## Fresh-context reconstruction

A fresh-context read-only Codex helper (`recovery_observer`, no inherited turns)
received only the repository location and observation instructions. It read
committed policy/docs, the actual checkout and live GitHub evidence—not scratch
or prior conversation. Parent froze writes during the inspection.

| Field | Reconstructed and matched |
| --- | --- |
| Issue | Open #6, standard profile |
| Branch | work/recovery, tracked checkout clean |
| Exact commit | 5fe6b2411b28ab9bb1f4546d2b51e36c537b6379, equal to remote |
| Findings | No open blockers; tester/review/PR/release acceptance still pending |
| Next action | Completed developer phase 4 → tester phase 5; compare reconstruction, then rerun verification after ending freeze |

All five fields matched. The helper correctly reported absent PR/CI as pending,
not failed, and did not pretend to have rerun the 67 tests. Parent ended the
freeze and reran all 67 tests successfully. No duplicate issue, PR, release or
second writer was created. This is actual fresh-context recovery with a
simulated reviewer persona, not real human approval or cross-platform review.

Durable sources: [signed handovers](https://github.com/smota/agentflow-demo/issues/6#issuecomment-5516163227),
[workflow status](https://github.com/smota/agentflow-demo/issues/6#issuecomment-5516163479),
[frozen commit](https://github.com/smota/agentflow-demo/commit/5fe6b2411b28ab9bb1f4546d2b51e36c537b6379).
