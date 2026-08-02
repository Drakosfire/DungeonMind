"""Optional D&D 5e semantic profile package.

Profile-owned, side-effect-free executable contracts and pure deterministic
application logic: immutable profile descriptors (``profiles/``), an exact
Threat vocabulary catalog (``vocabularies/``), strict provenance-bearing
candidate contracts (``contracts/``), and pure loaders/renderers/validators
(``application/``). Importing this package registers nothing and reads no
package data; resource reads happen only inside loader functions. The
DungeonMind kernel never imports this package, and this package imports only
narrow kernel contract/canonical modules — never kernel application,
infrastructure, service, or agent layers.
"""
