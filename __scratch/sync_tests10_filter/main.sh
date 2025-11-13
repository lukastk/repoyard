
rm -rf my_remote
mkdir my_remote

# rclone --config rclone.conf bisync my_local my_remote: --resync

# rclone --config rclone.conf bisync my_local my_remote: --resync --filter "+ /folder1/" --filter "+ /*/data/**" --filter "- **"
# rclone --config rclone.conf bisync my_local my_remote: --resync --include "/folder1/*"
# rclone --config rclone.conf bisync my_local my_remote: --resync --include "bojangles.txt/*" 

# rclone --config rclone.conf bisync my_local my_remote: --resync --filter "+ /*/jimmy.txt"
rclone --config rclone.conf bisync my_local my_remote: --resync --include "/*/jimmy.txt"


tree my_remote