# AwesomeAwesomeness

A resource library built from publicly discovered Awesome lists with **50,000+ observed GitHub stars**. Crawling and processing run locally; the public Streamlit app serves a versioned, read-only catalogue.

[Open the live application](https://awesomeawesomeness.streamlit.app/) ·
[Releases](https://github.com/smota/agentflow-demo/releases) ·
[Acceptance evidence](docs/demo/acceptance.md)

The public app is deployed independently of this computer. The current checkout
version is in package.json; the running version and catalogue digest appear in
the app footer. Release closeout is recorded in the linked GitHub workstream.

![AwesomeAwesomeness desktop discovery](docs/demo/images/v0.2-desktop.png)

Actual v0.2 browser screenshot; later release checks are recorded separately.

- [Approved goal and acceptance matrix](docs/demo/goal.md)
- [Delivery story](docs/demo/story.md)
- [Recovery and operating instructions](docs/demo/runbook.md)
- [GitHub workstream](https://github.com/smota/agentflow-demo/issues/1)

## Agentflow baseline

This project uses Agentflow **v1.0.0**, pinned at `d61b3ca71189f872a6fd78373076f2aab787f2e0`. It was installed using that release's `init` command. Newer source-only provider/transaction contracts are not claimed as features of this baseline.

Run the stack-independent governance checks with Node.js 20+:

```sh
npm run check:workflow
```

## Run the app

Use Python 3.11 in a project-local environment. From this repository in PowerShell:

```powershell
$demoRoot = (Get-Location).Path
New-Item -ItemType Directory -Force .cache/tmp, .cache/pip | Out-Null
$env:TEMP = Join-Path $demoRoot '.cache/tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $demoRoot '.cache/pip'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m streamlit run app.py --server.address=127.0.0.1
```

For tests/local ingestion, use the same cache environment and install the locked
development dependencies instead:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
```

On POSIX, use `.venv/bin/python` and equivalent project-local environment variables.
The crawler is
never imported by the hosted entrypoint. No API key or model is needed.

```sh
.venv/Scripts/python.exe -m pytest -q --basetemp=.cache/pytest
.venv/Scripts/python.exe -m tools.crawl validate
.venv/Scripts/python.exe -m tools.crawl build --run-id refresh-20260902
# Review data/staging/catalogue.json and pinned raw/license evidence first.
.venv/Scripts/python.exe -m tools.crawl publish --expected-digest <reviewed-digest>
```

Local crawling requires an authenticated GitHub CLI (`gh`); it never prints tokens.
Set TEMP/TMP and install caches within the project as described in the runbook.
The generated candidate is not deployed until committed and promoted through PRs.

## Preview coverage

3,037 resources from three independently qualified CC0 source lists, selected from
39 search candidates on 2026-09-02. Source stars are observation-time facts, not
live counts. We extract primary Markdown list-item links; HTML/table-only content
and linked lists are not recursively ingested. Full source revisions, licenses,
query evidence and excluded-candidate reasons are in data/catalogue.json.
