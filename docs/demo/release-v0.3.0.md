# v0.3.0 — Resume with evidence

Local crawler runs now retain pinned source checkpoints, reject changed engine
or raw inputs, and exclude concurrent writers. Explicit publication still needs
the reviewed candidate digest. Last-good data is never replaced by partial work.

Validation: 67 automated tests plus an actual cached-input interruption/resume
exercise. Repeated replay produced the identical 3,037-resource catalogue. The
published snapshot is unchanged. See recovery-results.md for exact evidence and
the separate fresh-context delivery-reconstruction exercise, which matched all
five fields from committed files and live GitHub evidence without prior turns.

No hosted crawler, model, credential, scheduler or heartbeat was added. A hard-kill
stale lock requires owner verification; this is not a power-loss durability claim.
