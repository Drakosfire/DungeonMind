"""Shared repository contract cases against PostgreSQL adapters.

Bounded discovery split from the per-boundary integration modules: these cases
prove port-level parity with memory without enlarging graph/records/semantic
files. Guarantees moved here: exact replay, conflicts, ordering, thread binding,
embedding lifecycle, batch atomicity, active-run search, scope/visibility, and
graph CAS genesis/stale-parent — all via ``tests/conformance`` cases.
"""

from __future__ import annotations

import pytest

from tests.conformance.repository_contract_cases import CASES


@pytest.mark.integration
@pytest.mark.conformance
@pytest.mark.parametrize("case_name,case_fn", CASES, ids=[n for n, _ in CASES])
def test_postgres_conformance(case_name: str, case_fn, repository_bundle) -> None:
    del case_name
    case_fn(repository_bundle)
