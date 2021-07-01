import subprocess

from pyroute2 import netns, NDB


# https://github.com/ldx/python-iptables/issues/37
# XTABLES_LIBDIR to iptables
# import iptc

def _init_bridge(ndb: NDB):
    bridge_name = 'br-container'

    if ndb.interfaces.exists(bridge_name):
        return bridge_name

    print(f'  create bridge for container network "{bridge_name}"')

    # bridgeを作成
    (ndb.interfaces
     .create(ifname=bridge_name, kind='bridge')
     .commit())

    (ndb.interfaces[bridge_name]
     .set(state='up')
     .commit())

    return bridge_name


def _init_host_peer(ndb: NDB, bridge_name: str):
    gw = '192.168.0.1'
    veth_br = 'v0br'
    veth_peer = 'v0p'

    if ndb.interfaces.exists(veth_br):
        return gw

    # bridge ~ host の virtual ethernet を作成
    print(f'  create virtual ethernet between [BRIDGE][{veth_br}] ~ [HOST](peer:{veth_peer})')
    (ndb.interfaces
     .create(ifname=veth_br,
             kind='veth',
             peer=veth_peer)
     .commit())

    # brige用のinterfaceを、bridgeに追加
    ndb.interfaces[bridge_name].add_port(veth_br).commit()

    # bridge側の interfaceを起動
    (ndb.interfaces
     .wait(ifname=veth_br)
     .set(state='up')
     .commit())

    # peer側の interfaceを起動
    (ndb.interfaces
     .wait(ifname=veth_peer)
     .set(state='up')
     .add_ip(f'{gw}/24')
     .commit())

    return gw


def _init_netns():
    ns_list = netns.listnetns()
    ns_idx = len(ns_list) + 1
    netns_name = f'container-ns-{ns_idx}'

    print(f'  create  network namespace "{netns_name}"')
    netns.create(netns_name)
    return netns_name


def _init_container_peer(ndb: NDB, bridge: str, netns_name: str):
    bridge_ifs = [i for i in ndb.interfaces if i['slave_kind'] == 'bridge']
    network_idx = len(bridge_ifs) + 1

    veth_br = f'v{network_idx}br'
    veth_container = f'v{network_idx}p'

    # bridge ~ container 用の virtual ethernet を作成する
    print(f'  create virtual ethernet between [BRIDGE]({veth_br}) ~ [{netns_name}]({veth_container})')
    ndb.sources.add(netns=netns_name)
    (ndb.interfaces
     .create(ifname=veth_br,
             kind='veth',
             peer={
                 'ifname': veth_container,
                 'net_ns_fd': netns_name,
             })
     .commit())

    (ndb.interfaces
     .wait(ifname=veth_br)
     .set(state='up')
     .commit())

    (ndb.interfaces
     .wait(target=netns_name, ifname=veth_container)
     .add_ip(f'192.168.0.{network_idx}/24')
     .set(state='up')
     .commit())

    # virtual ethernet の 終端を bridgeに接続する
    ndb.interfaces[bridge].add_port(veth_br).commit()
    return


def _init_gw_route(netns: str, gw: str):
    # FIXME replace pyroute2
    subprocess.run(['ip', 'netns', 'exec', netns, 'ip', 'route', 'add', 'default', 'via', gw])


def _clean(ndb: NDB):
    bridge_name = _init_bridge(ndb)

    for p in ndb.interfaces[bridge_name].ports:
        ifname = p['ifname']
        print(f'delete [veth]({ifname}) in bridge')
        ndb.interfaces[ifname].remove().commit()

    for ns in netns.listnetns():
        if (ns.startswith('container-ns-')):
            print(f'delete netns "{ns}"')
            netns.remove(ns)

    ndb.interfaces[bridge_name].remove().commit()


def run_network_clean():
    with NDB(log='on') as ndb:
        _clean(ndb)


def run_network(container_pid: int):
    netns_name = _init_netns()
    net_ns_fd = open(f'/proc/{container_pid}/ns/net').fileno()

    with NDB(log='on') as ndb:
        print('initialize required host-container network')
        bridge_name = _init_bridge(ndb)
        gw = _init_host_peer(ndb, bridge_name)

        print('initialize each container network')
        _init_container_peer(ndb, bridge_name, netns_name)
        _init_gw_route(netns_name, gw)
