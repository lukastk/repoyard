
rm -rf my_remote
mkdir my_remote

# rclone --config rclone.conf bisync my_local my_remote: --resync

# rclone --config rclone.conf bisync my_local my_remote: --resync --include "folder1/*"
rclone --config rclone.conf bisync my_local my_remote: --resync --include "/folder1/jimmy.txt"
# rclone --config rclone.conf bisync my_local my_remote: --resync --include "bojangles.txt/*" 

tree my_remote