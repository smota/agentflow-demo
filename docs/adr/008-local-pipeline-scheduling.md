# ADR 008 — Local-machine scheduling mechanism for unattended weekly pipeline runs

**Status:** Accepted

**Date:** 2026-09-04

## Context

The crawl/enrich/publish pipeline (`tools.lists discover`, `tools.lists enrich`, `tools.lists
stage`, `tools.lists publish`, gated by `tools.lists validate`) currently only runs when a
maintainer or an interactive agent session drives each step by hand. That couples every data
refresh to an open session and burns interactive agent usage on work that does not need a model
watching each command.

Epic F (#51) is scoped to a decision only: pick the local-machine-only mechanism that will trigger
a full pipeline run unattended, on the maintainer's own Windows machine, on a weekly cadence.
Epic G (#52) implements the chosen mechanism; this ADR does not touch the OS or register anything.

Hard constraint carried over from the epic body and the approved execution plan: no GitHub
Actions, no hosted CI, no external server. The candidate set is local-only by construction — this
ADR compares mechanisms within that constraint, not whether to leave the machine at all.

### Candidates

1. **Windows Task Scheduler** invoking a single wrapper script (`schtasks`/`Register-ScheduledTask`
   registering a weekly trigger that runs one `.ps1` wrapper, which in turn calls the `tools.lists`
   pipeline steps in order).
2. **A local long-running scheduler process** — a Python process (e.g. built on `schedule` or
   `APScheduler`) or a persistent PowerShell loop that stays resident and fires the pipeline itself
   at the configured time, with no OS-level task registration.

### Evaluation criteria (from the epic's Requirements section)

- **No external/hosted dependency** — both candidates satisfy this trivially; not a differentiator.
- **Survives machine sleep/restart reasonably** — does the trigger still fire, unattended, after the
  maintainer's machine has slept, been rebooted, or was simply off at the scheduled time?
- **Inspectable logs for an unattended overnight run** — can the maintainer, the next morning,
  determine whether the run happened, when, and whether it succeeded, without having watched it?

## Decision

**Windows Task Scheduler, registering a single weekly trigger that invokes one PowerShell wrapper
script**, which then runs the pipeline steps in order and exits non-zero on the first failed step.

Rationale, criterion by criterion:

- **Sleep/restart survival.** Task Scheduler is an OS service, not a process the maintainer has to
  keep alive. The task definition persists across reboots automatically. Two task settings close
  the sleep/off gap directly: `Wake the computer to run this task` (fires even if the machine was
  asleep at the trigger time) and `If the scheduled start is missed, run the task as soon as
  possible` (catches a run whose trigger time fell while the machine was fully off). A long-running
  scheduler process has neither property — if the process itself is not running when the trigger
  time arrives (machine off, asleep, process killed, terminal closed), the run simply does not
  happen, and nothing catches up the missed run afterward. Making a long-running process durable
  across reboot/sleep would mean auto-starting it at boot and keeping it alive — which in practice
  means wrapping it in Task Scheduler (`At log on`/`At startup` trigger) or a Windows service
  anyway. That does not remove the dependency on Task Scheduler; it adds a second, redundant
  scheduling layer on top of it for no benefit.
- **Inspectable logs.** Both candidates can write their own log file. The differentiator is that
  Task Scheduler adds a second, independent evidence source for free: Task Scheduler history
  (Microsoft-Windows-TaskScheduler/Operational in Event Viewer) and `schtasks /query /tn <name> /v
  /fo list` record every trigger fire, start time, and Last Run Result exit code — even if the
  wrapper script itself crashed before writing anything. A resident scheduler process has no such
  independent witness: if the process itself dies silently (unhandled exception, OOM, the window
  being closed), there is nothing outside the process to show a run was ever supposed to happen.
  The wrapper script still owns the primary evidence: it redirects stdout/stderr from each pipeline
  step to a timestamped file, aborts the run at the first failing step (no partial `publish`), and
  exits non-zero on failure so the OS-level "Last Run Result" is itself meaningful at a glance.
- **Operational simplicity.** One task registration is a single command a human runs once
  (explicitly out of scope for this ADR/epic to execute — see Consequences). A resident scheduler
  process is an always-on Python/PowerShell process the maintainer must remember is running,
  restart after every reboot, and avoid accidentally closing — a standing operational burden with
  no offsetting benefit once the sleep/restart and logging gaps above are accounted for.

**Cadence:** weekly, Sunday 02:00 local time — a window unlikely to collide with interactive use of
the machine, chosen so a full run (crawl + enrich + stage + publish) has the whole early-morning
window to complete before the maintainer might want the machine for anything else. Epic G's
wrapper-script design should treat this as a starting default, not a hard requirement, since actual
overnight run duration is not known until Epic G packages and times the full pipeline.

## Consequences

- Epic G implements one PowerShell wrapper script that runs `tools.lists discover`, `tools.lists
  enrich`, `tools.lists stage`, `tools.lists validate`, and `tools.lists publish` in order, aborts
  and exits non-zero on the first failing step, and writes a timestamped log per run under a
  git-ignored local log directory.
- Epic G also produces the exact `schtasks`/`Register-ScheduledTask` registration command, with
  `Wake the computer to run this task` and the missed-start catch-up setting enabled, for the
  maintainer to run themselves — this ADR and Epic F do not register anything with the OS.
- The mechanism is inherently single-machine: if the maintainer's Windows machine is decommissioned
  or replaced, the scheduled task must be re-registered on the new machine. This is accepted as the
  direct consequence of the local-machine-only constraint, not a gap to fix later.
- Task Scheduler history alone is not a substitute for the wrapper script's own log content — it
  confirms a run fired and its exit code, not what the pipeline actually did. Epic G's wrapper
  script log is the primary evidence; Task Scheduler history is the secondary/independent witness
  used to catch the case where the wrapper never started at all.

## Alternatives considered

- **A local long-running scheduler process** (Python `schedule`/`APScheduler` loop or a persistent
  PowerShell loop) — rejected. Does not survive sleep/reboot/process-kill without itself being
  relaunched by Task Scheduler or a Windows service wrapper, which only reintroduces the same
  dependency this option was meant to avoid, while adding a standing "is it still running" burden
  and no independent (outside-the-process) record that a run was ever due.
- **GitHub Actions / hosted CI scheduled workflow** — out of scope by the epic's hard constraint;
  not evaluated. Would require pushing pipeline credentials/config to a hosted runner and moves the
  refresh off the maintainer's own machine entirely, which the epic explicitly rules out.
- **A cloud cron/serverless scheduler (e.g. a small VM or function on a timer)** — out of scope for
  the same reason: introduces an external server/account, which is the hard constraint this epic
  exists to avoid.
- **A third-party Windows scheduling utility (e.g. NSSM-wrapped service, Cronicle, etc.)** —
  rejected as unnecessary: Task Scheduler already ships with Windows, requires no additional
  install or trust boundary, and already provides the wake/missed-run/history features that would
  be the reason to reach for a third-party tool.
