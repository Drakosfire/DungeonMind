# Compact Rust read index experiment

The offline builder exports the existing verified Python indexes to a sorted
byte directory (DMIDX001). Rust opens the immutable bytes and binary-searches
them in place. Python decodes only requested posting lists. The underlying
records, semantic digest, and authorization remain Core's normal work. The
prototype does not change a serving default or add a publication dependency.

The benchmark provisioner supplies the expected manifest independently of the
artifact. It binds space, revision, verified payload SHA-256, format, semantic
digest, and the exact artifact SHA-256. The reader checks the actual bytes
against this manifest. A self-recomputed checksum does not establish trust.
Provisioning a production trust root and artifact lifecycle is outside this
prototype. A builder that signs incorrect postings would still be incorrect.

## Reproduce

Use the existing Core Python environment, Rust 1.97.0, and task-owned scratch
and build directories. Set the shell variables below to absolute paths.

```sh
export PYTHONPATH="$PWD/src:$PWD"
export PYTHONDONTWRITEBYTECODE=1
PYO3_PYTHON="$python" CARGO_TARGET_DIR="$build_dir" cargo build --locked --release \
  --manifest-path benchmarks/compact_read_index/rust/Cargo.toml
extension="$build_dir/release/lib_dm_compact_read_index.so"
"$python" -m benchmarks.compact_read_index.probe build "$extension" \
  "$scratch/fixture.dmidx" "$scratch/fixture-trust.json"
"$python" -m benchmarks.compact_read_index.verify "$extension" \
  "$scratch/fixture.dmidx" "$scratch/fixture-trust.json" --scratch "$scratch"
for _ in $(seq 20); do
  "$python" -m benchmarks.compact_read_index.probe candidate "$extension" \
    "$scratch/fixture.dmidx" "$scratch/fixture-trust.json" || exit
done
```

For Elderwyld append the pinned Buddy checkout to `PYTHONPATH` and set
`DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL` to the isolated snapshot.
The Buddy repository adapter forces read-only transactions. Use the same
`build` and `candidate` commands with a distinct artifact and manifest and
`--elderwyld-capture "$capture_dir"`, where the directory contains the
retained D02 context-ready, context-request, and context-stop JSON. The
historical opening-query parity probe additionally takes
`--historical-revision rev:9eac817676327afaeaaff25d8f38df60` and separate
artifact and manifest paths. It asserts the requested revision differs from the
current head.

Each candidate invocation is one fresh Python process. Build mode evaluates
the Python oracle without timing its query. The candidate timer includes
revision verification, artifact validation, Python/Rust lookup and result
materialization. For Elderwyld it includes the opening query and the retained
selected Graph and citation reads, with no live turn or model activity.

## Evidence and decision

Core base `34032dc83a873b77e07eac0a397b9fe7ae682086`; Elderwyld host
`c25079c48e42360c5a0e3e060c43b8bf0a0cd019`; format `DMIDX001`.

| Input | Revision | Verified payload SHA-256 |
| --- | --- | --- |
| 10k neighborhood | `rev:bench-10000` | `533ae4f09b2273a913734e5d3088d32614b55fcf25c9d27bcff1d749fd13da00` |
| Elderwyld D02 | `rev:5293c1b237a0064bd16fffd080bfa6b1` | `d82906eb8a7590a62700ae08ee2d3b0b202275de6984358dbdcdb3ca85ae71cd` |
| Elderwyld parent | `rev:9eac817676327afaeaaff25d8f38df60` | `2a8ceff955b6f7b6d0623a787d81c2cc85baa780f646ec1ef60dff4e9baa9c24` |

| Input | n | Revision open p50 / p95 | Authorized reads p50 / p95 | Authorized reads min–max |
| --- | ---: | ---: | ---: | ---: |
| 10k neighborhood | 20 | 269 / 303 ms | 270 / 304 ms | 260–309 ms |
| Elderwyld D02 | 20 | 448 / 512 ms | 1,926 / 2,230 ms | 1,800–2,453 ms |

The 10k fixture matched all ordered postings and the authorized result with
scope exclusion, source visibility restriction, and a subsequent withdrawal.
Elderwyld matched the captured opening query, three selected Graph reads and
17 exact citation reads. The historical opening query matched the untimed
Python oracle. The verified source reader still owns live citation authority.

| Input | Artifact bytes | Offline encoding | Build retained / peak RSS | Candidate retained / peak RSS |
| --- | ---: | ---: | ---: | ---: |
| 10k neighborhood | 7,678,601 | 383 ms | 215 / 225 MiB | 203 / 203 MiB |
| Elderwyld D02 | 15,798,777 | 234 ms | 430 / 430 MiB | 414 / 414 MiB |

Memory is a single Linux process spot check using VmRSS and VmHWM, including
fixture or capture setup and imports. Offline encoding excludes the untimed
verified Python index build that supplies the postings, so the table does not
estimate publication cost. The retained 10k benchmark times the neighborhood
after opening its context, and the retained Elderwyld route uses other timing
boundaries. Neither is a matched control for these candidate timings.

**Decision:** leave this as an opt-in experiment. It demonstrably skips
in-worker derived index construction, but exact revision verification and
record parsing still happen on every cold open, the artifact adds 8–16 MB,
and the current evidence does not establish a route-level speedup. Require a
matched comparison and publication, trust, and memory evidence before any
production adoption. No baseline or ingestion rerun was performed.
