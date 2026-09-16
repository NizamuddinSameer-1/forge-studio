# Git notes for this project

## The v7 repo can lose its branch ref

`yt content hashing/` is a git repo sitting **inside OneDrive**.
On 2026-09-13 a commit succeeded but its branch ref disappeared seconds later:

```
$ git commit -m "..."
[feature/v7-stage1-robust 5b2447d] feat: ML adversarial stage, ...
 19 files changed, 4311 insertions(+), 104 deletions(-)

$ git log
fatal: your current branch 'feature/v7-stage1-robust' does not have any commits yet
```

`.git/refs/heads/` contained only `master`. Everything else — objects, reflog,
working tree — was completely intact. **No work was lost.**

### Why

Git updates refs atomically: it writes `refs/heads/x.lock`, then renames it into
place. OneDrive's sync filter (and/or antivirus) appears to interfere with that
rename inside a synced folder. Tellingly:

- `git update-ref refs/heads/<branch> <sha>` reported success and wrote a reflog
  entry, but the ref file still did not appear.
- Writing the file directly with `echo <sha> > .git/refs/heads/<branch>` **did**
  persist.

A direct write survives; the rename does not.

### Fix it

The commit object is never lost, so recovery is always possible. Find the sha in
the reflog and re-point the branch:

```bash
cd "yt content hashing"
git reflog                                       # find the sha you lost
git branch -f feature/v7-stage1-robust <sha>
```

If `git branch -f` does not stick either, write the ref directly:

```bash
mkdir -p .git/refs/heads/feature
echo <sha> > .git/refs/heads/feature/v7-stage1-robust
```

Then confirm:

```bash
git log --oneline -3 && git status
```

### Check after every commit

```bash
git log -1
```

If that says *"does not have any commits yet"*, the ref was eaten again — run the
recovery above. Your files are fine; only the pointer is missing.

### The real fix

Move the repo out of OneDrive, or exclude the `.git` folder from OneDrive sync.
As long as it stays in a synced folder, expect this to happen again.

---

## Repo layout

| Path | Repo? | Notes |
|---|---|---|
| `yt content hashing/` | ✅ git | Branch `feature/v7-stage1-robust`. Has `.gitignore` for `input/`, `output/`, caches. |
| project root, `app/`, `tools/` | ❌ not tracked | The studio itself is unversioned. |

## Handy commands

```bash
cd "yt content hashing"
python -m pytest -q          # 43 tests
git status --short           # should be clean
```
