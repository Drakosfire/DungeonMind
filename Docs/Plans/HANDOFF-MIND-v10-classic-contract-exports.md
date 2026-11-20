# Retire classic graph contract facade exports

Serial V10 slice on Core e56a3faee749ced9ac0913da5d7282da84b7cc2d.
Remove WorldGraphRevision, WorldGraphHead, WorldGraphProjectionRequestV2 and
ScopeModeV2 from the contracts facade. Keep historical leaf models unchanged.
No production facade consumer was found in the pinned Core, Buddy d73fea69
or WorldKeeper 348c0db trees. Core round-trip tests import the leaf types.

Verify facade absence, explicit leaf imports, round-trip parity and native
cold-import isolation. Verify the package build and independently review the
exact source before merging. Classic service and write-contract dispositions
are separate slices. Adopt any new Core pin only after Buddy qualification.
