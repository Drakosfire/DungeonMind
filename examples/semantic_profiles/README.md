# Semantic profile registry example

This directory is a **local composition example**, not production deployment
guidance.

## Locator versus identity

`descriptor_path` in `registry.json` is a **locator** used only at load time.
Paths resolve relative to the config file (parent segments such as `../` are
allowed). Graph identity is never a path. Durable identity is the pinned
`SemanticProfileRef`:

- `profile_id`
- `profile_revision`
- `descriptor_sha256`

Relocating an identical descriptor file and updating the config path does not
change graph identity. Changing descriptor bytes changes the digest and
requires a new immutable profile revision pin.

## Compute a descriptor digest

```bash
uv run python - <<'PY'
from pathlib import Path
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.application.semantic_profiles import descriptor_sha256

raw = Path("src/dungeonmind_dnd/profiles/dnd5e-v1.json").read_text(encoding="utf-8")
descriptor = SemanticProfileDescriptor.model_validate_json(raw)
print(descriptor_sha256(descriptor))
PY
```

## Point the host at a registry

```bash
export DUNGEONMIND_SEMANTIC_PROFILE_REGISTRY_PATH=examples/semantic_profiles/registry.json
```

When the env var is absent, the host constructs an empty registry. `dm_union_graph_v1`
and `dm_union_graph_v2` remain usable. A `dm_union_graph_v3` read fails closed —
there is no silent default to `dungeonmind.dnd5e`.

## Why old descriptors must remain available

A published v3 graph revision stores an exact profile ref. Deleting or altering
an old descriptor breaks later reads and retrieval-session reconstruction for
that revision. Keep historical profile revisions loadable for as long as those
graphs must remain readable.

## v1 and v2 coexist (PR B.2c)

This registry lists two revisions of `dungeonmind.dnd5e`:

- **`dnd5e-profile-v1`** — the original namespace-only descriptor. It remains
  valid for graphs pinned to it and is never edited.
- **`dnd5e-profile-v2`** — the profile identity pinned by the D&D Threat
  vocabulary catalog (`dungeonmind.dnd5e.threat` / `threat-v1`).

The registry locates **descriptors only** — it does not locate the vocabulary
catalog. The `dungeonmind_dnd` package loads its own catalog from package data
(`dungeonmind_dnd/vocabularies/threat-v1.json`) and verifies that the
catalog's pinned profile ref matches the bundled v2 descriptor byte-for-byte
by digest. Deleting either descriptor revision breaks old consumers (v3 graph
reads on v1; candidate validation on v2) and is forbidden.
