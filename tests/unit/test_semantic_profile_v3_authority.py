"""Seal the parallel V3 profile acceptance without changing vNext sequencing."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADR = ROOT / "Docs/Decisions/ADR-0027-vnext-open-predicate-namespaces.md"
STEWARD = ROOT / "Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md"
ROADMAP = ROOT / "Docs/Roadmaps/ROADMAP.md"
DISPOSITION = "SEMANTIC_PROFILE_V3_OPEN_PREDICATE_NAMESPACES_ACCEPTED"
REVIEWED_HEAD = "0f709d76fdc53bac9c9258d1751463ae2c76ca71"
MERGE = "a9051f02dfd95e051a83c1d74b26bb04a2b3e5bf"


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
    assert "**V6.K1 — authorized identity aliases in complete entity reads**" in steward
    assert "V6.K1 → Buddy V6.2" in steward
