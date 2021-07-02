import subprocess
from dataclasses import dataclass

from pyroute2 import netns, NDB


@dataclass
class Bridge:
    ip: str
    name: str


def _init_bridge(ndb: NDB) -> Bridge:
    gw = '192.168.0.1'
    bridge_name = 'br-container'
    bridge = Bridge(ip=gw, name=bridge_name)

    if ndb.interfaces.exists(bridge_name):
        return bridge

    print(f'  create bridge for container network "{bridge_name}"')

    # bridgeを作成
    (ndb.interfaces
     .create(ifname=bridge_name, kind='bridge')
     .commit())

    (ndb.interfaces[bridge_name]
     .set(state='up')
     .add_ip(f'{gw}/24')
     .commit())

    return bridge


def _init_netns():
    ns_list = netns.listnetns()
    ns_idx = len(ns_list) + 1
    netns_name = f'container-ns-{ns_idx}'

    print(f'  create  network namespace "{netns_name}"')
    netns.create(netns_name)
    return netns_name


def _init_container_peer(ndb: NDB, bridge: str, netns_name: str):
    bridge_ifs = [i for i in ndb.interfaces if i['slave_kind'] == 'bridge']
    network_idx = len(bridge_ifs) + 2

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
    bridge = _init_bridge(ndb)

    for p in ndb.interfaces[bridge.name].ports:
        ifname = p['ifname']
        print(f'delete [veth]({ifname}) in bridge')
        ndb.interfaces[ifname].remove().commit()

    for ns in netns.listnetns():
        if ns.startswith('container-ns-'):
            print(f'delete netns "{ns}"')
            netns.remove(ns)

    ndb.interfaces[bridge.name].remove().commit()


def network_clean():
    with NDB(log='on') as ndb:
        _clean(ndb)


def init_container_netns() -> str:
    with NDB(log='on') as ndb:
        print('initialize required host bridge network')
        bridge = _init_bridge(ndb)

        print('initialize each container network')
        netns_name = _init_netns()
        _init_container_peer(ndb, bridge.name, netns_name)
        _init_gw_route(netns_name, bridge.ip)

        return netns_name
