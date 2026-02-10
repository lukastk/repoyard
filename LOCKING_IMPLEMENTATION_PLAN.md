# Plan: Add Locking Mechanism to Prevent Race Conditions

## Summary

Add file-based locking using `filelock` library to prevent race conditions when multiple repoyard commands run concurrently on the same repository.

## Problem Statement

Repoyard has critical race condition vulnerabilities:
1. **Sync + Sync (same repo)** - Two concurrent syncs create different ULIDs, one overwrites the other
2. **Sync + Exclude/Include (same repo)** - Exclude deletes data while sync is running
3. **refresh_repoyard_meta() races** - New repos lost when multiple commands call refresh concurrently
4. **repometa.toml overwrites** - Concurrent modifications lose changes

## Solution Architecture

### Lock Directory Structure
```
~/.repoyard/locks/
    global.lock                    # Protects repoyard_meta.json
    repos/{index_name}/
        sync.lock                  # Per-repo sync operations
```

### Lock Types and Timeouts
| Lock | Scope | Timeout | Protects |
|------|-------|---------|----------|
| Global | All repos | 30s | `repoyard_meta.json` writes |
| Repo Sync | Per repo | 10 min | sync, include, exclude, delete operations |

### Deadlock Prevention
Acquire locks in order: Global -> Repo (alphabetical if multiple repos)

---

## Implementation Steps

### Step 1: Add Dependency
**File:** `pyproject.toml`

Add `filelock>=3.12.0` to dependencies.

### Step 2: Create Locking Module (NEW FILE)
**File:** `pts/mod/_utils/04_locking.pct.py`

Create new module with:
- `RepoyardLockManager` class
  - `global_lock()` context manager
  - `repo_sync_lock(index_name)` context manager
  - `multiple_repo_sync_locks(index_names)` for batch operations
- Async versions: `async_global_lock()`, `async_repo_sync_lock()`
- `LockAcquisitionError` exception with helpful messages
- `cleanup_stale_locks()` utility (removes locks > 24h old)

### Step 3: Protect Global Meta Operations (CRITICAL)
**File:** `pts/mod/_models.pct.py`

Modify `refresh_repoyard_meta()` (~line 327):
```python
def refresh_repoyard_meta(config):
    from repoyard._utils.locking import RepoyardLockManager
    lock_manager = RepoyardLockManager(config.repoyard_data_path)
    with lock_manager.global_lock():
        repoyard_meta = create_repoyard_meta(config)
        # Atomic write: temp file + rename
        tmp_path = config.repoyard_meta_path.with_suffix('.tmp')
        tmp_path.write_text(repoyard_meta.model_dump_json())
        tmp_path.rename(config.repoyard_meta_path)
    return repoyard_meta
```

### Step 4: Protect Sync Operations (CRITICAL)
**File:** `pts/mod/cmds/03_sync_repo.pct.py`

Wrap entire sync with per-repo lock:
```python
from repoyard._utils.locking import RepoyardLockManager, async_repo_sync_lock

lock_manager = RepoyardLockManager(config.repoyard_data_path)
async with async_repo_sync_lock(lock_manager, repo_index_name):
    # ... existing sync code ...
```

### Step 5: Protect Include/Exclude (CRITICAL)
**Files:**
- `pts/mod/cmds/06_exclude_repo.pct.py`
- `pts/mod/cmds/07_include_repo.pct.py`

Same pattern - wrap with `async_repo_sync_lock()`.

### Step 6: Protect Delete Operations (HIGH)
**File:** `pts/mod/cmds/08_delete_repo.pct.py`

Wrap with per-repo sync lock.

### Step 7: Protect New Repo Creation (HIGH)
**File:** `pts/mod/cmds/01_new_repo.pct.py`

Use global lock around repo creation + refresh.

### Step 8: Atomic Writes for RepoMeta.save() (HIGH)
**File:** `pts/mod/_models.pct.py`

Modify `RepoMeta.save()` (~line 184) to use temp file + rename pattern.

### Step 9: Update CLI Error Handling
**File:** `pts/mod/_cli/main.pct.py`

Catch `LockAcquisitionError` in commands and display user-friendly message.

### Step 10: Run Export and Tests
```bash
nbl export --reverse && nbl export
uv run pytest -v -m "not integration"
```

---

## Files to Modify

| File | Change | Priority |
|------|--------|----------|
| `pyproject.toml` | Add filelock dependency | P0 |
| `pts/mod/_utils/04_locking.pct.py` | **NEW** - locking module | P0 |
| `pts/mod/_models.pct.py` | Lock `refresh_repoyard_meta()`, atomic `RepoMeta.save()` | P0 |
| `pts/mod/cmds/03_sync_repo.pct.py` | Add per-repo sync lock | P0 |
| `pts/mod/cmds/06_exclude_repo.pct.py` | Add per-repo sync lock | P0 |
| `pts/mod/cmds/07_include_repo.pct.py` | Add per-repo sync lock | P0 |
| `pts/mod/cmds/08_delete_repo.pct.py` | Add per-repo sync lock | P1 |
| `pts/mod/cmds/01_new_repo.pct.py` | Add global lock | P1 |
| `pts/mod/_cli/main.pct.py` | Error handling for lock timeouts | P2 |

---

## Verification

1. **Unit tests pass:** `uv run pytest -v -m "not integration"`
2. **Manual test - concurrent syncs blocked:**
   ```bash
   # Terminal 1: Start long sync
   repoyard sync -r test-repo
   # Terminal 2: Try another sync (should wait or error)
   repoyard sync -r test-repo
   ```
3. **Manual test - sync + exclude blocked:**
   ```bash
   # Terminal 1: Start sync
   repoyard sync -r test-repo
   # Terminal 2: Try exclude (should wait)
   repoyard exclude -r test-repo
   ```
4. **Manual test - parallel syncs on different repos allowed:**
   ```bash
   # Should run concurrently
   repoyard sync -r repo-a &
   repoyard sync -r repo-b &
   ```
5. **Lock file cleanup:** Verify locks are released after commands complete

---

## Notes

- Locks are created lazily (no migration needed)
- `filelock` is cross-platform (macOS, Linux, Windows)
- Soft interruption (Ctrl-C) releases locks via context manager finally blocks
- Nested lock acquisition is safe (same thread can re-acquire)
- Stale locks (from crashed processes) can be cleaned with `cleanup_stale_locks()`
