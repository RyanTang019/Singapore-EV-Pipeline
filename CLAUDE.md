This is a UV managed project. Prefix necessary commands with `uv run`.

If present locally, `docs/PROJECT_CONTEXT.md` (untracked) has full project context — stack, footguns, GCP/Hetzner config, data sources, build order. Read it on demand.

## Retrieving context

- **Design intent / "why"**: read `docs/PROJECT_CONTEXT.md` (and the specs/plans under `docs/superpowers/`) — these are the source of truth for rationale.
- **"What connects to what" / "trace X" / "what depends on Y"**: if `graphify-out/graph.json` exists, answer via `graphify query "<question>"` first instead of reading the whole tree. Treat its output as a map to where to look, not as fact — the graph is a snapshot and can be stale or have unresolved edges.
- **Before editing**: read the actual file. Docs and the graph can lag; source never does.
- The graph excludes `docs/` (gitignored); refreshing it needs a manual copy-and-rebuild, so it won't auto-update on `graphify . --update`.
