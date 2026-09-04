<#
.SYNOPSIS
    Unattended entry point for the weekly local catalogue pipeline (Epic G / issue #52).

.DESCRIPTION
    This is the single wrapper script named in docs/adr/008-local-pipeline-scheduling.md: Windows
    Task Scheduler invokes this script on its weekly trigger, and this script invokes the actual
    pipeline sequence. It deliberately stays thin -- all sequencing, digest-recomputation and
    run-log logic live in tools/run_pipeline.py (Python, unit-tested by tests/test_run_pipeline.py)
    so this file has as little untested logic as possible.

    Responsibilities that belong here rather than in the Python module:
      - Resolve the repo root and the project's own virtualenv interpreter, so the task registration
        can stay a fixed one-line command regardless of where the maintainer's checkout lives.
      - Redirect the child process's combined stdout/stderr to a timestamped transcript file, so
        that even a catastrophic failure (e.g. the interpreter itself missing) leaves independent
        evidence outside tools/run_pipeline.py's own structured run-log -- matching the ADR's
        "Task Scheduler history is not a substitute for the wrapper script's own log content"
        design, in the direction the wrapper owns: a transcript survives even if the Python log
        was never written.
      - Propagate the child process's exit code as this script's own exit code, so Task Scheduler's
        "Last Run Result" is meaningful at a glance without opening any log.

    This script never publishes anything itself and never prompts for input -- every unattended-safe
    decision (including the digest-confirmation gate) is made inside tools/run_pipeline.py.

.PARAMETER RunId
    Optional pipeline run id. Defaults to tools/run_pipeline.py's own default (lists-<UTC date>).

.PARAMETER BatchSize
    Passed through to tools.lists enrich/profiles. Default 32 (16 for profiles, capped internally).

.PARAMETER Workers
    Passed through to tools.lists profiles. Default 4.

.PARAMETER Skip
    Optional list of early stages to skip (discover, enrich, profiles) -- testing/manual re-run
    only. stage/publish/validate always run.

.PARAMETER EnableCliInterpretation
    Opt into H2's optional headless-CLI eligibility interpretation stage (issue #53, Epic H). Off
    by default -- omitting this switch runs the exact same lists/projects sequence as before H2
    existed, with zero CLI-assisted stories.

.PARAMETER CliInterpretationBatchSize
    Passed through to tools.derive_interpretations build --batch-size when -EnableCliInterpretation
    is set. Defaults to tools.derive_interpretations's own default when omitted.

.EXAMPLE
    # What Task Scheduler runs weekly (see the registration command in the PR description):
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\run_pipeline.ps1

.EXAMPLE
    # A scoped manual test run against a throwaway run id, skipping the network-heavy early stages:
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\run_pipeline.ps1 `
        -RunId 'lists-test-epicg' -Skip discover,enrich,profiles
#>
[CmdletBinding()]
param(
    [string]$RunId,
    [int]$BatchSize = 32,
    [int]$Workers = 4,
    [string[]]$Skip = @(),
    [string]$LogDir,
    [switch]$EnableCliInterpretation,
    [int]$CliInterpretationBatchSize
)

$ErrorActionPreference = 'Stop'

# `-File`-invoked PowerShell (what Task Scheduler runs) does not parse a comma-joined command-line
# value into a [string[]] the way an in-session array literal would -- `-Skip a,b,c` arrives as one
# element "a,b,c", not three. Split defensively so both `-Skip discover,enrich` and
# `-Skip discover -Skip enrich` work identically.
$Skip = @($Skip | ForEach-Object { $_ -split ',' } | Where-Object { $_ })

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$PythonExe = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $PythonExe)) {
    Write-Error "Project virtualenv not found at $PythonExe. Create it (see README/docs/demo/list-data.md) before registering the scheduled task."
    exit 1
}

# .ToUniversalTime() rather than Get-Date -AsUTC: -AsUTC needs PowerShell 7+, and this script must
# run unattended under whichever powershell.exe Task Scheduler invokes, including Windows
# PowerShell 5.1.
function Get-UtcNow([string]$Format) { (Get-Date).ToUniversalTime().ToString($Format) }

$TranscriptDir = Join-Path $RepoRoot '.agent-runs\pipeline-runs\transcripts'
New-Item -ItemType Directory -Force -Path $TranscriptDir | Out-Null
$Stamp = Get-UtcNow 'yyyyMMddTHHmmssZ'
$TranscriptStem = if ($RunId) { $RunId } else { 'lists-' + (Get-UtcNow 'yyyyMMdd') }
$TranscriptPath = Join-Path $TranscriptDir "$TranscriptStem-$Stamp.log"

$PythonArgs = @('-m', 'tools.run_pipeline', '--batch-size', $BatchSize, '--workers', $Workers)
if ($RunId) { $PythonArgs += @('--run-id', $RunId) }
if ($LogDir) { $PythonArgs += @('--log-dir', $LogDir) }
foreach ($stage in $Skip) { $PythonArgs += @('--skip', $stage) }
if ($EnableCliInterpretation) { $PythonArgs += '--enable-cli-interpretation' }
if ($CliInterpretationBatchSize) { $PythonArgs += @('--cli-interpretation-batch-size', $CliInterpretationBatchSize) }

"[$(Get-UtcNow 'o')] run_pipeline.ps1 starting: $PythonExe $($PythonArgs -join ' ')" |
    Tee-Object -FilePath $TranscriptPath -Append | Write-Host

# No manual confirmation: tools.run_pipeline owns every unattended-safe decision, including the
# digest-confirmation gate before publish. This script only relays its exit code and output.
& $PythonExe @PythonArgs 2>&1 | Tee-Object -FilePath $TranscriptPath -Append | Write-Host
$ExitCode = $LASTEXITCODE

"[$(Get-UtcNow 'o')] run_pipeline.ps1 finished with exit code $ExitCode" |
    Tee-Object -FilePath $TranscriptPath -Append | Write-Host

exit $ExitCode
