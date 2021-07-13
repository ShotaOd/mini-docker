import os
import traceback
import uuid
from typing import List, Dict, Any

import cgroups
import linux
from pyroute2 import netns as NetNs

import commands.config as cfg
import commands.data as data
import commands.format as fmt
import commands.images as img
import commands.network as net


def _init_container(image: data.Image, tag: str) -> data.Container:
    id = f'{image.name.replace("/", "-")}_{tag}_{uuid.uuid4()}'
    root_dir = os.path.join(cfg.CONTAINER_DATA_DIR, id)
    rw_dir = os.path.join(root_dir, 'cow_rw')
    work_dir = os.path.join(root_dir, 'cow_workdir')

    for d in (rw_dir, work_dir):
        if not os.path.exists(d):
            os.makedirs(d)

    # docker image ディレクトリを overlayfs としてマウント
    # See: https://gihyo.jp/admin/serial/01/linux_containers/0018
    # See: https://tech-lab.sios.jp/archives/21103
    print('mounting docker image directory')
    print(image.content_dir)
    linux.mount(
        'overlay',
        root_dir,
        'overlay',
        linux.MS_NODEV,
        f"lowerdir={image.content_dir},upperdir={rw_dir},workdir={work_dir}"
    )

    return data.Container(id=id, root_dir=root_dir)


def pre_exec(image: data.Image, container: data.Container, option: Dict[str, Any]):
    try:
        container_id = container.id
        pid = os.getpid()
        cpus = option['cpus']
        memory = option['memory']
        netns = option['netns']
        override_cmd = option['override_cmd']

        # hostnameの設定
        print(f'set hostname {container_id}')
        linux.sethostname(container_id)

        # network namespace を設定
        print(f'set network namespace {netns}')
        NetNs.setns(netns)

        # control group の設定
        print(f'set control group')
        cg = cgroups.Cgroup(container_id)
        cg.set_cpu_limit(cpus)
        cg.set_memory_limit(memory)
        cg.add(pid)

        # proc, sys, dev の linux システムディレクトリの作成
        proc_dir = os.path.join(container.root_dir, 'proc')  # proc: PIDなどプロセスの情報
        sys_dir = os.path.join(container.root_dir, 'sys')  # sys: ドライバ関連のプロセスの情報
        dev_dir = os.path.join(container.root_dir, 'dev')  # dev: CPUやメモリなど基本デバイス
        for d in (proc_dir, sys_dir, dev_dir):
            if not os.path.exists(d):
                os.makedirs(d)

        # システムディレクトリのマウント
        print('mounting /proc, /sys, /dev, /dev/pts')
        linux.mount('proc', proc_dir, 'proc', 0, '')
        linux.mount('sysfs', sys_dir, 'sysfs', 0, '')

        # root directory の設定
        print(f'set root directory {container.root_dir}')
        os.chroot(container.root_dir)

        # working directory の設定
        if image.working_dir:
            print(f'set working directory {image.working_dir}')
            os.chdir(image.working_dir)
        else:
            os.chdir('/')

        # commandの解決
        cmd = override_cmd if len(override_cmd) > 0 else image.cmd
        if cmd:
            os.execvp(cmd[0], cmd)
            print(f'🏃️💨 {fmt.GREEN}Docker container {container.id} started! executing {cmd[0]}{fmt.END}')

    except Exception as e:
        print(f'''
    {fmt.RED}{type(e).__name__}
    {e}{fmt.END}
            ''')
        traceback.print_exc()
        exit(1)


def run_run(registry: str, image: str, tag: str, cpus: float, memory: str, source: int, dest: int,
            override_command: List[str]):
    print(f'running {registry}/{image}:{tag} ...')
    print(f'cpus={cpus}, memory={memory}, port={source}:{dest}')

    # イメージの検索・取得
    target_image = next((v for v in img.find_images() if v.name == f'{registry}/{image}' and v.version == tag), None)
    if target_image is None:
        raise FileNotFoundError(f'{image}:{tag} not found')

    # networkの初期化
    netns = net.init_container_network(source=source, dest=dest)

    # containerの初期化
    container = _init_container(target_image, tag)

    # 分離させる名前空間のフラグ
    # See: https://gihyo.jp/admin/serial/01/linux_containers/0002
    flags = (
            linux.CLONE_NEWPID |  # PID名前空間: プロセスIDの分離。異なる名前空間同士では、同一のプロセスIDを持つことが可能になる
            linux.CLONE_NEWUTS |  # UTS名前空間: ホスト名, ドメイン名の分離
            linux.CLONE_NEWNS |  # マウント名前空間: ファイルシステムのマウントポイントの分離
            linux.CLONE_NEWNET  # ネットワーク名前空間: 分離されたネットワークスタックを提供する
    )

    # 子プロセスを作成。コンテナとして立ち上げる
    # See: https://linuxjm.osdn.jp/html/LDP_man-pages/man2/clone.2.html
    option = {'cpus': cpus, 'memory': memory, 'netns': netns, 'override_cmd': override_command}
    pid = linux.clone(pre_exec, flags, (target_image, container, option))
    print(f'container process ID: {pid}')

    _, status = os.waitpid(pid, 0)
    print(f'{pid} exited with status {status}')
