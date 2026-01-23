# ---
# jupyter:
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Copy From Remote Integration Tests
#
# Tests for the `copy` command that downloads a remote repo to an arbitrary local path
# without including it in repoyard tracking.
#
# Tests:
# - Basic copy DATA to arbitrary path
# - Copy with --meta and --conf flags
# - Error without --overwrite when dest exists
# - Success with --overwrite
# - Error when dest is within repoyard data path (safety check)
# - Error when dest is within user repos path (safety check)

# %%
#|default_exp integration.cmds.test_copy_from_remote
#|export_as_func true

# %%
#|hide
from nblite import nbl_export, show_doc; nbl_export();

# %%
#|top_export
import asyncio
import pytest
import tempfile
import shutil
from pathlib import Path

from repoyard.cmds import (
    new_repo,
    sync_repo,
)
from repoyard.cmds._copy_from_remote import copy_from_remote
from repoyard._models import get_repoyard_meta, RepoPart
from repoyard.config import get_config
from repoyard import const

from tests.integration.conftest import create_repoyards

# %%
#|top_export
@pytest.mark.integration
def test_copy_from_remote():
    """Test copy command for downloading remote repos without tracking."""
    asyncio.run(_test_copy_from_remote())

# %%
#|set_func_signature
async def _test_copy_from_remote(): ...

# %% [markdown]
# ## Initialize repoyard

# %%
#|export
remote_name, remote_rclone_path, config, config_path, data_path = create_repoyards()

# %% [markdown]
# ## Create a repo with some data

# %%
#|export
repo_index_name = new_repo(
    config_path=config_path,
    repo_name="test-copy-repo",
    storage_location=remote_name,
)

# Refresh config and get repo meta
config = get_config(config_path)
repoyard_meta = get_repoyard_meta(config, force_create=True)
repo_meta = repoyard_meta.by_index_name[repo_index_name]

# Add some test data
local_data_path = repo_meta.get_local_part_path(config, RepoPart.DATA)
test_file = local_data_path / "test_data.txt"
test_file.write_text("Hello from copy test!")

# Add nested directory
nested_dir = local_data_path / "nested" / "subdir"
nested_dir.mkdir(parents=True, exist_ok=True)
(nested_dir / "nested_file.txt").write_text("Nested content")

# Sync to remote
await sync_repo(config_path=config_path, repo_index_name=repo_index_name)

# %% [markdown]
# ## Test 1: Basic copy DATA to arbitrary path

# %%
#|export
# Create temp directory for copy destination
with tempfile.TemporaryDirectory() as temp_dir:
    dest_path = Path(temp_dir) / "my_copy"

    result_path = await copy_from_remote(
        config_path=config_path,
        repo_index_name=repo_index_name,
        dest_path=dest_path,
        verbose=True,
    )

    assert result_path == dest_path.resolve()
    assert dest_path.exists()
    assert (dest_path / "test_data.txt").exists()
    assert (dest_path / "test_data.txt").read_text() == "Hello from copy test!"
    assert (dest_path / "nested" / "subdir" / "nested_file.txt").exists()
    assert (dest_path / "nested" / "subdir" / "nested_file.txt").read_text() == "Nested content"

    # Verify no repometa.toml by default
    assert not (dest_path / const.REPO_METAFILE_REL_PATH).exists()

    # Verify no conf folder by default
    assert not (dest_path / const.REPO_CONF_REL_PATH).exists()

# %% [markdown]
# ## Test 2: Copy with --meta flag

# %%
#|export
with tempfile.TemporaryDirectory() as temp_dir:
    dest_path = Path(temp_dir) / "my_copy_with_meta"

    result_path = await copy_from_remote(
        config_path=config_path,
        repo_index_name=repo_index_name,
        dest_path=dest_path,
        copy_meta=True,
        verbose=True,
    )

    assert dest_path.exists()
    assert (dest_path / "test_data.txt").exists()

    # Verify repometa.toml was copied
    assert (dest_path / const.REPO_METAFILE_REL_PATH).exists()

# %% [markdown]
# ## Test 3: Error without --overwrite when dest exists

# %%
#|export
with tempfile.TemporaryDirectory() as temp_dir:
    dest_path = Path(temp_dir) / "existing_dest"
    dest_path.mkdir(parents=True)
    (dest_path / "existing_file.txt").write_text("I exist already")

    try:
        await copy_from_remote(
            config_path=config_path,
            repo_index_name=repo_index_name,
            dest_path=dest_path,
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "already exists" in str(e)
        assert "--overwrite" in str(e)

# %% [markdown]
# ## Test 4: Success with --overwrite

# %%
#|export
with tempfile.TemporaryDirectory() as temp_dir:
    dest_path = Path(temp_dir) / "existing_dest"
    dest_path.mkdir(parents=True)
    (dest_path / "existing_file.txt").write_text("I exist already")

    result_path = await copy_from_remote(
        config_path=config_path,
        repo_index_name=repo_index_name,
        dest_path=dest_path,
        overwrite=True,
        verbose=True,
    )

    assert dest_path.exists()
    assert (dest_path / "test_data.txt").exists()
    assert (dest_path / "test_data.txt").read_text() == "Hello from copy test!"

# %% [markdown]
# ## Test 5: Error when dest is within repoyard data path

# %%
#|export
# Try to copy to within repoyard data path
bad_dest = config.repoyard_data_path / "bad_copy_dest"

try:
    await copy_from_remote(
        config_path=config_path,
        repo_index_name=repo_index_name,
        dest_path=bad_dest,
    )
    assert False, "Should have raised ValueError"
except ValueError as e:
    assert "is within the repoyard data path" in str(e)

# %% [markdown]
# ## Test 6: Error when dest is within user repos path

# %%
#|export
# Try to copy to within user repos path
bad_dest = config.user_repos_path / "bad_copy_dest"

try:
    await copy_from_remote(
        config_path=config_path,
        repo_index_name=repo_index_name,
        dest_path=bad_dest,
    )
    assert False, "Should have raised ValueError"
except ValueError as e:
    assert "is within the user repos path" in str(e)

# %% [markdown]
# ## Test 7: Verify no sync records created

# %%
#|export
with tempfile.TemporaryDirectory() as temp_dir:
    dest_path = Path(temp_dir) / "no_sync_record_copy"

    await copy_from_remote(
        config_path=config_path,
        repo_index_name=repo_index_name,
        dest_path=dest_path,
    )

    # Verify no sync record was created in the destination
    # (This is implicit - there's nowhere for a sync record to be in an arbitrary path)
    assert dest_path.exists()
    assert not (dest_path / ".repoyard").exists()

# %% [markdown]
# ## Cleanup

# %%
#|export
from repoyard.cmds import delete_repo

await delete_repo(config_path=config_path, repo_index_name=repo_index_name)
