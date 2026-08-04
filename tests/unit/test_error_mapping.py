"""HTTP error envelopes must not leak persistence internals."""

from dungeonmind.domain.errors import (
    CapabilityDeniedError,
    IdempotencyConflictError,
    PersistenceIntegrityError,
    PersistenceUnavailableError,
    RevisionNotFoundError,
)
from dungeonmind.service.error_mapping import error_envelope, http_status_for


def test_persistence_errors_use_fixed_public_messages() -> None:
    leak = (
        'connection to host "db.internal" port 5432 failed: password=super-secret '
        'DETAIL: Key (thread_id)=(thr:x) already exists in table "mind_threads". '
        "SQL: SELECT * FROM dungeonmind.mind_threads"
    )
    unavailable = PersistenceUnavailableError(leak, details={"reason": "connect", "dsn": leak})
    integrity = PersistenceIntegrityError(leak, details={"reason": "constraint", "sql": leak})

    u_env = error_envelope(unavailable)
    i_env = error_envelope(integrity)

    assert http_status_for(unavailable) == 503
    assert http_status_for(integrity) == 500
    assert u_env["error"]["message"] == "Persistence backend is temporarily unavailable."
    assert i_env["error"]["message"] == "Stored data failed an integrity check."
    assert u_env["error"]["details"] == {"reason": "connect"}
    assert i_env["error"]["details"] == {"reason": "constraint"}

    for envelope in (u_env, i_env):
        rendered = str(envelope)
        assert "super-secret" not in rendered
        assert "db.internal" not in rendered
        assert "mind_threads" not in rendered
        assert "SELECT *" not in rendered
        assert "password=" not in rendered


def test_existing_mind_turn_error_wording_is_not_publication_specific() -> None:
    errors = (
        CapabilityDeniedError("mind-turn capability mismatch"),
        RevisionNotFoundError("mind-turn revision missing"),
        IdempotencyConflictError("mind-turn request conflict"),
    )
    assert [
        error_envelope(error)["error"]["message"] for error in errors
    ] == [
        "mind-turn capability mismatch",
        "mind-turn revision missing",
        "mind-turn request conflict",
    ]
