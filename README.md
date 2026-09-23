# JevBrow

**Pre-alpha 0.1** · Local browser tools for Codex, backed by your own Brave or Chrome session.

JevBrow connects to a browser through the Chrome DevTools Protocol (CDP) and exposes a small set of MCP tools. Codex reads the visible page, chooses an action from JevBrow's observed list, and receives a new observation after each action. The MCP server does not call a second model or require a model API key.

> This is an early release. It handles common HTML controls and still needs supervision on consequential actions.

## What it does

- Opens a background tab owned by JevBrow in a browser that is already running locally.
- Reports visible text, supported controls, action IDs, and a page fingerprint.
- Clicks, types, selects a native option, scrolls, or waits only through an action ID from the latest observation.
- Refuses stale actions and consumes an observation before browser input, so a failed mutation is never replayed blindly.
- Closes its own tab without closing your other tabs or browser process.

Page text and labels are untrusted website content. The MCP client sees that content to decide what to do. Websites you open may be remote services, even though the browser connection and MCP process run locally.

## Requirements

- Python 3.12 or newer and [uv](https://docs.astral.sh/uv/)
- Brave or Chrome with remote debugging available at `http://127.0.0.1:9222`
- An MCP client such as Codex

Use a browser profile you intend to automate. CDP can interact with pages and sessions in that profile; keep the debugging port bound to loopback and do not expose it to your network.

## Install for Codex

```bash
git clone https://github.com/ZnOw01/JevBrow.git
cd JevBrow
uv sync
python scripts/codex_config.py install
```

The installer adds a marked `jevbrow` block to `~/.codex/config.toml`, using the actual checkout path, and keeps recovery snapshots alongside that file. It leaves unrelated settings in place. Restart Codex so it discovers the new MCP server. If your CDP port differs, change `BU_CDP_URL` in the marked block to your loopback endpoint.

To remove the integration:

```bash
python scripts/codex_config.py uninstall
```

You can also add the MCP server manually:

```toml
[mcp_servers.jevbrow]
command = "uv"
args = ["run", "--directory", "/absolute/path/to/JevBrow", "jevbrow"]
startup_timeout_sec = 30

[mcp_servers.jevbrow.env]
BU_CDP_URL = "http://127.0.0.1:9222"
```

## MCP workflow

1. Call `jevbrow_open(url)` for an `http` or `https` page, or `jevbrow_observe()` for the existing JevBrow tab.
2. Choose an `action_id` from the returned `actions` and pass its `fingerprint` to `jevbrow_click`, `jevbrow_type_text`, `jevbrow_select`, or `jevbrow_scroll_or_wait`.
3. Inspect the observation returned by that tool before another action. After an error or stale fingerprint, observe again.
4. Call `jevbrow_close()` when finished.

The API accepts no model-generated selectors, JavaScript, shell commands, or coordinates. Text entry is limited to an observed editable field and does not submit the form by itself. JevBrow exposes at most 250 page actions per observation and reports how many were omitted.

## Optional standalone mode

The original autonomous runner is separate from MCP. It uses a local OpenAI-compatible model endpoint (for example, CLIPRox) to choose actions and write field values. MCP mode never reads these model credentials.

```bash
cp .env.example .env
# Fill in JEVBROW_MODEL_API_KEY and adjust the local endpoint if needed.
uv run --env-file .env jevbrow-run --url https://example.com --goal 'Describe the page.'
```

For the local inspector, run `uv run --env-file .env jevbrow-demo` and open the loopback URL it prints. `.env`, browser recordings, caches, and local agent settings are ignored by Git.

## Development

```bash
uv sync --group dev
uv run pytest -q
uv run ruff check .
uv run python scripts/check_guards.py
```

The first two checks run offline. `check_guards.py` uses your local CDP browser and a temporary JevBrow-owned tab; it makes no model calls.

## Scope and provenance

This project keeps the original `jev_ultrafast` Python package name. It derives from the MIT-licensed [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast) prototype; the original copyright notice is preserved in [LICENSE](LICENSE). The MCP integration and local Codex setup are the focus of this fork.

JevBrow supports common visible HTML and ARIA controls. Shadow roots, frames, canvas controls, uploads, pop-ups, nested scrolling, and complex keyboard widgets can block progress. A visible action can still be the wrong action for a task. The older [performance reports](docs/performance.md) and [demo](docs/demo.mp4) document the upstream TypeSafe-based prototype; they are historical evidence, not benchmarks of this pre-alpha MCP integration.
