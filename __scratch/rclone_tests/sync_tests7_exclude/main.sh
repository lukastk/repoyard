
rm -rf my_remote
mkdir my_remote

# rclone --config rclone.conf bisync my_local my_remote: --resync

rclone --config rclone.conf bisync my_local my_remote: --resync --filter "- /*/data/**" --filter "- /hello/" --filter "- goodbye"