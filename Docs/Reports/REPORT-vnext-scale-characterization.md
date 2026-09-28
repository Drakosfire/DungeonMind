# vNext scale characterization — partial memory baseline through 10k

Main anchor: `ccd06cb119c834a3d7950d5109b85c7b6a683430`

Measured runtime anchor: `7c69e447f6d4acc963ac09c6fb9cb48cc1c5b9cc`

Measurement checkout: `ccd06cb119c834a3d7950d5109b85c7b6a683430`

This report records synthetic World-like and Rules-like stress shapes. Eleven measured operations use the classic V6 World Graph projection/retrieval API family; only tiny-delta publication uses native vNext. The classic timings are not claims about native-vNext entity/evidence/search performance. Rules-like is a workload shape only; it does not assert Rules domain semantics. No production/user data, PostgreSQL target, provider, or external service was used.

Environment: Linux-7.0.0-34-generic-x86_64-with-glibc2.39, x86_64, CPython 3.13.1, 8 logical CPUs.

The activation is sequential and bounded to 90 minutes and 8 GiB peak RSS. A virtual-address-space ulimit is recorded separately and is not misrepresented as an RSS limit. Timing and tracemalloc peaks are machine-dependent observations; digests/counts are deterministic identity. No aggregate score or universal latency threshold is claimed.

## Measurement matrix

| Shape | Size | Operation | API family | Adapter | Disposition | Median seconds | Peak traced bytes | Result digest | Reason |
|---|---:|---|---|---|---|---:|---:|---|---|
| world_like | 100 | cold_parse | memory | classic_v6_world_graph | measured | 0.0202898 | 2669196 | `4a10b6972d1d…` |  |
| world_like | 100 | full_projection | memory | classic_v6_world_graph | measured | 0.120479 | 4684405 | `4ebdd78c45c0…` |  |
| world_like | 100 | exact_entity | memory | classic_v6_world_graph | measured | 0.129919 | 4684901 | `9c6bc36d4a97…` |  |
| world_like | 100 | complete_entity | memory | classic_v6_world_graph | measured | 0.126942 | 4684717 | `12e914daa54f…` |  |
| world_like | 100 | neighborhood_d1 | memory | classic_v6_world_graph | measured | 0.312688 | 4685005 | `5bdf0611cc2d…` |  |
| world_like | 100 | neighborhood_d2 | memory | classic_v6_world_graph | measured | 0.159723 | 4684957 | `eb37e4f17ac8…` |  |
| world_like | 100 | evidence | memory | classic_v6_world_graph | measured | 0.119858 | 4684941 | `44f94f8cefd7…` |  |
| world_like | 100 | source_anchor | memory | classic_v6_world_graph | measured | 0.140347 | 4912199 | `60de132aa898…` |  |
| world_like | 100 | deterministic_search | memory | classic_v6_world_graph | measured | 0.150333 | 4684741 | `74871300a3d3…` |  |
| world_like | 100 | source_snapshot | memory | classic_v6_world_graph | measured | 0.00149067 | 31619 | `b5eef6a1ca7b…` |  |
| world_like | 100 | tiny_delta_publication | memory | native_vnext | measured | 0.0143098 | 315927 | `2834bec7d28d…` |  |
| world_like | 100 | canonical_serialize_hash | memory | classic_v6_world_graph | measured | 0.0356864 | 1471036 | `04054efa63b4…` |  |
| world_like | 1000 | cold_parse | memory | classic_v6_world_graph | measured | 0.292417 | 26859440 | `5d8e37a7a266…` |  |
| world_like | 1000 | full_projection | memory | classic_v6_world_graph | measured | 1.36177 | 46183133 | `13aa54ed0935…` |  |
| world_like | 1000 | exact_entity | memory | classic_v6_world_graph | measured | 1.31258 | 46183725 | `ed0f8bcf9bec…` |  |
| world_like | 1000 | complete_entity | memory | classic_v6_world_graph | measured | 1.20148 | 46183725 | `ea0537dc888e…` |  |
| world_like | 1000 | neighborhood_d1 | memory | classic_v6_world_graph | measured | 1.24701 | 46184077 | `3c199fe43ea7…` |  |
| world_like | 1000 | neighborhood_d2 | memory | classic_v6_world_graph | measured | 1.23797 | 46184077 | `5f8973aa57d0…` |  |
| world_like | 1000 | evidence | memory | classic_v6_world_graph | measured | 0.9125 | 46184013 | `2d1ac385402c…` |  |
| world_like | 1000 | source_anchor | memory | classic_v6_world_graph | measured | 1.25457 | 48434245 | `28f55a96e245…` |  |
| world_like | 1000 | deterministic_search | memory | classic_v6_world_graph | measured | 1.68067 | 46183861 | `ebda0d296c60…` |  |
| world_like | 1000 | source_snapshot | memory | classic_v6_world_graph | measured | 0.000732208 | 31619 | `b5eef6a1ca7b…` |  |
| world_like | 1000 | tiny_delta_publication | memory | native_vnext | measured | 0.079163 | 2838075 | `7c7ac0aca4ee…` |  |
| world_like | 1000 | canonical_serialize_hash | memory | classic_v6_world_graph | measured | 0.295195 | 14686360 | `8313884343d1…` |  |
| world_like | 10000 | cold_parse | memory | classic_v6_world_graph | measured | 7.14121 | 265823288 | `2823d186e30a…` |  |
| world_like | 10000 | full_projection | memory | classic_v6_world_graph | measured | 18.7654 | 459644221 | `6153a56c21bc…` |  |
| world_like | 10000 | exact_entity | memory | classic_v6_world_graph | measured | 19.9969 | 459644813 | `a150c6a29765…` |  |
| world_like | 10000 | complete_entity | memory | classic_v6_world_graph | measured | 17.6086 | 459644813 | `e9eae4f1e85d…` |  |
| world_like | 10000 | neighborhood_d1 | memory | classic_v6_world_graph | measured | 16.9099 | 459645165 | `22080c4b9d22…` |  |
| world_like | 10000 | neighborhood_d2 | memory | classic_v6_world_graph | measured | 17.1633 | 459645165 | `7e2629b050f9…` |  |
| world_like | 10000 | evidence | memory | classic_v6_world_graph | measured | 16.386 | 459645077 | `b462fe4e1bb0…` |  |
| world_like | 10000 | source_anchor | memory | classic_v6_world_graph | measured | 19.156 | 485791249 | `23fe769471d6…` |  |
| world_like | 10000 | deterministic_search | memory | classic_v6_world_graph | measured | 25.0263 | 459644949 | `6d5cf188f769…` |  |
| world_like | 10000 | source_snapshot | memory | classic_v6_world_graph | measured | 0.00106483 | 31619 | `b5eef6a1ca7b…` |  |
| world_like | 10000 | tiny_delta_publication | memory | native_vnext | measured | 3.03872 | 27255463 | `83f2389121d6…` |  |
| world_like | 10000 | canonical_serialize_hash | memory | classic_v6_world_graph | measured | 3.49305 | 146837456 | `8207a4e80efd…` |  |
| world_like | 50000 | cold_parse | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 50000 | full_projection | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 50000 | exact_entity | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 50000 | complete_entity | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 50000 | neighborhood_d1 | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 50000 | neighborhood_d2 | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 50000 | evidence | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 50000 | source_anchor | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 50000 | deterministic_search | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 50000 | source_snapshot | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 50000 | tiny_delta_publication | memory | native_vnext | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 50000 | canonical_serialize_hash | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 100000 | cold_parse | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 100000 | full_projection | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 100000 | exact_entity | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 100000 | complete_entity | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 100000 | neighborhood_d1 | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 100000 | neighborhood_d2 | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 100000 | evidence | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 100000 | source_anchor | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 100000 | deterministic_search | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 100000 | source_snapshot | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 100000 | tiny_delta_publication | memory | native_vnext | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 100000 | canonical_serialize_hash | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 100 | cold_parse | memory | classic_v6_world_graph | measured | 0.0251607 | 2671556 | `4e2098bc58c9…` |  |
| rules_like | 100 | full_projection | memory | classic_v6_world_graph | measured | 0.121884 | 4692205 | `d97613d3bc05…` |  |
| rules_like | 100 | exact_entity | memory | classic_v6_world_graph | measured | 0.127651 | 4692797 | `e5fba6a061cf…` |  |
| rules_like | 100 | complete_entity | memory | classic_v6_world_graph | measured | 0.131419 | 4692797 | `539b502c09ce…` |  |
| rules_like | 100 | neighborhood_d1 | memory | classic_v6_world_graph | measured | 0.124881 | 4693149 | `2a6599206820…` |  |
| rules_like | 100 | neighborhood_d2 | memory | classic_v6_world_graph | measured | 0.126456 | 4693149 | `26d8b6639123…` |  |
| rules_like | 100 | evidence | memory | classic_v6_world_graph | measured | 0.119066 | 4693013 | `7d588e285f8c…` |  |
| rules_like | 100 | source_anchor | memory | classic_v6_world_graph | measured | 0.160644 | 4927879 | `f7c17df6f2b9…` |  |
| rules_like | 100 | deterministic_search | memory | classic_v6_world_graph | measured | 0.159454 | 4692933 | `c8c1eb87f7e6…` |  |
| rules_like | 100 | source_snapshot | memory | classic_v6_world_graph | measured | 0.00115241 | 31619 | `b5eef6a1ca7b…` |  |
| rules_like | 100 | tiny_delta_publication | memory | native_vnext | measured | 0.0113621 | 315927 | `0aad2c04f08e…` |  |
| rules_like | 100 | canonical_serialize_hash | memory | classic_v6_world_graph | measured | 0.0347365 | 1475236 | `4b8a9216581a…` |  |
| rules_like | 1000 | cold_parse | memory | classic_v6_world_graph | measured | 0.283067 | 26883440 | `a6eee2754543…` |  |
| rules_like | 1000 | full_projection | memory | classic_v6_world_graph | measured | 1.35413 | 46183133 | `a8c8cfd574ed…` |  |
| rules_like | 1000 | exact_entity | memory | classic_v6_world_graph | measured | 1.54857 | 46183725 | `5b3ede4d8744…` |  |
| rules_like | 1000 | complete_entity | memory | classic_v6_world_graph | measured | 1.39212 | 46183725 | `5503a6cfe1ef…` |  |
| rules_like | 1000 | neighborhood_d1 | memory | classic_v6_world_graph | measured | 1.29428 | 46184077 | `9913bfe7fb70…` |  |
| rules_like | 1000 | neighborhood_d2 | memory | classic_v6_world_graph | measured | 1.24856 | 46184077 | `fb92b21e291b…` |  |
| rules_like | 1000 | evidence | memory | classic_v6_world_graph | measured | 1.41037 | 46183893 | `44b89f4651e1…` |  |
| rules_like | 1000 | source_anchor | memory | classic_v6_world_graph | measured | 1.33994 | 48674861 | `59c6e75d07e6…` |  |
| rules_like | 1000 | deterministic_search | memory | classic_v6_world_graph | measured | 2.07639 | 46183861 | `4d95edaa633e…` |  |
| rules_like | 1000 | source_snapshot | memory | classic_v6_world_graph | measured | 0.00145478 | 31619 | `b5eef6a1ca7b…` |  |
| rules_like | 1000 | tiny_delta_publication | memory | native_vnext | measured | 0.0740233 | 2838075 | `9ffead83ffd5…` |  |
| rules_like | 1000 | canonical_serialize_hash | memory | classic_v6_world_graph | measured | 0.344619 | 14728360 | `a9ed5c8fb5ef…` |  |
| rules_like | 10000 | cold_parse | memory | classic_v6_world_graph | measured | 7.2072 | 266063288 | `7c1dc6daae8a…` |  |
| rules_like | 10000 | full_projection | memory | classic_v6_world_graph | measured | 19.8853 | 460692797 | `612c5a6b7801…` |  |
| rules_like | 10000 | exact_entity | memory | classic_v6_world_graph | measured | 19.4656 | 460693389 | `d70e3cfbcea5…` |  |
| rules_like | 10000 | complete_entity | memory | classic_v6_world_graph | measured | 24.3636 | 460693389 | `97b79fabc325…` |  |
| rules_like | 10000 | neighborhood_d1 | memory | classic_v6_world_graph | measured | 18.4907 | 460693741 | `e90d0f3c1709…` |  |
| rules_like | 10000 | neighborhood_d2 | memory | classic_v6_world_graph | measured | 17.9622 | 460693741 | `1b9e8a42006d…` |  |
| rules_like | 10000 | evidence | memory | classic_v6_world_graph | measured | 16.8519 | 460693533 | `957e703bfe2a…` |  |
| rules_like | 10000 | source_anchor | memory | classic_v6_world_graph | measured | 18.4992 | 489204665 | `47a3720f2481…` |  |
| rules_like | 10000 | deterministic_search | memory | classic_v6_world_graph | measured | 22.9251 | 460693525 | `ccf54bce44b4…` |  |
| rules_like | 10000 | source_snapshot | memory | classic_v6_world_graph | measured | 0.00129513 | 31619 | `b5eef6a1ca7b…` |  |
| rules_like | 10000 | tiny_delta_publication | memory | native_vnext | measured | 2.14225 | 27255463 | `55f17d6dc277…` |  |
| rules_like | 10000 | canonical_serialize_hash | memory | classic_v6_world_graph | measured | 2.85425 | 147257456 | `201fae019b4b…` |  |
| rules_like | 50000 | cold_parse | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 50000 | full_projection | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 50000 | exact_entity | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 50000 | complete_entity | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 50000 | neighborhood_d1 | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 50000 | neighborhood_d2 | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 50000 | evidence | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 50000 | source_anchor | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 50000 | deterministic_search | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 50000 | source_snapshot | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 50000 | tiny_delta_publication | memory | native_vnext | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 50000 | canonical_serialize_hash | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 100000 | cold_parse | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 100000 | full_projection | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 100000 | exact_entity | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 100000 | complete_entity | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 100000 | neighborhood_d1 | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 100000 | neighborhood_d2 | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 100000 | evidence | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 100000 | source_anchor | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 100000 | deterministic_search | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 100000 | source_snapshot | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 100000 | tiny_delta_publication | memory | native_vnext | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| rules_like | 100000 | canonical_serialize_hash | memory | classic_v6_world_graph | not_measured | — | — | — | Not attempted: this host has no enforceable 8 GiB peak-RSS limit; PR #91 activation prohibits 50k/100k until revised activation/waiver. |
| world_like | 100 | cold_parse | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100 | full_projection | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100 | exact_entity | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100 | complete_entity | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100 | neighborhood_d1 | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100 | neighborhood_d2 | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100 | evidence | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100 | source_anchor | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100 | deterministic_search | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100 | source_snapshot | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100 | tiny_delta_publication | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100 | canonical_serialize_hash | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 1000 | cold_parse | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 1000 | full_projection | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 1000 | exact_entity | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 1000 | complete_entity | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 1000 | neighborhood_d1 | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 1000 | neighborhood_d2 | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 1000 | evidence | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 1000 | source_anchor | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 1000 | deterministic_search | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 1000 | source_snapshot | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 1000 | tiny_delta_publication | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 1000 | canonical_serialize_hash | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 10000 | cold_parse | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 10000 | full_projection | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 10000 | exact_entity | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 10000 | complete_entity | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 10000 | neighborhood_d1 | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 10000 | neighborhood_d2 | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 10000 | evidence | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 10000 | source_anchor | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 10000 | deterministic_search | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 10000 | source_snapshot | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 10000 | tiny_delta_publication | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 10000 | canonical_serialize_hash | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 50000 | cold_parse | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 50000 | full_projection | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 50000 | exact_entity | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 50000 | complete_entity | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 50000 | neighborhood_d1 | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 50000 | neighborhood_d2 | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 50000 | evidence | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 50000 | source_anchor | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 50000 | deterministic_search | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 50000 | source_snapshot | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 50000 | tiny_delta_publication | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 50000 | canonical_serialize_hash | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100000 | cold_parse | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100000 | full_projection | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100000 | exact_entity | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100000 | complete_entity | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100000 | neighborhood_d1 | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100000 | neighborhood_d2 | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100000 | evidence | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100000 | source_anchor | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100000 | deterministic_search | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100000 | source_snapshot | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100000 | tiny_delta_publication | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| world_like | 100000 | canonical_serialize_hash | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100 | cold_parse | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100 | full_projection | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100 | exact_entity | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100 | complete_entity | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100 | neighborhood_d1 | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100 | neighborhood_d2 | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100 | evidence | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100 | source_anchor | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100 | deterministic_search | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100 | source_snapshot | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100 | tiny_delta_publication | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100 | canonical_serialize_hash | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 1000 | cold_parse | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 1000 | full_projection | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 1000 | exact_entity | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 1000 | complete_entity | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 1000 | neighborhood_d1 | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 1000 | neighborhood_d2 | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 1000 | evidence | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 1000 | source_anchor | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 1000 | deterministic_search | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 1000 | source_snapshot | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 1000 | tiny_delta_publication | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 1000 | canonical_serialize_hash | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 10000 | cold_parse | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 10000 | full_projection | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 10000 | exact_entity | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 10000 | complete_entity | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 10000 | neighborhood_d1 | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 10000 | neighborhood_d2 | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 10000 | evidence | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 10000 | source_anchor | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 10000 | deterministic_search | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 10000 | source_snapshot | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 10000 | tiny_delta_publication | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 10000 | canonical_serialize_hash | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 50000 | cold_parse | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 50000 | full_projection | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 50000 | exact_entity | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 50000 | complete_entity | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 50000 | neighborhood_d1 | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 50000 | neighborhood_d2 | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 50000 | evidence | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 50000 | source_anchor | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 50000 | deterministic_search | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 50000 | source_snapshot | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 50000 | tiny_delta_publication | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 50000 | canonical_serialize_hash | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100000 | cold_parse | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100000 | full_projection | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100000 | exact_entity | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100000 | complete_entity | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100000 | neighborhood_d1 | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100000 | neighborhood_d2 | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100000 | evidence | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100000 | source_anchor | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100000 | deterministic_search | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100000 | source_snapshot | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100000 | tiny_delta_publication | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |
| rules_like | 100000 | canonical_serialize_hash | postgresql | inactive_postgresql | not_measured | — | — | — | No PostgreSQL target authorized by PR #91 activation. |

## Interpretation and limits

The semantic preflight checks fixture counts and stable IDs directly from the deterministic generator, then hand-authored exact-identity, visibility-exclusion, search, evidence, complete-object, and source-anchor expectations through supported APIs before timing. Repeated semantic digests are an additional determinism check, not the correctness oracle.

PostgreSQL is explicitly inactive under PR #91; every PostgreSQL matrix cell is `not_measured` for lack of an authorized target. Large-scale non-core operations outside the activated cohort are explicitly not measured. `resource_limited` rows name the enforced host limit and observed process high-water RSS where available.

Acceptance state: **PARTIAL_MEMORY_BASELINE_THROUGH_10K_PENDING_PRIME_REVIEW**. PRIME authorized the partial baseline through 10k; 50k/100k attempts are deferred and not accepted. This does not accept the full characterization, V8, or V11.

Regenerate with the command and environment recorded in the JSON artifact. Compare timings only on materially comparable hosts and interpreter builds. This artifact is not V8 acceptance, V11 acceptance, or permission to dispatch a cutover.
