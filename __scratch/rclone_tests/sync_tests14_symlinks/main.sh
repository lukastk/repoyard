
rm -rf my_remote
mkdir my_remote

# rclone --config rclone.conf sync my_local/hello.txt my_remote:hello.txt
rclone --config rclone.conf sync my_local my_remote: --links