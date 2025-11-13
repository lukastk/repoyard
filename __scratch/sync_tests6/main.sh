
rm -rf my_remote
mkdir my_remote
echo "hello" > my_remote/goodbye.txt

rm -rf my_local
echo "hello" > my_local/hello.txt
echo "jimbo" > my_local/bojangles.txt

# Will remove the goodbye.txt file from my_remote
rclone --config rclone.conf sync my_local my_remote: --exclude-from exclude.txt

rclone --config rclone.conf sync my_local my_remote: --exclude "jimbo.txt"

# copy the contents without removing anything
# rclone --config rclone.conf copy my_local my_remote:

rclone --config rclone.conf ls my_remote:

rclone --config rclone.conf lsjson my_remote:


rclone --config rclone.conf bisync my_local my_remote:

rclone --config rclone.conf bisync my_local my_remote: --resync

echo bojangles > my_local/bojangles.txt

rclone --config rclone.conf bisync my_local my_remote:


