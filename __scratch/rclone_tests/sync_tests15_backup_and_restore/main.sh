rm -rf my_local
mkdir my_local
echo "hello" > my_local/hello.txt
echo "jimbo" > my_local/bojangles.txt
echo "same in both" > my_local/same_in_both.txt

rm -rf my_remote
mkdir my_remote
mkdir my_remote/my_dir

echo "goodbye!" > my_remote/my_dir/hello.txt
echo "file" > my_remote/my_dir/ignore_this.txt
echo "goodbye" > my_remote/my_dir/goodbye.txt
echo "same in both" > my_remote/my_dir/same_in_both.txt

rclone --config rclone.conf sync my_remote:my_dir my_remote:my_dir_old

# rclone --config rclone.conf sync my_local/hello.txt my_remote:hello.txt
rclone --config rclone.conf sync my_local my_remote:my_dir --backup-dir my_remote:backup

# Restore from backup
rclone --config rclone.conf sync my_remote:backup my_remote:my_dir

# restore protocol:
# - ls the contents of the target
# - copy over the contents of the backup to the target
# - remove any files from the target that are not in the ls


# rclone lsjson hetzner-box:repoyard/repos/20251116_190037_yBiGa__test-repo-1/data --files-only --recursive