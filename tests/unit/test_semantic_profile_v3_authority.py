"""Seal the parallel V3 profile acceptance without changing vNext sequencing."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADR = ROOT / "Docs/Decisions/ADR-0027-vnext-open-predicate-namespaces.md"
STEWARD = ROOT / "Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md"
ROADMAP = ROOT / "Docs/Roadmaps/ROADMAP.md"
V6_HANDOFF = ROOT / "Docs/Handoffs/HANDOFF-v6-k1-complete-entity-authorized-aliases.md"
DISPOSITION = "SEMANTIC_PROFILE_V3_OPEN_PREDICATE_NAMESPACES_ACCEPTED"
REVIEWED_HEAD = "0f709d76fdc53bac9c9258d1751463ae2c76ca71"
MERGE = "a9051f02dfd95e051a83c1d74b26bb04a2b3e5bf"
V6_DISPOSITION = "V6_K1_COMPLETE_ENTITY_AUTHORIZED_ALIASES_ACCEPTED"
V6_REVIEWED_HEAD = "91d2ebaf8aadf512a26ac209cfe8f6414063e732"
V6_MERGE = "f3738f3af3e3c8e204668a3d87d240a32c0d3988"


def test_v3_parallel_authority_is_accepted_and_does_not_claim_transition() -> None:
    adr = ADR.read_text(encoding="utf-8")
    steward = STEWARD.read_text(encoding="utf-8")
    roadmap = ROADMAP.read_text(encoding="utf-8")

    assert f"**Status:** Accepted — `{DISPOSITION}`" in adr
    assert "SEMANTIC_PROFILE_V3_SUBSTANTIVE_PASS" in adr
    for authority in (adr, steward, roadmap):
        assert DISPOSITION in authority
        assert REVIEWED_HEAD in authority
        assert MERGE in authority
    assert "**no** accepted V2→V3 profile-transition" in steward
    assert "cannot transition to V3 under this capability" in roadmap
    assert "**DungeonMindBuddy V6.2 — complete-object read adaptation" in steward
    assert "next active consumer step is DungeonMindBuddy V6.2" in roadmap


def test_v6_k1_is_complete_without_changing_v3_parallel_boundary() -> None:
    handoff = V6_HANDOFF.read_text(encoding="utf-8")
    steward = STEWARD.read_text(encoding="utf-8")
    roadmap = ROADMAP.read_text(encoding="utf-8")

    assert f"**Status:** COMPLETE — `{V6_DISPOSITION}`" in handoff
    assert "PASS review `5321738653`" in handoff
    for authority in (handoff, steward, roadmap):
        assert V6_DISPOSITION in authority
        assert V6_REVIEWED_HEAD in authority
        assert V6_MERGE in authority
    assert "V6.K1 COMPLETE" in steward
    assert "PARALLEL SEMANTIC-PROFILE V3" in steward
    assert "V2→V3 profile transition" in steward
