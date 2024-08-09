# sh0.py

__version__ = '1.0.20240802'  # Major.Minor.Patch

# Created by Chris Drake.
# Linux-like shell interface for CircuitPython.  https://github.com/gitcnd/cpy_shell
# 
# This is a separate module for holding some commands.
# it is separate to save RAM

import os
import time


#print(self.get_desc(4).format(e)) # Socket send exception: {}
def _bare(f):
    if f.endswith('/') and len(f) > 1:
        f = f.rstrip('/')
    return f


def _file_exists(filepath):
    try:
        os.stat(filepath)
        return True
    except OSError:
        return False


def _human_size(size): # 137b
    # Convert bytes to human-readable format
    for unit in ['B', 'K', 'M', 'G', 'T']:
        if size < 1024:
            return f"{round(size):,}{unit}"
        size /= 1024
    return f"{round(size):,}P"  # Handle very large sizes as petabytes


def df(shell, cmdenv): # 148 bytes - caution: _human_size
    try:
        fs_stat = os.statvfs('/')
        block_size = fs_stat[0]
        total_blocks = fs_stat[2]
        free_blocks = fs_stat[3]
        total_size = total_blocks * block_size
        free_size = free_blocks * block_size
        used_size = total_size - free_size
        print(shell.get_desc(80).format(_human_size(total_size), _human_size(used_size), _human_size(free_size)))
    except OSError as e:
        shell._ee(cmdenv,e) # print(f"{}: {e}")


def ls(shell,cmdenv):   # impliments -F -l -a -t -r -S -h - caution _human_size
    args=cmdenv['args']
    tsort=[]

    def list_items(items):
        for f in sorted(items, reverse=bool(cmdenv['sw'].get('r'))):
            if (f.startswith('.') or ("/." in f and '/' not in f.split("/.")[-1])) and not cmdenv['sw'].get('a'): continue
            #print(f"f={f}")
            if not _file_exists(f):
                print(shell.get_desc(12).format(cmdenv['args'][0], f))  # ls: cannot access 'sdf': No such file or directory
                continue
            pt = os.stat(f)
            #mtime = time.localtime(pt[7])
            mtime = time.gmtime(pt[7])
            #mtime_str = f"{mtime.tm_year}-{mtime.tm_mon:02}-{mtime.tm_mday:02} {mtime.tm_hour:02}:{mtime.tm_min:02}.{mtime.tm_sec:02}"
            #mtime[0]-=30
            mtime_str = f"{mtime[0]}-{mtime[1]:02}-{mtime[2]:02} {mtime[3]:02}:{mtime[4]:02}:{mtime[5]:02}"

            tag = "/" if cmdenv['sw'].get('F') and pt[0] & 0x4000 else ""
            sz=pt[6]
            if pt[0] & 0x4000 and ( pt[6]<1 or pt[6]>1000000000):
                sz=4096 # some filesystem report 1,073,572,116 for folders
            fsize = _human_size(sz) if cmdenv['sw'].get('h') else sz
            ret=f"{fsize:,}\t{mtime_str}\t{f}{tag}" if cmdenv['sw'].get('l') else f"{f}{tag}"
            if cmdenv['sw'].get('t'):
                tsort.append((pt[7], ret))
            elif cmdenv['sw'].get('S'):
                tsort.append((sz, ret))
            elif cmdenv['sw'].get('s'):
                tsort.append((-sz, ret))
            else:
                print(ret)

    for path in cmdenv['args'][1:] if len(cmdenv['args']) > 1 else [os.getcwd()]:
 
        path=_bare(path) # cannot stat("foo/")
        try:
            fstat = os.stat(path)
            if fstat[0] & 0x4000:  # Check for directory bit
                if path.endswith("/"):
                    path = path[:-1]
                path_pre = f"{path}/" if path else ""
    
                list_items([f"{path_pre}{filename}" for filename in os.listdir(path)])
            else:
                list_items([path])
        except OSError:
            print(f"{path} Not found")  # Handle non-existent paths

    if cmdenv['sw'].get('t') or cmdenv['sw'].get('S') or cmdenv['sw'].get('s'):
        for _, ret in sorted(tsort, reverse=not bool(cmdenv['sw'].get('r'))):
            print(ret)


def cd(shell, cmdenv):
    if len(cmdenv['args']) < 2:
        shell._ea(cmdenv) # print(self.get_desc(9).format(cmdenv['args'][0])) # {}: missing operand(s)
    else:
        try:
            os.chdir(cmdenv['args'][1])
        except OSError as e:
            shell._ee(cmdenv, e) # print(f"cd: {e}")


def _cp(src, tgt):
    try:
        with open(src, 'rb') as src_file:
                with open(tgt, 'wb') as dest_file:  # OSError: [Errno 30] Read-only filesystem
                    dest_file.write(src_file.read())
    except OSError as e:
        shell._ee(cmdenv, e)  # print(f"mv: {e}")


def _confirm_overwrite(shell, filename):
    response = input(f"{filename} exists. Overwrite? (y/n): ")
    return response.lower() == 'y'

def mv(shell, cmdenv):
    #print("cmdenv", cmdenv)
    cmd = cmdenv['args'][0]
    interactive = cmdenv['sw'].get('i', False)
    if len(cmdenv['args']) < 3:
        shell._ea(cmdenv)  # print("mv: missing file operand")
    else:
        target = cmdenv['args'][-1]
        try:
            fstat = os.stat(target)
        except OSError:
            fstat = [0xFCD]
        if fstat[0] & 0x4000:
            if target.endswith("/"):
                target = target[:-1]
            for path in cmdenv['args'][1:-1]:
                dest = target + '/' + path
                if interactive and _file_exists(dest):
                    if not _confirm_overwrite(shell, dest):
                        continue
                if cmd == 'cp':
                    _cp(path, dest)
                else:
                    os.rename(path, dest)
        else:
            if len(cmdenv['args']) == 3:
                path = cmdenv['args'][1]
                try:
                    if interactive and _file_exists(target):
                        if not _confirm_overwrite(shell, target):
                            return
                    if cmd == 'cp':
                        _cp(path, target)
                    else:  # mv
                        if not fstat[0] == 0xFCD:
                            os.remove(target)
                        os.rename(path, target)
                except OSError as e:
                    shell._ee(cmdenv, e)  # print(f"mv: {e}")
            else:
                print(shell.get_desc(11).format(cmd, target))  # {}: target '{}' is not a directory

def cp(shell, cmdenv):
    mv(shell, cmdenv)  # mv knows to do a cp if that was the command.


def rm(shell, cmdenv):
    if len(cmdenv['args']) < 2:
        shell._ea(cmdenv) # print("rm: missing file operand")
    else:
        for path in cmdenv['args'][1:]:
            try:
                if os.stat(path)[0] & 0x4000:  # Check if it's a directory
                    os.rmdir(path)
                else:
                    os.remove(path)
            except OSError as e:
                shell._ee(cmdenv,e) # print(f"rm: {e}")


def mkdir(shell, cmdenv):
    if len(cmdenv['args']) < 2:
        shell._ea(cmdenv) # print("mkdir: missing file operand")
    else:
        for path in cmdenv['args'][1:]:
            try:
                if cmdenv['args'][0] == 'rmdir':
                    os.rmdir(path)
                else:
                    os.mkdir(path)
            except OSError as e:
                shell._ee(cmdenv,e) # print(f"{}: {e}")


def rmdir(shell, cmdenv):
    mkdir(shell, cmdenv)



def sort(shell,cmdenv):  # 53 bytes
    return "\n".join(sorted(cmdenv['args'][1:], reverse='-r' in cmdenv['sw']))


def pwd(shell, cmdenv):
    print(os.getcwd())


""" Not working in micropython

def ping(shell, cmdenv):
    import ipaddress
    import socketpool
    import wifi
    if len(cmdenv['args']) < 2:
        #print("usage: ping <address>")
        print(shell.get_desc(14)) # usage: ping <address>
        return

    dom = cmdenv['args'][1]

    pool = socketpool.SocketPool(wifi.radio)

    try:
        addr_info = pool.getaddrinfo(dom, 80)  # Using port 80 for HTTP
        ip = addr_info[0][4][0]
        ip1 = ipaddress.ip_address(ip)
    except Exception as e:
        #print(f'Error getting IP address: {e}') # saves 21 bytes
        print(shell.get_desc(15).format(e)) # Error getting IP address: {e}
        return

    #print(f"PING {dom} ({ip}) 56(84) bytes of data.")
    print(shell.get_desc(16).format(dom,ip)) # PING {dom} ({ip}) 56(84) bytes of data.
    
    packet_count = 4
    transmitted = 0
    received = 0
    total_time = 0
    times = []

    for seq in range(1, packet_count + 1):
        transmitted += 1
        start_time = time.monotonic()
        
        result = wifi.radio.ping(ip1)
        rtt = (time.monotonic() - start_time) * 1000  # Convert to milliseconds
        total_time += rtt
        
        if result is not None:
            received += 1
            times.append(rtt)
            print(f"64 bytes from {ip}: icmp_seq={seq} time={rtt:.1f} ms")
        else:
            #print(f"Request timeout for icmp_seq {seq}")
            print(shell.get_desc(17).format(seq)) # Request timeout for icmp_seq {seq}
        
        if rtt<1000 and seq<packet_count:
            time.sleep((1000-rtt)/1000)

    #print(f"--- {ip} ping statistics ---\n{transmitted} packets transmitted, {received} received, {((transmitted - received) / transmitted) * 100:.0f}% packet loss, time {total_time:.0f}ms")
    print(shell.get_desc(18).format(ip,transmitted,received,((transmitted - received) / transmitted) * 100,total_time)) # --- {ip} ping statistics ---\n{transmitted} packets transmitted, {received} received, {((transmitted - received) / transmitted) * 100:.0f}% packet loss, time {total_time:.0f}ms

    if times:
        min_time = min(times)
        avg_time = sum(times) / len(times)
        max_time = max(times)
        mdev_time = (sum((x - avg_time) ** 2 for x in times) / len(times)) ** 0.5
        #print(f"rtt min/avg/max/mdev = {min_time:.3f}/{avg_time:.3f}/{max_time:.3f}/{mdev_time:.3f} ms")
        print(shell.get_desc(19).format(min_time,avg_time,max_time,mdev_time)) # rtt min/avg/max/mdev = {min_time:.3f}/{avg_time:.3f}/{max_time:.3f}/{mdev_time:.3f} ms

"""

def clear(shell, cmdenv):
    print("\033[2J\033[H", end='')  # ANSI escape codes to clear screen


def cls(shell, cmdenv):
    print("\033[2J", end='')  # ANSI escape code to clear screen


def setpin(shell, cmdenv):
    import machine
    if not 'pin' in cmdenv['sw'] or not 'value' in cmdenv['sw']:
        print(shell.get_desc(29)) # "usage: {} --pin=<pin_number> --value=<0 or 1>".format(cmdenv['args'][0]))
    else:
        try:
            #print(f"setting {cmdenv['sw']['pin']} to {cmdenv['sw']['value']}")
            led = machine.Pin(int(cmdenv['sw']['pin']), machine.Pin.OUT)
            led.value(int(cmdenv['sw']['value']))
        except Exception as e:
            print(shell.get_desc(10).format(cmdenv['args'][0],e)) # {}: {}

def pwm(shell, cmdenv): # was 4044 bytes
    import machine
    if not 'pin' in cmdenv['sw'] or not 'duty' in cmdenv['sw'] or not 'freq' in cmdenv['sw']:
        print(shell.get_desc(28)) # .format(cmdenv['args'][0])) # usage: {} --pin=<pin_number> --duty=<0 to 65535> --freq=<integer number> [--loop=<n> --ondelay=<seconds> --offdelay=<seconds> --voff=<duty cyle for off>]
    else:
        try:
            pwm = machine.PWM(int(cmdenv['sw']['pin']), freq=int(cmdenv['sw']['freq']), duty_u16=int(cmdenv['sw']['duty']))    # create a PWM object on a pin and set freq and duty
            # pwm.duty_u16(32768)            # set duty to 50%
            # pwm.init(freq=5000, duty_ns=5000)    # reinitialise with a period of 200us, duty of 5us
            # pwm.duty_ns(3000)            # set pulse width to 3us
            if 'loop' in cmdenv['sw']:
                ondelay=float(cmdenv['sw']['ondelay']) if 'ondelay' in cmdenv['sw'] else 0.5
                offdelay=float(cmdenv['sw']['offdelay']) if 'offdelay' in cmdenv['sw'] else 0.5
                voff=int(cmdenv['sw']['voff']) if 'voff' in cmdenv['sw'] else 0 if int(cmdenv['sw']['duty']) > 32767 else 65535
                num=int(cmdenv['sw']['loop'])
                while num>0:
                    pwm.duty_u16(int(cmdenv['sw']['duty']))
                    time.sleep(ondelay)
                    pwm.duty_u16(voff)
                    time.sleep(offdelay)
                    num=num-1
                pwm.deinit()
        except Exception as e:
            shell._ee(cmdenv, e)  # print(f"{}: {e}") # ValueError: invalid pin

def getpin(shell, cmdenv):
    import machine
    if not 'pin' in cmdenv['sw']:
        print(shell.get_desc(30)) # usage: getpin --pin=<pin_number> [--pullup=1]
    else:
        if 'pullup' in cmdenv['sw']:
            led = machine.Pin(int(cmdenv['sw']['pin']), machine.Pin.IN, machine.Pin.PULL_UP)
        elif 'pulldown' in cmdenv['sw']:
            led = machine.Pin(int(cmdenv['sw']['pin']), machine.Pin.IN, machine.Pin.PULL_DOWN)
        else:
            led = machine.Pin(int(cmdenv['sw']['pin']), machine.Pin.IN)
        print("pin {} is {}".format(cmdenv['sw']['pin'], led.value()))

