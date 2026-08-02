"""Optional D&D 5e semantic profile package.

Profile-owned, side-effect-free executable contracts and pure deterministic
application logic: immutable profile descriptors (``profiles/``), an exact
Threat vocabulary catalog (``vocabularies/``), strict provenance-bearing
candidate contracts (``contracts/``), non-mutating create-or-connect
contribution planning contracts, and pure loaders/renderers/validators/
planners (``application/``). The planner is graph-aware only through passed
values — one exact stored revision and a configured snapshot reader — and
remains repository-blind; it never appends, decides, or publishes. Importing
this package registers nothing and reads no package data; resource reads
happen only inside loader functions. The DungeonMind kernel never imports
this package, and this package imports only narrow kernel contract/canonical/
graph-snapshot modules — never kernel repositories, infrastructure, service,
or agent layers.
"""
