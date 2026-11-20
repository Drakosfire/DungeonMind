import subprocess
import sys
from pathlib import Path

from scripts.generate_vnext_contract_bundle import make_bundle

from dungeonmind.contracts import vnext


def test_checked_in_vnext_bundle_is_reproducible() -> None:
    root = Path(__file__).parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "scripts/generate_vnext_contract_bundle.py",
            "--check",
            "Docs/Contracts/vnext/dm_vnext_contract_v1.json",
        ],
        cwd=root,
        check=False,
    )
    assert result.returncode == 0


def test_bundle_inventory_matches_public_contract_models() -> None:
    bundle = make_bundle()
    bundle_names = {item["public_name"] for item in bundle["contracts"]}
    model_names = {model.__name__ for model in vnext.PUBLIC_CONTRACT_MODELS}
    assert bundle_names == model_names
    assert model_names <= set(vnext.__all__)
    assert "semantic_invariants" in bundle
    assert bundle["semantic_invariants"]["invariant_count"] == len(
        bundle["semantic_invariants"]["invariants"]
    )


def test_source_publication_contracts_are_additive_outside_frozen_inventory():
    assert tuple(m.__name__ for m in vnext.PUBLIC_CONTRACT_MODELS) == (
        "Assertion",
        "ContributionDisposition",
        "DomainContractDescriptor",
        "DomainContractRef",
        "Entity",
        "EvidenceRefV3",
        "IdentityAlias",
        "IdentityDecisionV3",
        "KnowledgeContribution",
        "KnowledgeHead",
        "KnowledgeRevision",
        "ProjectionRequest",
        "ProjectionSnapshot",
        "PublishKnowledgeRevisionCommand",
        "SemanticProfileDescriptorV2",
        "SourceArtifactV3",
        "SourceRevisionV2",
    )
    assert vnext.GovernedNativeSourcePublicationV1 not in vnext.PUBLIC_CONTRACT_MODELS
    assert vnext.GovernedNativeSourcePublicationReceiptV1 not in vnext.PUBLIC_CONTRACT_MODELS
