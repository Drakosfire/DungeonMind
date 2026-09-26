# Agent operating policy

This file is the durable repository operating law for agents working in DungeonMind. Slice-specific facts belong in checked-in handoffs. Product UX and campaign-memory presentation belong in DungeonMindBuddy.

DungeonMind owns durable world knowledge, identity, provenance, revisions/publication, retrieval semantics, and knowledge persistence.

## Ecosystem execution core — overmind-agent-core-v1

These rules are intentionally shared across active DungeonMind ecosystem repositories. Repository-specific law may add constraints, but it must not weaken this core.

1. **Re-anchor before action.** Fetch the current remote default branch and inspect relevant open PRs/active work before editing, reviewing, or merging. Chat history, stale handoffs, and local `main` are not current authority.
2. **Respect ownership boundaries.** Cross-repository architecture and sequencing belong in DungeonOverMind; runtime/product implementation belongs in the repository that owns the capability. When a change crosses owners, name the contract.
3. **Handoffs are portable bounded contracts.** A handoff may live on `main`, a branch, a PR, or another durable pinned ref/location. Its location alone neither activates nor invalidates it. Execution authority comes from explicit authorization/status, a pinned authority/ref, and bounded scope/write ownership. Do not require a handoff to be merged to `main` unless the specific workstream explicitly makes that a gate.
4. **Finish authorized implementation work all the way to a PR.** Once implementation is authorized, ordinary completion includes: implement → test/verify → inspect the cumulative diff → commit intended changes → push the branch → open or update the assigned PR. If no PR exists, open it. Do not stop with intended work only local, uncommitted, or unpushed and wait for another prompt to commit/push/open the PR.
5. **Merge is separate authority.** Opening/updating a PR is part of implementation completion; merging it is not. Merge only when the user or the repository's explicit process authorizes merge.
6. **Use isolated Git lanes.** Do not develop on local `main`. Use a branch/worktree or equivalent isolated checkout, and treat file/runtime/state collisions as coordination problems rather than relying on Git conflicts.
7. **Keep slices bounded.** One implementation slice should deliver one independently useful capability. A second capability, new durable/public contract, or unplanned extra PR is a stop/split signal unless explicitly authorized.
8. **Verify at the owning boundary.** Review the exact cumulative base→head diff and prove behavior at the layer that owns the invariant. A green helper test is not evidence for a boundary it does not exercise.
9. **Settle after merge.** Re-anchor, synchronize mutable authority that now became stale, and prune superseded process/transition scaffolding. Git history is the default archive; preserve a separate archive copy only when it carries unique durable evidence.

## Always release `main`

Git will not check out the same branch in two worktrees. **Never leave `main` checked out.**

- Do not work on `main`. Do not `git switch main` / `git checkout main` / `git pull` on `main` to clean up or start the next task.
- Start from the remote, without checking out local `main`:

      git fetch origin main
      git switch -c <branch> origin/main

- Add worktrees the same way. Never `git worktree add <path> main`. Never `git worktree add <path>` while this repo is on `main`.

      git fetch origin main
      git worktree add -b <branch> <new-path> origin/main

- If you are on `main`, release it immediately:

      git fetch origin main
      git switch --detach origin/main

- Before you finish a turn, `git branch --show-current` must not print `main`. If it does, detach as above.

## Worktree / Cursor workspace switch order

Never delete, move, or prune the checkout the **current Cursor window** is using until a replacement checkout is live in that window.

Required order:

1. `git fetch origin main`
2. Create the new worktree from `origin/main`. Never `git worktree add <path> main`. Never add a worktree while this repo has `main` checked out.

       git worktree add -b <branch> <new-path> origin/main

3. Switch the Cursor workspace / agent root onto `<new-path>`.
4. Confirm a **new terminal** launches: `pwd` is `<new-path>`, `git branch --show-current` is not `main`, and Git commands succeed.
5. Only then remove or move the previous worktree.

Do not invert this. Deleting the open worktree first leaves terminals spawning in a missing directory (`worktree doesn't exist`) and the window stays bound to a path that is gone.

`move_agent_to_root` fetches `origin/<branch>` at the destination. A local-only branch aborts that switch. Push the new branch, or open the new folder in Cursor, **before** removing the old checkout.
