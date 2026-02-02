# ---
# jupyter:
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # _force_push_to_remote

# %%
#|default_exp cmds._force_push_to_remote
#|export_as_func true

# %%
#|hide
from nblite import nbl_export, show_doc; nbl_export();

# %%
#|top_export
from pathlib import Path
import asyncio

from repoyard.config import get_config
from repoyard._models import get_repoyard_meta, RepoPart, SyncRecord
from repoyard._remote_index import find_remote_repo_by_id
from repoyard._utils.rclone import rclone_sync, rclone_mkdir, rclone_purge
from repoyard._utils.locking import RepoyardLockManager, REPO_SYNC_LOCK_TIMEOUT, acquire_lock_async
from repoyard._utils import check_interrupted, SoftInterruption

# %%
#|set_func_signature
async def force_push_to_remote(
    config_path: Path,
    repo_index_name: str,
    source_path: Path,
    force: bool = False,
    show_rclone_progress: bool = False,
    soft_interruption_enabled: bool = True,
    verbose: bool = False,
) -> None:
    """
    Force push a local folder to a repo's remote DATA location.

    This is a destructive operation that overwrites the remote DATA with the
    contents of source_path. It properly manages sync records for consistency.

    Args:
        config_path: Path to the repoyard config file
        repo_index_name: The index name of the repository (local)
        source_path: Source folder to push
        force: Required safety flag - must be True to proceed
        show_rclone_progress: Show rclone progress output
        soft_interruption_enabled: Enable soft interruption handling
        verbose: Print verbose output

    Raises:
        ValueError: If force is False or source_path doesn't exist
    """
    ...

# %% [markdown]
# Set up testing args

# %%
from tests.integration.conftest import create_repoyards

remote_name, remote_rclone_path, config, config_path, data_path = create_repoyards()

# %%
# Args
from repoyard.cmds import new_repo, sync_repo
import tempfile

config_path = config_path
repo_index_name = new_repo(
    config_path=config_path, repo_name="test_repo", storage_location="my_remote"
)
# Create a temp source directory with some test content
source_path = Path(tempfile.mkdtemp()) / "force_push_source"
source_path.mkdir(parents=True)
(source_path / "test_file.txt").write_text("test content for force push")

force = True  # Must be True for the operation to proceed
show_rclone_progress = False
soft_interruption_enabled = True
verbose = False

# %%
# Sync the repo first so there's something on remote
await sync_repo(config_path=config_path, repo_index_name=repo_index_name)

# %% [markdown]
# # Function body

# %% [markdown]
# Safety check: require force flag

# %%
#|export
if not force:
    raise ValueError(
        "This is a destructive operation that will overwrite the remote DATA. "
        "You must pass --force to confirm."
    )

# %%
#|export
config = get_config(config_path)

# %%
#|export
source_path = Path(source_path).resolve()

if not source_path.exists():
    raise ValueError(f"Source path '{source_path}' does not exist.")

if not source_path.is_dir():
    raise ValueError(f"Source path '{source_path}' is not a directory.")

# %%
#|export
repoyard_meta = get_repoyard_meta(config)

if repo_index_name not in repoyard_meta.by_index_name:
    raise ValueError(f"Repo '{repo_index_name}' does not exist locally.")

repo_meta = repoyard_meta.by_index_name[repo_index_name]

# %% [markdown]
# Find the remote index name (may differ from local due to renames)

# %%
#|export
storage_location = repo_meta.storage_location
sl_config = config.storage_locations[storage_location]

# Find remote index name by repo_id (handles renames)
remote_index_name = await find_remote_repo_by_id(
    config=config,
    storage_location=storage_location,
    repo_id=repo_meta.repo_id,
)

if remote_index_name is None:
    raise ValueError(
        f"Repo '{repo_index_name}' not found on remote storage '{storage_location}'. "
        f"The repo may have been deleted or the remote is not accessible."
    )

if verbose:
    print(f"Found remote repo: {remote_index_name}")

# %% [markdown]
# Build remote paths

# %%
#|export
from repoyard import const

remote_repo_path = sl_config.store_path / const.REMOTE_REPOS_REL_PATH / remote_index_name
remote_data_path = remote_repo_path / const.REPO_DATA_REL_PATH

# Sync record paths
local_sync_record_path = repo_meta.get_local_sync_record_path(config, RepoPart.DATA)
remote_sync_record_path = (
    sl_config.store_path
    / const.SYNC_RECORDS_REL_PATH
    / remote_index_name  # Use remote index name for remote sync record
    / f"{RepoPart.DATA.value}.rec"
)

# Backup paths
local_sync_backups_path = config.local_sync_backups_path / repo_meta.index_name / RepoPart.DATA.value
remote_sync_backups_path = (
    sl_config.store_path
    / const.REMOTE_BACKUP_REL_PATH
    / remote_index_name  # Use remote index name for remote backups
    / RepoPart.DATA.value
)

# %% [markdown]
# Acquire per-repo sync lock

# %%
#|export
_lock_manager = RepoyardLockManager(config.repoyard_data_path)
_lock_path = _lock_manager.repo_sync_lock_path(repo_index_name)
_lock_manager._ensure_lock_dir(_lock_path)
_sync_lock = __import__('filelock').FileLock(_lock_path, timeout=0)
await acquire_lock_async(
    _sync_lock,
    f"repo sync ({repo_index_name})",
    _lock_path,
    REPO_SYNC_LOCK_TIMEOUT,
)

# %% [markdown]
# Perform the force push with proper sync record management

# %%
#|export
try:
    if soft_interruption_enabled and check_interrupted():
        raise SoftInterruption()

    if verbose:
        print(f"Force pushing {source_path} to {storage_location}:{remote_data_path}")

    # Create incomplete sync record and save to BOTH sides (same ULID)
    # This creates a "sync session" marker - if interrupted, both sides have the same incomplete ULID,
    # proving this machine owns the interrupted sync and can safely retry
    rec = SyncRecord.create(sync_complete=False)
    backup_name = str(rec.ulid)

    if verbose:
        print(f"Creating sync session with ULID: {rec.ulid}")

    # Save incomplete record to both sides BEFORE syncing
    await rec.rclone_save(
        config.rclone_config_path.as_posix(),
        storage_location,
        remote_sync_record_path.as_posix(),
    )
    await rec.rclone_save(
        config.rclone_config_path.as_posix(),
        "",
        local_sync_record_path.as_posix(),
    )

    # Create backup directory on remote
    backup_path = remote_sync_backups_path / backup_name
    await rclone_mkdir(
        rclone_config_path=config.rclone_config_path.as_posix(),
        source=storage_location,
        source_path=backup_path.as_posix(),
    )

    if verbose:
        print("Syncing data to remote...")

    # Perform the sync (source -> remote DATA)
    success, stdout, stderr = await rclone_sync(
        rclone_config_path=config.rclone_config_path.as_posix(),
        source="",
        source_path=source_path.as_posix(),
        dest=storage_location,
        dest_path=remote_data_path.as_posix(),
        backup_path=f"{storage_location}:{backup_path.as_posix()}",
        progress=show_rclone_progress,
    )

    if not success:
        raise RuntimeError(f"Failed to sync to remote: {stderr}")

    if verbose:
        print("Sync completed successfully.")

    # Update sync records to complete state
    complete_rec = SyncRecord.create(sync_complete=True)
    await complete_rec.rclone_save(
        config.rclone_config_path.as_posix(),
        "",
        local_sync_record_path.as_posix(),
    )
    await complete_rec.rclone_save(
        config.rclone_config_path.as_posix(),
        storage_location,
        remote_sync_record_path.as_posix(),
    )

    if verbose:
        print("Sync records updated.")

    # Clean up backup
    await rclone_purge(
        rclone_config_path=config.rclone_config_path.as_posix(),
        source=storage_location,
        source_path=backup_path.as_posix(),
    )

    if verbose:
        print("Backup cleaned up.")
        print(f"Force push complete: {source_path} -> {storage_location}:{remote_data_path}")

finally:
    _sync_lock.release()
