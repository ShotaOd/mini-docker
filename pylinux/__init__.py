import os
import ctypes

from syscall_table import syscall_table
import signal as sig
import namespace as ns

from cgroups import Cgroup

# def before_exec(c_group: Cgroup, root_dir: str) -> Callable[[], None]:
#     def fn():
#         c_group.add(os.getpid())
#
#         ctypes.
#         os.chroot(root_dir)
#
#     return fn


def main():
    print('foo')
    import time
    time.sleep(10)


c_main_pointer = ctypes.CFUNCTYPE(ctypes.c_void_p)(main)


def foo():
    # # cg = Cgroup('test')
    #
    # # リソース制限をかける
    # # cg.set_cpu_limit(50)
    # # cg.set_memory_limit(50)
    #
    # c_dll = ctypes.CDLL(None)
    # stack = ctypes.c_int * (1024 * 1024)
    # pointer = ctypes.POINTER(stack)
    # print(dir(pointer.contents))
    # # pointer_value = ctypes.cast(pointer.contents, ctypes.c_void_p).value
    # res = c_dll.syscall(syscall_table['clone'], 1024, ns.CLONE_NEWNS) #, c_main_pointer, ns.CLONE_NEWNS)
    # print(res)
    # os.waitpid(res, 0)
    # # エラーの捕捉
    # print(ctypes.get_errno())
    # print(os.strerror(ctypes.get_errno()))


def test():
    import linux


if __name__ == "__main__":
    foo()