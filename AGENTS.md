# JevBrow

JevBrow is a local MCP server for Codex and a local CDP browser. Read README.md before editing.

- MCP mode uses Codex's active model for decisions; do not call a second model from MCP tools.
- Browser connections must use the loopback `BU_CDP_URL` configured for the user's Brave Origin/Chrome. Never add cloud browser or cloud-auth flows.
- Only execute actions from the latest observed action list. Never accept model-generated selectors, JavaScript, commands, or coordinates.
- Consume an observation before browser mutation, never retry a mutation, and return a new observation after each action.
- Keep CDP sessions and page data local to the MCP process; close only Jev-owned tabs on shutdown.
- Keep credentials in ignored `.env` files or process environment. Never print secrets. No model/API calls from tests.
- Do not commit or push unless the user requests it.
