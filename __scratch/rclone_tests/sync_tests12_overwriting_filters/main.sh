rm -rf my_local
mkdir my_local
echo "hello" > my_local/hello.txt
echo "jimbo" > my_local/bojangles.txt


rm -rf my_remote
mkdir my_remote
echo "file" > my_remote/ignore_this.txt

# rclone --config rclone.conf sync my_local/hello.txt my_remote:hello.txt
rclone --config rclone.conf sync my_local my_remote: --exclude "ignore_this.txt"

rclone --config rclone.conf sync my_local my_remote: --filter "- ignore_this.txt"
