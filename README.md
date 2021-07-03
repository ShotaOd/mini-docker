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

### ネットワーク名前空間の分離

#### ネットワーク名前空間の確認

- terminalを2つ用意
  - *host*
  - *container 1*
  - *container 2*

*container 1*

```bash
sudo su -
cd /vagrant

./mini-docker run alpine
ip addr

# --->
# 1: lo: <LOOPBACK> mtu 65536 qdisc noop qlen 1000
#     link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
# 2: v8p@if26: <BROADCAST,MULTICAST,UP,LOWER_UP,M-DOWN> mtu 1500 qdisc noqueue qlen 1000
#     link/ether 6a:95:d9:da:11:ca brd ff:ff:ff:ff:ff:ff
#     inet 192.168.0.8/24 scope global v8p
#        valid_lft forever preferred_lft forever
#     inet6 fe80::6895:d9ff:feda:11ca/64 scope link
#        valid_lft forever preferred_lft forever
```

*container 2*

```bash
sudo su -
cd /vagrant

./mini-docker run alpine
ip addr

# --->
# 1: lo: <LOOPBACK> mtu 65536 qdisc noop state DOWN qlen 1000
#     link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00```
# 2: v11p@if29: <BROADCAST,MULTICAST,UP,LOWER_UP,M-DOWN> mtu 1500 qdisc noqueue state UP qlen 1000
#     link/ether a6:0a:06:39:11:35 brd ff:ff:ff:ff:ff:ff#### 同一ポートを複数コンテナで起動できる
#     inet 192.168.0.11/24 scope global v11p
#        valid_lft forever preferred_lft forever- echo server を pull
#     inet6 fe80::a40a:6ff:fe39:1135/64 scope link```bash
#        valid_lft forever preferred_lft forever./mini-docker pull hashicorp/http-echo
```

*host*

- containerから、bridgeへ疎通ができる

```bash
ip netns exec container-ns-1 ping 192.168.0.1
# PING 192.168.0.1 (192.168.0.1) 56(84) bytes of data.
# 64 bytes from 192.168.0.1: icmp_seq=1 ttl=64 time=0.050 ms
# 64 bytes from 192.168.0.1: icmp_seq=2 ttl=64 time=0.052 ms
^C
# --- 192.168.0.1 ping statistics ---
```

- container1から、container2へ疎通ができる

```bash
ip netns exec container-ns-2 ping 192.168.0.3
# PING 192.168.0.1 (192.168.0.3) 56(84) bytes of data.
# 64 bytes from 192.168.0.3: icmp_seq=1 ttl=64 time=0.050 ms
# 64 bytes from 192.168.0.3: icmp_seq=2 ttl=64 time=0.052 ms
^C
# --- 192.168.0.1 ping statistics ---
```

#### 異なるネットワーク名前空間で、重複したportで起動できる

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