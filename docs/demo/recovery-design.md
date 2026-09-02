# Recovery contract

The crawler has one writer lock for build/publish. Each named run atomically saves
discovery, all selected source revisions and completed per-source results. A
checkpoint digest detects accidental changes; an engine fingerprint rejects
resume after code changes. These hashes are integrity checks, not signatures or
protection from a malicious local administrator.

On resume, validate the checkpoint and every completed raw input before skipping
work. Merge once from the ordered per-source map, so replay cannot append duplicates.
Only a complete validated candidate reaches staging; only explicit digest-bound
publish can replace the last good catalogue. Refreshing discovery uses a new run
ID. Partial discovery before the first checkpoint may be safely repeated.

`--replay-published` reprocesses pinned local raw files from the accepted snapshot
through the same source loop, with networking forbidden by construction. An
explicit `--interrupt-after 1` raises after saving the first source. This is an
actual process exit induced by a deterministic fault, not an OS crash or power-loss
test. Resume repeats the same command without the injection flag.

Lock recovery is fail-closed. Normal exceptions release the lock; a hard kill may
leave it behind. Never remove a lock merely because it is old. Inspect the PID
and active commands first, then preserve the stale lock as an incident artifact
before a reviewed retry. No scheduler, daemon or heartbeat is installed.

A separate fresh-context Codex helper receives only the repository location and
read-only task: reconstruct current issue/branch/commit/findings/next action from
committed docs and GitHub, without local scratch or prior conversation. Parent
freezes mutations during that read and compares all five fields before continuing.
It is a simulated reviewer persona in an actual fresh-context harness boundary.
