# AwesomeAwesomeness

A resource library built from publicly discovered Awesome lists with **50,000+ observed GitHub stars**. Crawling and processing run locally; the public Streamlit app serves a versioned, read-only catalogue.

**Status:** foundation in progress; no application release or public deployment yet.

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

Application setup and public URL will appear with the first working release.
