
rm -rf my_remote
mkdir my_remote
echo "hello" > my_remote/goodbye.txt

rm -rf my_local
mkdir my_local
echo "hello" > my_local/hello.txt
echo "jimbo" > my_local/bojangles.txt

# rclone --config rclone.conf bisync my_local my_remote: --resync