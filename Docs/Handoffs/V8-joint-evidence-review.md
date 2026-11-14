# Elderwyld V8 joint evidence review

Disposition: pending joint acceptance. Scope follows Core #174, the fresh-native Elderwyld cohort. The legacy bridge is outside that scope.

## Tested pins

Buddy `e7e892808dbfbb39016f59aba42becfb6be39655` with installed Core `45d04fb6691cb084b1d50feb1ddb7ab18f15a95d`. The serving deployment and its authority are tracked in the [V8 checkpoint](HANDOFF-v8-joint-acceptance-checkpoint.md).

## Evidence

- The candidate passed 52 focused Buddy preservation tests.
- Paired isolated PostgreSQL projection matched membership across 50,003 nodes, directed edge, display fields, and mapped source and evidence attribution. Two samples per path yielded medians of 5.71 s classic and 4.06 s native.
- The paired 10k HTTP governed write created two locations and one directed relationship in each arm. Each replay returned the same committed revision. The citation excerpt matched byte for byte. Prepare and confirm took 677 ms and 3,632 ms classic versus 191 ms and 706 ms native in single isolated samples.
- Native 50k synthetic diagnostics passed structural checks for entity reads, neighborhood, search, evidence, anchors, and publication. These isolate Core work in memory. The separate 50k World-like and Rules-like diagnostic measured classic APIs.

## Cold neighborhood disposition for review

On the paired 10k fixture, the first native request took 2.12 s versus 0.54 s classic, with exact citation parity. Repeat native requests took 378–387 ms versus 522–541 ms classic. Earlier profiling places the cold cost in revision reconstruction and context preparation before traversal.

The proposal is to carry the cold cost explicitly for scoped Elderwyld, capture deployed cold and repeat timings at V11, and prioritize reducing whole-revision preparation in the post-vNext performance program. Restarts, eviction, and new pinned revisions can expose the first-request cost again.

The [versioned evidence artifact](dm_vnext_contract_acceptance_v1.json) records candidate-pin outputs for Buddy preservation, organizational memory, and adversarial identity. Joint acceptance still requires a decision on the measured cold neighborhood cost. V9 follows joint acceptance and requires the deployment rollback rehearsal.

## Later Buddy route evidence

Buddy `952f4117cd90e575cf17e12840ebc33687fbdf22` pins the same Core
`45d04fb6691cb084b1d50feb1ddb7ab18f15a95d`. This candidate adds the recap
and complete-object cache changes from Buddy #3527 and #3533. The versioned
fixture acceptance artifact above retains its own original tested pins.

- On the isolated Elderwyld restore, authenticated recap discovery and paging
  reopened the same 112 admitted bytes at the native head and its parent.
  The shared search anchor reopened 1532 bytes matching the stored Core
  extension proof. The candidate refused anonymous recap discovery and
  stale binding requests.
- The complete-object cache reuses immutable parsed revisions and opens a
  fresh source authority view. Its withdrawal regression returned 409 with
  no source bindings at the unchanged graph revision. On the paired 10k
  fixture, native repeated reads fell from 1862–2118 ms to 363–374 ms.
  The first cached-build read took 1873 ms. The selected object shape and
  normalized excerpt matched, with different assertion payload counts.
- On the isolated Elderwyld API after restart, complete-object returned
  the same digest in 1824, 348 and 342 ms. Exact-object and node-evidence
  repeated reads took 325–334 ms and 311–313 ms respectively. Mounted
  search took 1766, 450 and 448 ms with identical response digests.
- The paired 10k node-evidence fixture returned mapped anchors and reopened
  exact matching bytes at 547–562 ms classic and 347–356 ms native. Capped
  search returned stable results within each arm, kept its seed first,
  disclosed bounded coverage and reopened matching citation bytes. Its
  secondary matches and coverage labels differed. The 987–1020 ms classic
  and 458–631 ms native values are diagnostic timings for different outputs.

The authenticated browser loaded the native Graph on the isolated candidate.
A persisted Plan turn stopped before provider dispatch. Nine provider-free
PostgreSQL broker tests cover Plan subject-search selection and single use.
The completed Plan browser citation, the broader scale acceptance and the
cold-cost disposition remain open. The classic search dispatch was rehearsed
on the isolated snapshot without moving either head. Deployment rollback
still requires a process-level rehearsal. No serving switch occurred.
