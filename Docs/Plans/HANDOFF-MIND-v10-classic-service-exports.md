# Retire classic graph service facade exports

Serial V10 slice on Core 291918ec47062bab7b270411bb750b1263e336ae.
PR #249 merged exact fea861e3 with all three CI jobs green.
Remove WorldGraphProjectionService and WorldGraphRetrievalService from the
application facade. Keep their leaf implementations for retained work.

The pinned Core, Buddy d73fea69 and WorldKeeper 348c0db audit found no
production facade imports of these names. Move historical test imports to
the explicit leaf. Verify facade absence, cold native isolation, historical
leaf behavior and installed wheel compatibility before merge.
