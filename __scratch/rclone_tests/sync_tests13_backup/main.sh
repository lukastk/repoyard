rm -rf my_local
mkdir my_local
echo "hello" > my_local/hello.txt
echo "jimbo" > my_local/bojangles.txt


rm -rf my_remote
mkdir my_remote
mkdir my_remote/my_dir
echo "file" > my_remote/my_dir/ignore_this.txt

# rclone --config rclone.conf sync my_local/hello.txt my_remote:hello.txt
rclone --config rclone.conf sync my_local my_remote:my_dir --backup-dir my_remote:backup