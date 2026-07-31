"""Deterministic grounded fixture agent — no network, no model, no repositories."""

from __future__ import annotations

import json
from typing import Any

from ..contracts.evidence import EvidenceRole
from ..contracts.retrieval import (
    Claim,
    ClaimAuthority,
    ClaimStatus,
    DiagnosticEntry,
)
from .protocol import AgentAdapter, AgentTurnContext, AgentTurnResult

FIXTURE_AGENT_ADAPTER_ID = "fixture-grounded-agent-v1"


class FixtureGroundedAgentAdapter:
    """Answers only from assembled fixture context JSON."""

    @property
    def adapter_id(self) -> str:
        return FIXTURE_AGENT_ADAPTER_ID

    def execute_turn(self, context: AgentTurnContext) -> AgentTurnResult:
        try:
            payload = json.loads(context.input.assembled_context)
        except json.JSONDecodeError:
            return AgentTurnResult(
                answer=(
                    "I cannot answer from the available context; "
                    "the assembled context was not valid JSON."
                ),
                claims=[],
                diagnostics=[
                    DiagnosticEntry(
                        code="fixture_agent_invalid_context",
                        severity="error",
                        message="assembled_context was not valid JSON",
                    )
                ],
            )

        objects = list(payload.get("objects") or [])
        relationships = list(payload.get("relationships") or [])
        evidence = list(payload.get("evidence") or [])
        coverage = payload.get("coverage") or {}
        message = context.input.message

        support_ids = {
            str(item.get("evidence_ref_id"))
            for item in evidence
            if str(item.get("evidence_role", "")).lower()
            in {EvidenceRole.SUPPORT.value, "support"}
        }

        diagnostics = [
            DiagnosticEntry(
                code="fixture_only_agent",
                severity="info",
                message="Deterministic fixture-grounded agent; not a model provider.",
                data={"adapter_id": self.adapter_id},
            )
        ]

        missing = list(coverage.get("missing") or [])
        gap_codes = list(coverage.get("gap_codes") or [])

        def _abstain() -> AgentTurnResult:
            return AgentTurnResult(
                answer=(
                    "I do not have grounded knowledge for that question "
                    "in the admitted graph context."
                ),
                claims=[],
                diagnostics=[
                    *diagnostics,
                    DiagnosticEntry(
                        code="fixture_agent_abstain",
                        severity="info",
                        message="Insufficient admitted context; abstaining.",
                        data={"missing": missing, "gap_codes": gap_codes},
                    ),
                ],
            )

        # Curated miss: never invent unmentioned entities from noisy retrieval.
        if "Moon King" in message:
            return _abstain()

        if not objects and not relationships:
            return _abstain()

        answer, claims = _answer_from_context(
            message=message,
            objects=objects,
            relationships=relationships,
            support_ids=support_ids,
        )
        return AgentTurnResult(answer=answer, claims=claims, diagnostics=diagnostics)


def _object_by_id(objects: list[dict[str, Any]], object_id: str) -> dict[str, Any] | None:
    for obj in objects:
        if obj.get("object_id") == object_id:
            return obj
    return None


def _label(objects: list[dict[str, Any]], object_id: str) -> str:
    obj = _object_by_id(objects, object_id)
    if obj is None:
        return object_id
    return str(obj.get("label") or object_id)


def _support_for(entity: dict[str, Any], support_ids: set[str]) -> list[str]:
    return [
        eid
        for eid in list(entity.get("evidence_ref_ids") or [])
        if eid in support_ids
    ]


def _claim(
    *,
    claim_id: str,
    text: str,
    evidence_ref_ids: list[str],
) -> Claim:
    if evidence_ref_ids:
        return Claim(
            claim_id=claim_id,
            text=text,
            authority=ClaimAuthority.GRAPH_FACT,
            status=ClaimStatus.ACCEPTED,
            evidence_ref_ids=evidence_ref_ids,
        )
    return Claim(
        claim_id=claim_id,
        text=text,
        authority=ClaimAuthority.INFERENCE,
        status=ClaimStatus.ACCEPTED,
        evidence_ref_ids=[],
    )


def object_id_fallback(obj: dict[str, Any]) -> str:
    return str(obj.get("object_id") or "unknown")


def _answer_from_context(
    *,
    message: str,
    objects: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    support_ids: set[str],
) -> tuple[str, list[Claim]]:
    folded = message.casefold()
    claims: list[Claim] = []

    safeguards = [
        rel
        for rel in relationships
        if str(rel.get("predicate")) == "safeguards"
    ]
    resides = [
        rel
        for rel in relationships
        if str(rel.get("predicate")) == "resides_in"
    ]

    if "safeguard" in folded and safeguards:
        rel = safeguards[0]
        subject = _label(objects, str(rel["subject_object_id"]))
        obj = _label(objects, str(rel["object_object_id"]))
        evidence_ids = _support_for(rel, support_ids)
        text = f"{subject} safeguards {obj}."
        claims.append(
            _claim(
                claim_id="claim:fixture-safeguards",
                text=text,
                evidence_ref_ids=evidence_ids,
            )
        )
        return text, claims

    if ("where" in folded or "live" in folded or "reside" in folded) and resides:
        rel = resides[0]
        subject = _label(objects, str(rel["subject_object_id"]))
        obj = _label(objects, str(rel["object_object_id"]))
        evidence_ids = _support_for(rel, support_ids)
        text = f"{subject} resides_in {obj}."
        claims.append(
            _claim(
                claim_id="claim:fixture-resides",
                text=text,
                evidence_ref_ids=evidence_ids,
            )
        )
        return text, claims

    if "connected" in folded and resides:
        rel = resides[0]
        subject = _label(objects, str(rel["subject_object_id"]))
        obj = _label(objects, str(rel["object_object_id"]))
        evidence_ids = _support_for(rel, support_ids)
        text = f"{subject} is connected to {obj} via resides_in."
        claims.append(
            _claim(
                claim_id="claim:fixture-connected",
                text=text,
                evidence_ref_ids=evidence_ids,
            )
        )
        return text, claims

    ledger = next(
        (
            obj
            for obj in objects
            if obj.get("object_id") == "obj:item-sun-ledger"
            or "sun ledger" in str(obj.get("label", "")).casefold()
        ),
        None,
    )
    if ledger is not None and "what" in folded and "ledger" in folded:
        label = str(ledger.get("label") or object_id_fallback(ledger))
        kind = str(ledger.get("kind") or "artifact")
        summary = ledger.get("summary")
        evidence_ids = _support_for(ledger, support_ids)
        if isinstance(summary, str) and summary.strip():
            text = f"{label}: {summary.strip()}"
        else:
            article = "an" if kind[:1].casefold() in {"a", "e", "i", "o", "u"} else "a"
            text = f"{label} is {article} {kind}."
        claims.append(
            _claim(
                claim_id="claim:fixture-ledger",
                text=text,
                evidence_ref_ids=evidence_ids,
            )
        )
        return text, claims

    if objects:
        labels = ", ".join(str(obj.get("label")) for obj in objects[:3])
        text = f"Relevant admitted entities: {labels}."
        claims.append(
            Claim(
                claim_id="claim:fixture-inspection",
                text=text,
                authority=ClaimAuthority.INFERENCE,
                status=ClaimStatus.ACCEPTED,
            )
        )
        return text, claims

    return (
        "I do not have grounded knowledge for that question "
        "in the admitted graph context.",
        [],
    )


# Protocol structural satisfaction for type checkers.
_: type[AgentAdapter] = FixtureGroundedAgentAdapter
