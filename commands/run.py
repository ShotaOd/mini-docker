import stat
import os
import subprocess
import uuid
from dataclasses import dataclass
from typing import List

import commands.format as fmt
import commands.images as img

import traceback
import linux
import cgroups

CONTAINER_DATA_DIR = '/var/opt/app/container'

@dataclass(frozen=True)
class ContainerDir:
    root_dir: str
    rw_dir: str
    work_dir: str


def _init_container_dir(container_id: str) -> ContainerDir:
    root_dir = os.path.join(CONTAINER_DATA_DIR, container_id)
    rootfs_dir = os.path.join(root_dir, 'rootfs')
    rw_dir = os.path.join(root_dir, 'cow_rw')
    work_dir = os.path.join(root_dir, 'cow_workdir')

    for d in (rootfs_dir, rw_dir, work_dir):
        if not os.path.exists(d):
            os.makedirs(d)

    return ContainerDir(root_dir=root_dir, rw_dir=rw_dir, work_dir=work_dir)


def _run_in_process(
        image: img.Image,
        container_id: str,
        container_dir: ContainerDir,
        cpus: float,
        memory: str,
        override_command: List[str]):
    try:
        pid = os.getpid()

        # control group の設定
        cg = cgroups.Cgroup(container_id)
        cg.set_cpu_limit(cpus)
        cg.set_memory_limit(memory)
        cg.add(pid)

        # コンテナにホスト名をセット
        linux.sethostname(container_id)

        # ルートディレクトリをプライベートにマウント
        # See: https://kernhack.hatenablog.com/entry/2015/05/30/115705
        # print('mounting / privately')
        # linux.mount(None, '/', None, linux.MS_PRIVATE | linux.MS_REC, '')

        # docker image ディレクトリを overlayfs としてマウント
        # See: https://gihyo.jp/admin/serial/01/linux_containers/0018
        # See: https://tech-lab.sios.jp/archives/21103
        print('mounting docker image directory')
        print(image.content_dir)
        linux.mount(
            'overlay',
            container_dir.root_dir,
            'overlay',
            linux.MS_NODEV,
            f"lowerdir={image.content_dir},upperdir={container_dir.rw_dir},workdir={container_dir.work_dir}"
        )

        # proc, sys, dev の linux システムディレクトリの作成
        # proc_dir = os.path.join(container_dir.root_dir, 'proc') # proc: PIDなどプロセスの情報
        # sys_dir = os.path.join(container_dir.root_dir, 'sys')   # sys: ドライバ関連のプロセスの情報
        # dev_dir = os.path.join(container_dir.root_dir, 'dev')   # dev: CPUやメモリなど基本デバイス
        # for d in (proc_dir, sys_dir, dev_dir):
        #     if not os.path.exists(d):
        #         os.makedirs(d)

        # システムディレクトリのマウント
        # print('mounting /proc, /sys, /dev, /dev/pts')
        # linux.mount('proc', proc_dir, 'proc', 0, '')
        # linux.mount('sysfs', sys_dir, 'sysfs', 0, '')
        # linux.mount('tmpfs', dev_dir, 'tmpfs', linux.MS_NOSUID | linux.MS_STRICTATIME, 'mode=755')

        # print('mounting devices')
        # for i, dev in enumerate(['stdin', 'stdout', 'stderror']):
        #     os.symlink(f'/proc/self/fd/{i}', os.path.join(dev_dir, dev))
        # devices = {'null': (stat.S_IFCHR, 1, 3), 'zero': (stat.S_IFCHR, 1, 5),
        #            'random': (stat.S_IFCHR, 1, 8), 'urandom': (stat.S_IFCHR, 1, 9),
        #            'console': (stat.S_IFCHR, 136, 1), 'tty': (stat.S_IFCHR, 5, 0),
        #            'full': (stat.S_IFCHR, 1, 7)}
        # for device, (dev_type, major, minor) in devices.items():
        #     os.mknod(os.path.join(dev_dir, device), 0o666 | dev_type, os.makedev(major, minor))

        # コンテナのルートディレクトリを変更
        # print('changing container root directory')
        # old_root = os.path.join(container_dir.root_dir, 'old_root')
        # os.makedirs(old_root)
        # linux.pivot_root(container_dir.root_dir, old_root)
        # os.chdir('/')
        # linux.umount2('/old_root', linux.MNT_DETACH)
        # os.rmdir('/old_root')
        os.chroot(container_dir.root_dir)
        os.chdir(os.path.expanduser('~'))

        command = override_command if len(override_command) > 0 else image.cmd

        print(f'🏃️💨 {fmt.GREEN}Docker container {container_id} started! executing {command[0]}{fmt.END}')
        os.execvp(command[0], command)

    except Exception as e:
        print(f'''
{fmt.RED}{type(e).__name__}
{e}{fmt.END}
        ''')
        traceback.print_exc()
        exit(1)


def run_run(image: str, tag: str, cpus: float, memory: str, command: List[str]):
    print(f'Start running {image}:{tag} ...')
    print(f'cpus={cpus}, memory={memory}')

    # イメージの検索・取得
    target_image = next((v for v in img.find_images() if v.name == f'library/{image}' and v.version == tag), None)
    if target_image is None:
        raise FileNotFoundError(f'{image}:{tag} not found')

    id = uuid.uuid4()
    container_id = f'{image}_{tag}_{id}'
    container_dir = _init_container_dir(container_id)

    # 分離させる名前空間のフラグ
    # See: https://gihyo.jp/admin/serial/01/linux_containers/0002
    flags = (
        linux.CLONE_NEWPID | # PID名前空間: プロセスIDの分離。異なる名前空間同士では、同一のプロセスIDを持つことが可能になる
        linux.CLONE_NEWUTS | # UTS名前空間: ホスト名, ドメイン名の分離
        linux.CLONE_NEWNS  | # マウント名前空間: ファイルシステムのマウントポイントの分離
        linux.CLONE_NEWNET   # ネットワーク名前空間: 分離されたネットワークスタックを提供する
    )

    # 子プロセスを作成。コンテナとして立ち上げる
    # See: https://linuxjm.osdn.jp/html/LDP_man-pages/man2/clone.2.html
    pid = linux.clone(_run_in_process, flags, (target_image, container_id, container_dir, cpus, memory, command))

    print(f'container process ID: {pid}')

    _, status = os.waitpid(pid, 0)
    print(f'{pid} exited with status {status}')
