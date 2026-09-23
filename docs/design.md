# JevBrow design

JevBrow has two decision modes that share one local browser executor.

## MCP mode

Codex chooses the next action using the model already active in the MCP client. The stdio server holds the browser connection and tab state in its own process. It observes visible text and supported controls, then returns action IDs and a fingerprint. A mutation tool accepts only an ID from that observation and its fingerprint; it never accepts a generated selector, script, coordinate, or shell command.

Before dispatch, the server checks page freshness and action kind. It consumes the observation before browser input. If CDP reports a timeout after dispatch, the caller must observe again; JevBrow does not replay the mutation. A successful action returns a new observation. Only the tab created by JevBrow is closed on shutdown.

## Standalone mode

The optional autonomous runner sends a goal, visible page context, and offered action IDs to a local OpenAI-compatible endpoint. Its JSON response must choose one offered ID. A separate local model call writes text for an observed editable field. This mode needs `JEVBROW_MODEL_*` settings; MCP mode does not.

## Observation and guards

A single browser-side DOM snapshot reads common HTML and ARIA controls, labels, current values, and visible text. A WeakMap assigns code-owned identities to DOM nodes; a Map retains live references for execution. Navigation creates a new cache. At most 250 actions are returned per observation, and the result reports how many candidates were omitted.

Freshness guards compare the document and meaningful state. For a click or native select, they also check the selected target and nearby form, dialog, or row context. The executor resolves current geometry immediately before input and rejects hidden, disabled, readonly, or covered targets. An interrupted select stops because its change event may already have fired.

The reader is intentionally narrower than a full browser accessibility tree. Shadow roots, frames, canvas, uploads, pop-ups, nested scrolling, and complex keyboard widgets are outside the current implementation. The [historical performance report](performance.md) describes measurements from the upstream TypeSafe prototype; it does not measure this MCP release.
