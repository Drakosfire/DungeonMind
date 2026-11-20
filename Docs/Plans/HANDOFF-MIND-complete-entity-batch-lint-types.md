# Complete entity batch lint and optional-counter typing

Status: COMPLETE, CorePR240 accepted/merged.
Owner: MIND; independent Hubble/root review and merge; no deployment authority.
Merge:757cc986a55aaba7013e27724e42ef50f814804c.
Accepted code:36c5f1f0538716413ddd4b90000af0ccf41997b7.
Review:5985957336. CI44650060111 all3terminalSUCCESS.
Base:b6539db99fe5c961123bf7615c9d67cd4e40676b.

## Accepted outcome and invariants

The4-path repair restores static correctness of accepted complete-entity batching:
this handoff, application/vnext/entity_reads.py, read_context.py and owning entity
read test. Private projected provenance callback is typed Sequence[str] ->
KnowledgeProvenanceSnapshot with tuple normalization at immutable builder boundary;
actual tuple callers retain identity/order/duplicates/work. Line wraps preserve
checks. Optional existing snapshot counter is modeled by private Protocol/cast
under the unchanged getattr/non-None guard. No public reader requirement, new
counter/default, runtime isinstance, Any cast, suppression or admission change.
The one wrapped test assertion and other logic are unchanged.

Fresh original audit covered143/145-150/158/239 complete paginated file lists:
no4-path overlap. No process/Steward/roadmap or other PR work absorbed. Current
Core239 adopts accepted main normally; its publication source is not part of240.

## Evidence and accurate limits

Scoped scratch/v10-core/complete-entity-batch-lint-types/final-36c5f1f.json binds
code/test hashes, owning194passed0failure0skip, fullRuffPASS, explicit-interpreter
Pyright0errors0warnings and exact4-path/documented AST normalization proof.
Code/test checks preceded final commit with identical source inputs; no new broad
execution claimed. Hubble independently194passed and accepted bounded source;
CI44650060111 all3success is separate exact-head delivery evidence.

Initial diagnostics retained: literal no-default getattr B009 and Sequence->tuple
builder type errors. Final private type/cast avoids suppression/behavior changes.
Root's original Core239 fullunit3279/1 failure remainedFAILED at240 acceptance;
this static repair did not claim to resolve import-isolation test debt. Separate
Core241 subsequently fixes that test boundary. Do not relabel old failure logs.

## Settled ownership and continuation

Original4-path implementation lease released after merge. Root explicitly
re-authorizes this handoff-only seal during239 integration; no production/test
extension.239 must integrate240/241 and requalify its exact source. Full manual
adoption/UI/current-route retirement/deployment/rollback/V11 remain open.
MIND retains task checkout/cache and scoped diagnostic evidence for active goal.
No newenv/worktree/DB/provider/live/baseline changes or cleanup were performed.
Cleanup follow-up needs scoped approval plus active-process/mount/dirty/unique-data
checks; protect accepted commits and unique evidence before deletion.
