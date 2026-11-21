"""Build or measure one fresh-process compact Core read.

Run as python -m benchmarks.compact_read_index.probe. The Python oracle
runs only in build mode; candidate mode never times an oracle read.
"""
import argparse
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
from time import perf_counter

from .artifact import Manifest, build, parse
from .fixture import prepare


def load_extension(path):
    spec = importlib.util.spec_from_file_location("_dm_compact_read_index", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def witness(parsed, result):
    return {
        "semantic_digest": parsed.semantic_digest,
        "result_digest": result.result_digest,
        "entities": [entity.entity_id for entity in result.entities],
        "edges": [
            [edge.assertion_id, edge.subject_entity_id, edge.value.entity_id]
            for edge in result.traversal_assertions
        ],
        "evidence": [evidence.evidence_ref_id for evidence in result.evidence],
    }


def memory():
    fields = dict(
        line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines()
        if line.startswith(("VmRSS:", "VmHWM:"))
    )
    return {
        "process_rss_kib": int(fields["VmRSS"].split()[0]),
        "process_peak_rss_kib": int(fields["VmHWM"].split()[0]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("build", "candidate"))
    parser.add_argument("extension", type=Path)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--elderwyld-capture", type=Path)
    parser.add_argument("--historical-revision")
    args = parser.parse_args()
    extension = load_extension(args.extension)
    if args.elderwyld_capture:
        from .elderwyld import prepare as prepare_elderwyld

        open_revision, query, collect_witness = prepare_elderwyld(
            args.elderwyld_capture, historical_revision=args.historical_revision,
        )
        get_parsed = lambda opened: opened.access.parsed
    else:
        open_revision, query = prepare()
        collect_witness = witness
        get_parsed = lambda opened: opened
    if args.mode == "build":
        opened = open_revision()
        parsed = get_parsed(opened)
        expected_result = collect_witness(opened, query(opened))
        start = perf_counter()
        data, manifest = build(extension, parsed)
        build_ms = (perf_counter() - start) * 1000
        args.artifact.write_bytes(data)
        args.manifest.write_text(json.dumps({
            "manifest": asdict(manifest), "witness": expected_result,
        }))
        print(json.dumps({
            "artifact_build_ms": build_ms, "artifact_bytes": len(data),
            **memory(),
            "manifest": asdict(manifest),
        }))
        return

    trust = json.loads(args.manifest.read_text())
    expected = Manifest(**trust["manifest"])
    start = perf_counter()
    opened = open_revision(lambda stored, rows: parse(
        extension, stored, rows, args.artifact, expected,
    ))
    opened_at = perf_counter()
    result = query(opened)
    elapsed = (perf_counter() - start) * 1000
    if collect_witness(opened, result) != trust["witness"]:
        raise ValueError("authorized neighborhood differs from Python oracle")
    print(json.dumps({
        "first_authorized_query_ms": elapsed,
        "revision_open_ms": (opened_at - start) * 1000,
        **memory(),
    }))


if __name__ == "__main__":
    main()
