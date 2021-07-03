from commands.network import network_clean
import subprocess


def _umount_overlayfs():
    print('umount all overlayfs')
    cmd = 'mount -t overlay'
    res = subprocess.run(cmd.split(' '), stdout=subprocess.PIPE, text=True)
    mount_points = [line.split(' ')[2] for line in res.stdout.split('\n') if line]
    for point in mount_points:
        print(f'  u: {point}')
        umount_cmd = f'umount -l {point}'
        subprocess.run(umount_cmd.split(' '))


def run_clean():
    _umount_overlayfs()
    network_clean()
