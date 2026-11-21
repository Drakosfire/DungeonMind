"""Check artifact refusal paths without re-running the retrieval baseline."""
import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .artifact import FIELDS, Manifest, parse
from .fixture import prepare
from .probe import load_extension, witness


def expect_rejection(operation, error, message):
    try:
        operation()
    except error as exc:
        if message not in str(exc):
            raise
    else:
        raise AssertionError(f"expected rejection: {message}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extension", type=Path)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()
    extension = load_extension(args.extension)
    trusted = Manifest(**json.loads(args.manifest.read_text())["manifest"])
    open_revision, query = prepare()
    original = args.artifact.read_bytes()

    with TemporaryDirectory(prefix="refusal-", dir=args.scratch) as directory:
        test_file = Path(directory) / "candidate.dmidx"

        def load(expected):
            return open_revision(
                lambda stored, rows: parse(extension, stored, rows, test_file, expected)
            )

        expect_rejection(lambda: load(trusted), FileNotFoundError, "candidate.dmidx")
        test_file.write_bytes(original)
        for field, value in (
            ("format", "DMIDX999"), ("space_id", "other-space"),
            ("revision_id", "other-revision"), ("payload_sha256", "0" * 64),
        ):
            expect_rejection(
                lambda: load(replace(trusted, **{field: value})),
                ValueError, "revision binding mismatch",
            )

        test_file.write_bytes(original[:-1])
        expect_rejection(lambda: load(trusted), ValueError, "trusted artifact digest")
        expect_rejection(
            lambda: load(replace(trusted, index_sha256=sha256(original[:-1]).hexdigest())),
            ValueError, "invalid compact read index",
        )

        test_file.write_bytes(original)
        python, rust = open_revision(), load(trusted)
        for field in FIELDS:
            expected_index = getattr(python, field)
            actual_index = getattr(rust, field)
            assert tuple(expected_index) == tuple(actual_index), field
            assert all(expected_index[key] == actual_index[key] for key in expected_index), field

        before = witness(python, query(python))
        assert before == witness(rust, query(rust))
        scoped = witness(python, query(python, out_of_scope=True))
        assert scoped == witness(rust, query(rust, out_of_scope=True))
        assert before["edges"] and not scoped["edges"]
        hidden = witness(python, query(python, hide_source=True))
        assert hidden == witness(rust, query(rust, hide_source=True))
        assert before["evidence"] and not hidden["evidence"]
        expected_after = witness(python, query(python, withdraw=True))
        assert expected_after == witness(rust, query(rust))
        assert before["evidence"] and not expected_after["evidence"]

        # Keep the directory valid and change an actual posting's JSON bytes.
        marker = b'["ent:'
        offset = original.index(marker) + len(marker)
        changed = original[:offset] + b"!" + original[offset + 1:]
        assert len(extension.Index(changed)) == len(extension.Index(original))
        forged_checksum = sha256(changed).hexdigest()
        assert forged_checksum != trusted.index_sha256
        test_file.write_bytes(changed)
        # The recomputed checksum is supplied by an untrusted artifact producer.
        # Only the separately provisioned builder digest is consulted by parse.
        expect_rejection(lambda: load(trusted), ValueError, "trusted artifact digest")

    print("missing, mismatched, malformed and rechecksummed artifact refusal and ordered indexes, scope, visibility and withdrawal parity passed")


if __name__ == "__main__":
    main()
