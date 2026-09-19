# Agent operating policy

This file is the durable repository operating law for agents working in DungeonMind. Slice-specific facts belong in checked-in handoffs. Product UX and campaign-memory presentation belong in DungeonMindBuddy.

DungeonMind owns durable world knowledge, identity, provenance, revisions/publication, retrieval semantics, and knowledge persistence.

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
