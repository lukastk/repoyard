# Plan: ID-Based Syncing with Flexible Names and Tombstones

## Overview

This plan restructures repoyard to use the **repo ID** (timestamp + subid) as the immutable sync key, allowing names to be flexible and differ between local and remote. It also introduces a simple tombstone approach for deleted repos.

## Key Concepts

### Current Nomenclature
- `index_name`: `{timestamp}_{subid}__{name}` (e.g., `20251122_143022_a7kx9__my-project`)
- Used as directory name and unique identifier

### New Nomenclature
- **Repo ID**: `{timestamp}_{subid}` (e.g., `20251122_143022_a7kx9`) - immutable, unique identifier
- **Name**: Human-readable label (e.g., `my-project`) - can differ between local/remote
- **Index name**: `{repo_id}__{name}` - still used for directories, but can differ local vs remote

### Core Principle
**Syncing is based on ID, not name.** A local repo with ID `X` syncs to remote repo with ID `X`, regardless of whether their names match.

---

## Part 1: Nomenclature and Model Changes

### 1.1 Update `RepoMeta` Model

**File:** `pts/mod/_models.pct.py`

```python
class RepoMeta(StrictModel):
    repo_id: str          # "20251122_143022_a7kx9" - the immutable ID
    name: str             # "my-project" - the human-readable name
    # ... other fields ...

    @property
    def index_name(self) -> str:
        """Full index name (ID + name), used for directory paths."""
        return f"{self.repo_id}__{self.name}"

    @classmethod
    def parse_index_name(cls, index_name: str) -> tuple[str, str]:
        """Parse index_name into (repo_id, name)."""
        parts = index_name.split("__", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid index_name format: {index_name}")
        return parts[0], parts[1]

    @classmethod
    def extract_repo_id(cls, index_name: str) -> str:
        """Extract just the repo_id from an index_name."""
        return cls.parse_index_name(index_name)[0]
```

### 1.2 Update `RepoyardMeta` Model

**File:** `pts/mod/_models.pct.py`

Add lookup by ID:
```python
class RepoyardMeta(StrictModel):
    repo_metas: list[RepoMeta]

    @property
    def by_index_name(self) -> dict[str, RepoMeta]:
        """Lookup by full index_name."""
        return {rm.index_name: rm for rm in self.repo_metas}

    @property
    def by_repo_id(self) -> dict[str, RepoMeta]:
        """Lookup by repo_id only."""
        return {rm.repo_id: rm for rm in self.repo_metas}
```

### 1.3 Update CLI Argument Handling

**File:** `pts/mod/_cli/main.pct.py`

Update repo selection to accept either full index_name OR just repo_id:
```python
def resolve_repo(
    config: Config,
    repo_ref: str,  # Can be index_name OR repo_id
) -> RepoMeta:
    """Resolve a repo reference (index_name or repo_id) to RepoMeta."""
    repoyard_meta = get_repoyard_meta(config)

    # Try exact index_name match first
    if repo_ref in repoyard_meta.by_index_name:
        return repoyard_meta.by_index_name[repo_ref]

    # Try repo_id match
    if repo_ref in repoyard_meta.by_repo_id:
        return repoyard_meta.by_repo_id[repo_ref]

    # Try partial match on repo_id
    matches = [rm for rm in repoyard_meta.repo_metas if rm.repo_id.startswith(repo_ref)]
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        raise ValueError(f"Ambiguous repo reference '{repo_ref}'. Matches: {[m.index_name for m in matches]}")

    raise ValueError(f"Repo '{repo_ref}' not found.")
```

---

## Part 2: Syncing by ID

### 2.1 Core Sync Logic Change

**Current behavior:** Sync local path `repos/{index_name}/` to remote path `repos/{index_name}/`

**New behavior:** Sync local repo with ID `X` to remote repo with ID `X`, even if names differ

### 2.2 Finding Remote Repo by ID

When syncing, we need to find the remote repo path for a given ID. Options:

**Approach: Local cache with fallback to remote scan**

Cache location: `~/.repoyard/remote_indexes/{storage_location}.json`

```json
{
    "20251122_143022_a7kx9": "20251122_143022_a7kx9__my-project",
    "20251122_143025_b8mz2": "20251122_143025_b8mz2__other-repo"
}
```

**Lookup logic:**
```python
async def find_remote_repo_by_id(config, storage_location, repo_id) -> str | None:
    """Find remote index_name for a given repo_id."""
    # 1. Check local cache
    cache = load_remote_index_cache(config, storage_location)
    if repo_id in cache:
        cached_index_name = cache[repo_id]
        # Verify it still exists on remote
        if await rclone_exists(config, storage_location, f"repos/{cached_index_name}"):
            return cached_index_name
        # Cache is stale, remove entry
        del cache[repo_id]

    # 2. Cache miss or stale - do full scan
    repos = await rclone_lsjson(config, storage_location, "repos/")
    for item in repos:
        if item["IsDir"] and item["Name"].startswith(f"{repo_id}__"):
            # Update cache
            cache[repo_id] = item["Name"]
            save_remote_index_cache(config, storage_location, cache)
            return item["Name"]

    # 3. Not found - remove from cache if present
    if repo_id in cache:
        del cache[repo_id]
        save_remote_index_cache(config, storage_location, cache)

    return None
```

**Cache utilities:**
```python
def get_remote_index_cache_path(config, storage_location) -> Path:
    return config.repoyard_data_path / "remote_indexes" / f"{storage_location}.json"

def load_remote_index_cache(config, storage_location) -> dict[str, str]:
    cache_path = get_remote_index_cache_path(config, storage_location)
    if cache_path.exists():
        return json.loads(cache_path.read_text())
    return {}

def save_remote_index_cache(config, storage_location, cache: dict[str, str]) -> None:
    cache_path = get_remote_index_cache_path(config, storage_location)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2))

def update_remote_index_cache(config, storage_location, repo_id, index_name) -> None:
    """Update a single entry in the cache (e.g., after rename)."""
    cache = load_remote_index_cache(config, storage_location)
    cache[repo_id] = index_name
    save_remote_index_cache(config, storage_location, cache)

def remove_from_remote_index_cache(config, storage_location, repo_id) -> None:
    """Remove an entry from the cache (e.g., after delete)."""
    cache = load_remote_index_cache(config, storage_location)
    if repo_id in cache:
        del cache[repo_id]
        save_remote_index_cache(config, storage_location, cache)
```

### 2.3 Update `sync_repo` Command

**File:** `pts/mod/cmds/03_sync_repo.pct.py`

```python
# Find remote repo by ID (may have different name)
remote_index_name = await find_remote_repo_by_id(config, repo_meta.storage_location, repo_meta.repo_id)

if remote_index_name is None:
    # Check tombstones
    if await is_tombstoned(config, repo_meta.storage_location, repo_meta.repo_id):
        raise ValueError(f"Repo '{repo_meta.repo_id}' was deleted on remote. Cannot sync.")
    # Remote doesn't exist - this is a new repo, push it
    remote_index_name = repo_meta.index_name

# Note if names differ
if remote_index_name != repo_meta.index_name:
    local_name = repo_meta.name
    remote_name = RepoMeta.parse_index_name(remote_index_name)[1]
    print(f"Note: Local name '{local_name}' differs from remote name '{remote_name}'")

# Sync using the remote's index_name for remote paths
await sync_helper(
    local_path=repo_meta.get_local_part_path(config, part),
    remote_path=f"repos/{remote_index_name}/{part.value}",
    ...
)
```

### 2.4 Update Status Display

**File:** `pts/mod/_cli/main.pct.py` (status command)

When displaying repo status, show both names if they differ:
```
Repo: 20251122_143022_a7kx9
  Local name:  my-project
  Remote name: my-renamed-project  [DIFFERS]
  Status: synced
```

---

## Part 3: Rename Feature

### 3.1 Rename Scope Options

Renaming can be:
- **Local only** - Just rename local directories/metadata
- **Remote only** - Just rename remote directories/metadata
- **Both** - Rename both local and remote

### 3.2 Create `rename_repo` Command

**File:** `pts/mod/cmds/10_rename_repo.pct.py` (NEW)

```python
async def rename_repo(
    config_path: Path,
    repo_ref: str,              # Can be index_name or repo_id
    new_name: str,
    scope: Literal["local", "remote", "both"] = "both",
    soft_interruption_enabled: bool = True,
):
    """
    Rename a repository.

    Args:
        repo_ref: Repository reference (index_name or repo_id)
        new_name: The new name for the repository
        scope: Where to apply the rename - "local", "remote", or "both"
    """
```

**Implementation:**

```python
# Resolve repo
repo_meta = resolve_repo(config, repo_ref)
old_name = repo_meta.name
new_index_name = f"{repo_meta.repo_id}__{new_name}"

if scope in ("local", "both"):
    # Rename local directories
    old_local_path = repo_meta.get_local_path(config)
    new_local_path = old_local_path.parent / new_index_name
    old_local_path.rename(new_local_path)

    # Rename data directory
    old_data_path = repo_meta.get_local_part_path(config, RepoPart.DATA)
    new_data_path = old_data_path.parent / new_index_name
    old_data_path.rename(new_data_path)

    # Rename sync records directory
    old_sync_records = config.sync_records_path / repo_meta.index_name
    new_sync_records = config.sync_records_path / new_index_name
    if old_sync_records.exists():
        old_sync_records.rename(new_sync_records)

    # Update repometa.toml
    repo_meta.name = new_name
    repo_meta.save(config)

    # Refresh repoyard_meta
    refresh_repoyard_meta(config)

    # Update user symlinks
    await create_user_symlinks(config_path)

if scope in ("remote", "both"):
    # Find current remote index_name
    remote_index_name = await find_remote_repo_by_id(config, repo_meta.storage_location, repo_meta.repo_id)
    if remote_index_name is None:
        raise ValueError(f"Repo '{repo_meta.repo_id}' not found on remote")

    new_remote_index_name = f"{repo_meta.repo_id}__{new_name}"

    # Rename remote directories using rclone moveto
    await rclone_moveto(config, repo_meta.storage_location,
                        f"repos/{remote_index_name}", f"repos/{new_remote_index_name}")
    await rclone_moveto(config, repo_meta.storage_location,
                        f"sync_records/{remote_index_name}", f"sync_records/{new_remote_index_name}")

    # Update the remote index cache
    update_remote_index_cache(config, repo_meta.storage_location, repo_meta.repo_id, new_remote_index_name)
```

### 3.3 Create `sync_name` Command

**File:** `pts/mod/cmds/11_sync_name.pct.py` (NEW)

Command to sync names between local and remote (bidirectional with required flag):

```python
async def sync_name(
    config_path: Path,
    repo_ref: str,
    to_local: bool = False,
    to_remote: bool = False,
    soft_interruption_enabled: bool = True,
):
    """
    Sync repository name between local and remote.

    Exactly one of to_local or to_remote must be True.

    Args:
        to_local: Rename local to match remote name
        to_remote: Rename remote to match local name
    """
    # Validate flags - exactly one must be set
    if to_local == to_remote:
        raise ValueError("Must specify exactly one of --to-local or --to-remote")

    config = get_config(config_path)
    repo_meta = resolve_repo(config, repo_ref)
    remote_index_name = await find_remote_repo_by_id(config, repo_meta.storage_location, repo_meta.repo_id)

    if remote_index_name is None:
        raise ValueError(f"Repo '{repo_meta.repo_id}' not found on remote")

    local_name = repo_meta.name
    remote_name = RepoMeta.parse_index_name(remote_index_name)[1]

    if local_name == remote_name:
        print(f"Names already match: '{local_name}'")
        return

    if to_local:
        print(f"Renaming local '{local_name}' → '{remote_name}' (to match remote)")
        await rename_repo(config_path, repo_ref, remote_name, scope="local")
    else:  # to_remote
        print(f"Renaming remote '{remote_name}' → '{local_name}' (to match local)")
        await rename_repo(config_path, repo_ref, local_name, scope="remote")
```

### 3.4 CLI Commands

**File:** `pts/mod/_cli/main.pct.py`

```python
@app.command(name="rename")
def cli_rename(
    repo: str = Option(..., "--repo", "-r", help="Repo index_name or repo_id"),
    new_name: str = Option(..., "--new-name", "-n", help="New name for the repository"),
    scope: str = Option("both", "--scope", "-s", help="Where to rename: local, remote, or both"),
):
    """Rename a repository."""
    asyncio.run(rename_repo(get_config_path(), repo, new_name, scope))

@app.command(name="sync-name")
def cli_sync_name(
    repo: str = Option(..., "--repo", "-r", help="Repo index_name or repo_id"),
    to_local: bool = Option(False, "--to-local", help="Rename local to match remote"),
    to_remote: bool = Option(False, "--to-remote", help="Rename remote to match local"),
):
    """
    Sync repository name between local and remote.

    Must specify exactly one of --to-local or --to-remote.
    """
    asyncio.run(sync_name(get_config_path(), repo, to_local=to_local, to_remote=to_remote))

@app.command(name="untombstone")
def cli_untombstone(
    repo_id: str = Option(..., "--repo-id", "-i", help="The repo ID to untombstone"),
    storage_location: str = Option(..., "--storage-location", "-s", help="Storage location"),
):
    """
    Remove a tombstone, allowing a previously deleted repo ID to be reused.

    Use with caution - this is for recovering from accidental deletions.
    """
    asyncio.run(remove_tombstone(get_config_path(), storage_location, repo_id))
```

---

## Part 4: Tombstones for Deleted Repos

### 4.1 Tombstone Structure

**Location:** `{storage_location}:{store_path}/tombstones/{repo_id}.json`

**Content:**
```json
{
    "repo_id": "20251122_143022_a7kx9",
    "deleted_at_utc": "2025-01-23T12:34:56Z",
    "deleted_by_hostname": "MacBook-Pro",
    "last_known_name": "my-project"
}
```

### 4.2 Tombstone Utilities

**File:** `pts/mod/_tombstones.pct.py` (NEW)

```python
class Tombstone(StrictModel):
    repo_id: str
    deleted_at_utc: datetime
    deleted_by_hostname: str
    last_known_name: str

async def create_tombstone(
    config: Config,
    storage_location: str,
    repo_id: str,
    last_known_name: str,
) -> None:
    """Create a tombstone for a deleted repo."""
    tombstone = Tombstone(
        repo_id=repo_id,
        deleted_at_utc=datetime.now(timezone.utc),
        deleted_by_hostname=get_hostname(),
        last_known_name=last_known_name,
    )

    # Write to remote
    tombstone_path = f"tombstones/{repo_id}.json"
    await rclone_write(config, storage_location, tombstone_path, tombstone.model_dump_json())

async def is_tombstoned(
    config: Config,
    storage_location: str,
    repo_id: str,
) -> bool:
    """Check if a repo_id has been tombstoned."""
    tombstone_path = f"tombstones/{repo_id}.json"
    return await rclone_exists(config, storage_location, tombstone_path)

async def get_tombstone(
    config: Config,
    storage_location: str,
    repo_id: str,
) -> Tombstone | None:
    """Get tombstone info for a repo_id, or None if not tombstoned."""
    tombstone_path = f"tombstones/{repo_id}.json"
    content = await rclone_cat(config, storage_location, tombstone_path)
    if content is None:
        return None
    return Tombstone.model_validate_json(content)

async def list_tombstones(
    config: Config,
    storage_location: str,
) -> list[Tombstone]:
    """List all tombstones for a storage location."""
    files = await rclone_lsjson(config, storage_location, "tombstones/")
    tombstones = []
    for f in files:
        if f["Name"].endswith(".json"):
            content = await rclone_cat(config, storage_location, f"tombstones/{f['Name']}")
            tombstones.append(Tombstone.model_validate_json(content))
    return tombstones

async def remove_tombstone(
    config_path: Path,
    storage_location: str,
    repo_id: str,
) -> None:
    """
    Remove a tombstone, allowing a repo ID to be reused.

    Use for recovering from accidental deletions.
    """
    config = get_config(config_path)
    tombstone_path = f"tombstones/{repo_id}.json"

    if not await rclone_exists(config, storage_location, tombstone_path):
        raise ValueError(f"No tombstone found for repo ID '{repo_id}'")

    await rclone_delete(config, storage_location, tombstone_path)
    print(f"Removed tombstone for '{repo_id}'")
```

### 4.3 Update `delete_repo` Command

**File:** `pts/mod/cmds/08_delete_repo.pct.py`

```python
async def delete_repo(
    config_path: Path,
    repo_ref: str,
    soft_interruption_enabled: bool = True,
):
    """Delete a repository."""
    config = get_config(config_path)
    repo_meta = resolve_repo(config, repo_ref)

    # Check if remote exists
    remote_index_name = await find_remote_repo_by_id(config, repo_meta.storage_location, repo_meta.repo_id)
    remote_exists = remote_index_name is not None

    # Acquire lock
    ...

    try:
        if remote_exists:
            # Create tombstone BEFORE deleting
            await create_tombstone(
                config,
                repo_meta.storage_location,
                repo_meta.repo_id,
                repo_meta.name,
            )

            # Delete remote repo
            await rclone_purge(config, repo_meta.storage_location, f"repos/{remote_index_name}")
            await rclone_purge(config, repo_meta.storage_location, f"sync_records/{remote_index_name}")

        # Delete local repo (works even if remote doesn't exist - orphaned repo case)
        local_path = repo_meta.get_local_path(config)
        if local_path.exists():
            shutil.rmtree(local_path)

        data_path = repo_meta.get_local_part_path(config, RepoPart.DATA)
        if data_path.exists():
            shutil.rmtree(data_path)

        sync_records_path = config.sync_records_path / repo_meta.index_name
        if sync_records_path.exists():
            shutil.rmtree(sync_records_path)

        # Refresh metadata
        refresh_repoyard_meta(config)

    finally:
        # Release lock
        ...
```

### 4.4 Update `sync_repo` to Check Tombstones

**File:** `pts/mod/cmds/03_sync_repo.pct.py`

```python
# Early in sync_repo, after resolving repo_meta:

# Check if repo was tombstoned
if await is_tombstoned(config, repo_meta.storage_location, repo_meta.repo_id):
    tombstone = await get_tombstone(config, repo_meta.storage_location, repo_meta.repo_id)
    raise ValueError(
        f"Cannot sync repo '{repo_meta.repo_id}': it was deleted on {tombstone.deleted_at_utc} "
        f"by {tombstone.deleted_by_hostname}.\n"
        f"Run 'repoyard delete -r {repo_meta.repo_id}' to remove the local orphaned copy."
    )
```

### 4.5 Update `get_sync_status` for Tombstones

**File:** `pts/mod/_models.pct.py`

Add new sync condition:
```python
class SyncCondition(Enum):
    ...
    TOMBSTONED = "tombstoned"  # Repo was deleted on remote
```

---

## Part 5: Multi-Sync and Status Updates

### 5.1 Update `multi-sync` Command

**File:** `pts/mod/_cli/multi-sync.pct.py`

When syncing multiple repos:
1. For each repo, find remote by ID
2. Note name mismatches
3. Skip tombstoned repos with warning

### 5.2 Update Status Command

Show name mismatches clearly:
```
$ repoyard status

Storage: my_remote
  20251122_143022_a7kx9
    Local:  my-project
    Remote: my-renamed-project  [NAME MISMATCH]
    Status: synced

  20251122_143025_b8mz2
    Local:  other-repo
    Remote: other-repo
    Status: needs_push

  20251122_143030_c9na3
    Local:  deleted-project
    Remote: [TOMBSTONED - deleted 2025-01-20 by MacBook-Air]
    Status: orphaned
```

---

## Part 6: New Utility Functions

### 6.1 `rclone_moveto` Function

**File:** `pts/mod/_utils/01_rclone.pct.py`

```python
async def rclone_moveto(
    config: Config,
    remote: str,
    source_path: str,
    dest_path: str,
) -> None:
    """Move/rename a remote path."""
    cmd = [
        "rclone", "moveto",
        "--config", str(config.rclone_config_path),
        f"{remote}:{source_path}",
        f"{remote}:{dest_path}",
    ]
    returncode, stdout, stderr = await run_cmd_async(cmd)
    if returncode != 0:
        raise RuntimeError(f"rclone moveto failed: {stderr}")
```

### 6.2 `rclone_exists` Function

**File:** `pts/mod/_utils/01_rclone.pct.py`

```python
async def rclone_exists(
    config: Config,
    remote: str,
    path: str,
) -> bool:
    """Check if a remote path exists."""
    result = await rclone_lsjson(config, remote, path)
    return result is not None
```

### 6.3 `rclone_cat` Function

**File:** `pts/mod/_utils/01_rclone.pct.py`

```python
async def rclone_cat(
    config: Config,
    remote: str,
    path: str,
) -> str | None:
    """Read contents of a remote file."""
    cmd = [
        "rclone", "cat",
        "--config", str(config.rclone_config_path),
        f"{remote}:{path}",
    ]
    returncode, stdout, stderr = await run_cmd_async(cmd)
    if returncode != 0:
        return None
    return stdout
```

### 6.4 `rclone_write` Function (via rclone rcat)

**File:** `pts/mod/_utils/01_rclone.pct.py`

```python
async def rclone_write(
    config: Config,
    remote: str,
    path: str,
    content: str,
) -> None:
    """Write content to a remote file."""
    # Write to temp file first, then copy
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        f.write(content)
        temp_path = f.name

    try:
        cmd = [
            "rclone", "copyto",
            "--config", str(config.rclone_config_path),
            temp_path,
            f"{remote}:{path}",
        ]
        returncode, stdout, stderr = await run_cmd_async(cmd)
        if returncode != 0:
            raise RuntimeError(f"rclone write failed: {stderr}")
    finally:
        Path(temp_path).unlink()
```

### 6.5 `rclone_delete` Function

**File:** `pts/mod/_utils/01_rclone.pct.py`

```python
async def rclone_delete(
    config: Config,
    remote: str,
    path: str,
) -> None:
    """Delete a single remote file."""
    cmd = [
        "rclone", "deletefile",
        "--config", str(config.rclone_config_path),
        f"{remote}:{path}",
    ]
    returncode, stdout, stderr = await run_cmd_async(cmd)
    if returncode != 0:
        raise RuntimeError(f"rclone delete failed: {stderr}")
```

---

## Files Summary

| File | Change | Priority |
|------|--------|----------|
| `pts/mod/_models.pct.py` | Add `by_repo_id`, `parse_index_name`, `TOMBSTONED` condition | P0 |
| `pts/mod/_tombstones.pct.py` | **NEW** - Tombstone model and utilities | P0 |
| `pts/mod/_remote_index.pct.py` | **NEW** - Remote index cache utilities | P0 |
| `pts/mod/_utils/01_rclone.pct.py` | Add `rclone_moveto`, `rclone_exists`, `rclone_cat`, `rclone_write`, `rclone_delete` | P0 |
| `pts/mod/cmds/08_delete_repo.pct.py` | Create tombstone, handle orphaned repos, update cache | P0 |
| `pts/mod/cmds/03_sync_repo.pct.py` | Check tombstones, find remote by ID (with cache), note name mismatches | P0 |
| `pts/mod/cmds/10_rename_repo.pct.py` | **NEW** - Rename command (local/remote/both) | P1 |
| `pts/mod/cmds/11_sync_name.pct.py` | **NEW** - Sync name with required --to-local / --to-remote flags | P1 |
| `pts/mod/_cli/main.pct.py` | Add `rename`, `sync-name`, `untombstone` commands, update `resolve_repo` | P1 |
| `pts/mod/_cli/multi-sync.pct.py` | Handle name mismatches, skip tombstoned | P2 |
| `pts/mod/cmds/04_sync_missing_repometas.pct.py` | Skip tombstoned repos | P2 |
| `pts/mod/config.pct.py` | Add `remote_indexes_path` property | P0 |
| `pts/mod/cmds/01_new_repo.pct.py` | Add ID collision check, `--sync-first` flag | P1 |

---

## Part 7: ID Collision Prevention

### 7.1 Update `new_repo` Command

**File:** `pts/mod/cmds/01_new_repo.pct.py`

When generating a new repo ID, verify it doesn't collide with any existing local repo:

```python
async def new_repo(
    config_path: Path,
    repo_name: str,
    storage_location: str,
    sync_repometas_first: bool = False,  # NEW - optionally sync before checking
    soft_interruption_enabled: bool = True,
):
    config = get_config(config_path)

    # Optionally sync repometas first to get latest state from remote
    if sync_repometas_first:
        await sync_missing_repometas(config_path)

    # Get all existing repo IDs
    repoyard_meta = get_repoyard_meta(config)
    existing_ids = {rm.repo_id for rm in repoyard_meta.repo_metas}

    # Generate unique repo ID (with collision check)
    repo_id = generate_unique_repo_id(existing_ids)

    # ... rest of new_repo logic ...
```

### 7.2 ID Generation with Collision Check

**File:** `pts/mod/_models.pct.py` (or a new utility)

```python
import random
import string
from datetime import datetime

def generate_repo_id() -> str:
    """Generate a repo ID: {timestamp}_{5-char-subid}"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    subid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"{timestamp}_{subid}"

def generate_unique_repo_id(existing_ids: set[str], max_attempts: int = 100) -> str:
    """
    Generate a repo ID that doesn't collide with existing IDs.

    Args:
        existing_ids: Set of existing repo IDs to check against
        max_attempts: Maximum generation attempts before raising error

    Returns:
        A unique repo ID

    Raises:
        RuntimeError: If unable to generate unique ID after max_attempts
    """
    for _ in range(max_attempts):
        repo_id = generate_repo_id()
        if repo_id not in existing_ids:
            return repo_id

    raise RuntimeError(
        f"Failed to generate unique repo ID after {max_attempts} attempts. "
        f"This should be extremely rare - please report this issue."
    )
```

### 7.3 Config Option

**File:** `pts/mod/config.pct.py`

Add to Config model:
```python
class Config(StrictModel):
    # ... existing fields ...

    # New repo creation settings
    sync_before_new_repo: bool = False  # If True, sync repometas before creating new repo
```

**In config.toml:**
```toml
# Optional - sync repometas before creating new repos to check for ID collisions on remote
# Default: false
sync_before_new_repo = true
```

### 7.4 CLI Flag (overrides config)

**File:** `pts/mod/_cli/main.pct.py`

```python
@app.command(name="new")
def cli_new(
    repo_name: str = Option(..., "--name", "-n", help="Name for the new repository"),
    storage_location: str = Option(..., "--storage-location", "-s", help="Storage location"),
    sync_first: bool | None = Option(None, "--sync-first/--no-sync-first",
        help="Sync repometas before creating (overrides config.sync_before_new_repo)"),
    # ... other options ...
):
    """Create a new repository."""
    config = get_config(get_config_path())

    # CLI flag overrides config, config overrides default (False)
    should_sync_first = sync_first if sync_first is not None else config.sync_before_new_repo

    asyncio.run(new_repo(
        get_config_path(),
        repo_name,
        storage_location,
        sync_repometas_first=should_sync_first,
    ))
```

### 7.4 Why This Is Safe

- The ID format `{timestamp}_{5-char-subid}` has ~60 million combinations per second
- Collision probability is astronomically low even without checking
- But checking is cheap (just a set lookup) and provides defense-in-depth
- The `--sync-first` flag allows paranoid users to also check against remote state

---

## Migration Notes

- No migration needed - changes are backward compatible
- Existing repos continue to work
- Tombstones are created going forward
- Old repos without tombstones just won't have that protection

---

## Resolved Questions

1. **Un-tombstone feature** - Yes, include `repoyard untombstone -r <repo_id>` to remove tombstone file

2. **Bidirectional name sync** - Single command with required direction flag:
   ```
   repoyard sync-name -r <repo> --to-local   # Rename local to match remote
   repoyard sync-name -r <repo> --to-remote  # Rename remote to match local
   ```
   Running without either flag should error.

3. **Remote index cache** - Maintain a local cache mapping repo IDs to remote index names:
   - Cache location: `~/.repoyard/remote_indexes/{storage_location}.json`
   - On sync: check cache first, if miss or stale → full scan → update cache
   - Cache invalidation: if cached index_name doesn't exist on remote → full scan
