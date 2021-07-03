# Mini docker
学習用のなんちゃってDocker

## セットアップ

### VMの作成と起動

```bash
vagrant up
vagrant ssh
```

```bash
sudo su -
```

```bash
cat /etc/os-release

# --->
# NAME="Ubuntu"
# VERSION="20.10 (Groovy Gorilla)" 
```

### セットアップスクリプトを実行
```bash
cd /vagrant
./init.sh
```

## コマンド
### Docker imageのpull

```bash
./mini-docker pull ubuntu

# or タグを指定
./mini-docker pull ubuntu:latest

# or レジストリを指定
./mini-docker pull hashicorp/http-echo
```

### Docker imageの確認

```bash
./mini-docker images
```

### コンテナの起動

```bash
./mini-docker run busybox

# cmd 上書き
./mini-docker run busybox /bin/ash
```

### コンテナ環境のclean

> todo clean mount point 

```
./mini-docker clean
```

## 各種動作確認

### PID名前空間の分離

#### hostとコンテナでPID名前空間が分離されている
コンテナから見ると、自身にPID = 1 が割り当てられている

*host (VM)*
```bash
ps a
# --->
#    PID TTY      STAT   TIME COMMAND
#    698 tty1     Ss+    0:00 /sbin/agetty -o -p -- \u --noclear tty1 linux
#  ...
#  20414 pts/0    S      0:00 -bash
#  20559 pts/0    S      0:00 /usr/bin/python3 ./mini-docker run --memory 100M ubuntu /bin/bash 
#  ...
#  20587 pts/1    R+     0:00 ps a
```

*container*
```bash
./mini-docker run busybox top
# --->
#    PID TTY      STAT   TIME COMMAND
#      1 ?        S      0:00 /bin/bash
#     24 ?        R+     0:00 ps a
```

### UTS名前空間の分離

#### UTS名前空間が分離されている

*host (VM)*
```bash
hostname
# --->  vagrant
hostname newhost
hostname
# ---> newhost
```

*container*
```bash
./mini-docker run busybox
hostname
# ---> library-busybox_latest_b3b66eea-8ab6-49dd-96ff-b6be8eb1b62f
hostname container
hostname
# ---> container
```

*host (VM)*
```bash
hostname
# ---> newhost
```

### chroot, overlayfs

#### hostはコンテナのルートディレクトリ内を見られるが、コンテナは自身のルートディレクトリから外側を見ることができない

*host (VM)*
```bash
touch /tmp/a.txt
ls /tmp | grep 'a.txt'
# ---> a.txt
```

*container*
```bash
ls / | grep 'a.txt'
# ---> <nothing>

touch /b.txt
ls / | grep 'b.txt'
# ---> b.txt
```

*host (VM)*
```bash
ls /var/opt/app/container/library-busybox_latest_b3b66eea-8ab6-49dd-96ff-b6be8eb1b62f/cow_rw/ | grep 'b.txt'
# ---> b.txt
```

### リソースの分離 (cgroup)

#### コンテナの最大CPU利用量を制限できる

*host (VM)*
```bash
# 1コアの25%までに制限
./mini-docker run --cpus 0.25 ubuntu /bin/bash
```

*host (VM - another terminal)*
```bash
# CPUの状況をグラフィカルに表示するかっこいいツールのインストール
pip3 install s-tui
s-tui
```

*container*
```bash
yes > /dev/null
```

#### コンテナの最大メモリ利用量を制限できる

*host (VM)*
```bash
./mini-docker run --memory 100M ubuntu /bin/bash
```

*host (VM - another terminal)*
```bash
sudo su -
htop -d 0.3 -p {pid}
```

*container*
```bash
yes > /dev/null
# ---> yes: standard output: Broken pipe
# ---> Killed
```

#### 同一ポートを複数コンテナで起動できる

- echo server を pull
```bash
./mini-docker pull hashicorp/http-echo
```

- vagrant instance の ip を取得する
```bash
ip addr show eth1 | grep 'inet ' | xargs echo | cut -d' ' -f2 | cut -d'/' -f1

# ---> (ex.) 172.28.128.3
```

- terminalを3つ用意する
    - *host not in vagrant*
    - *container 1*
    - *container 2*

*container 1* port **50001** で待ち受ける

```bash
sudo su -
cd /vagrant
./mini-docker run --port 50001:5678  hashicorp/http-echo /http-echo -text "this is container 1"
```

*container 2* port **50002** で待ち受ける

```bash
sudo su -
cd /vagrant
./mini-docker run --port 50002:5678  hashicorp/http-echo /http-echo -text "this is container 2"
```

*host not in vagrant*

```bash
curl <vagrant_instance_ip>:50001
# ---> this is container 1

curl <vagrant_instance_ip>:50002
# ---> this is container 2
```

## 参考
- [Fewbytes/rubber-docker](https://github.com/Fewbytes/rubber-docker)
- [tonybaloney/mocker](https://github.com/tonybaloney/mocker)