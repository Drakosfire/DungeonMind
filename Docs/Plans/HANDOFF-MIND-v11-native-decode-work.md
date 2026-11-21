# Reduce native artifact decode work

Independent of PR #249 at Core e56a3faee749ced9ac0913da5d7282da84b7cc2d.
The isolated Elderwyld profile found artifact expansion and parsed index
construction dominating the cold path. The combined scratch prototype took
8–53 ms less on six paired decodes with equal parsed results.

Keep the artifact format, full reconstructed-source proof, JSON validation,
depth limits, and all index ordering and integrity rules. Optimize string
skipping in the depth precheck and avoid redundant bucket allocation and
sorting during index construction. Run existing corruption, round-trip and
parsed-index tests, then compare the exact candidate on the named 10k native
HTTP fixture. Reuse the retained V8/classic evidence. Do not deploy until
route parity and latency are measured on the candidate.
