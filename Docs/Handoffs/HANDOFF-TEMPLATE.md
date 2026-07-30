# HANDOFF — <slice name>

**Created:** <date>
**Status:** <ACTIVE | SUPERSEDED | LANDED>
**Repository / branch:** <repo> / <branch>
**Predecessor:** <link or "none">
**One-line mission:** <what this slice delivers and why it is independently useful>

---

## §1 Outcome

<The single observable end state. One paragraph.>

## §2 Authority and anchors

<Ordered list of checked-in sources the agent must read first. Never chat
history. Include ADRs and authority map entries that bind this slice.>

## §3 Scope

**In scope:** <bulleted, concrete>
**Out of scope (falsification):** <what this slice must NOT attempt — derived
from the founding charter §14 non-goals and §15 stop conditions>

## §4 Invariants that bind this slice

<Copy the specific invariants from Docs/Architecture/ARCHITECTURE.md §2–3
that constrain the work, plus any slice-local ones.>

## §5 Work plan

<Numbered steps, each independently verifiable. Name the tests/gates that
prove each step.>

## §6 Acceptance gates

<Exact commands and expected results. Include lint, unit tests, and any
integration/smoke gates from the founding charter §13 relevant to this slice.>

## §7 Stop conditions

<When to halt and report instead of proceeding. Always include the charter
§15 conditions that apply; add slice-specific ones.>

## §8 Handback requirements

- Repositories and revisions (repo / branch / base SHA / head SHA / PR / status)
- Decisions (question / evidence / decision / rejected alternatives /
  consequences / reversal path)
- Verification (exact commands + results)
- What remains false (explicit list — never imply more than landed)
- Named next slices (independently useful successors, not a general backlog)
