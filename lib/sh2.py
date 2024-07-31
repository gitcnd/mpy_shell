# sh2.py

__version__ = '1.0.20240626'  # Major.Minor.Patch

# Created by Chris Drake.
# Linux-like shell interface for CircuitPython.  https://github.com/gitcnd/cpy_shell
# 
# This is a separate module for holding some commands.
# it is separate to save RAM

import gc
import time
#import wifi
#import ipaddress
#import socketpool



def wc(shell, cmdenv): # 249 bytes
    if len(cmdenv['args']) < 2:
        shell._ea(cmdenv)  # print("wc: missing file operand")
    else:
        path = cmdenv['args'][1]
        try:
            with open(path, 'rb') as file:
                lines = 0
                words = 0
                bytes_count = 0
                while True:
                    chunk = file.read(512)
                    if not chunk:
                        break
                    lines += chunk.count(b'\n')
                    words += len(chunk.split())
                    bytes_count += len(chunk)
                print(f"{lines} {words} {bytes_count} {path}")
        except Exception as e:
            shell._ee(cmdenv, e)  # print(f"wc: {e}")



def history(shell, cmdenv):
    try:
        with open("/.history.txt", "r") as file:
            for index, line in enumerate(file, start=1):
                parts = line.strip().split("\t")
                if len(parts) < 2:
                    continue
                #date_time = time.localtime(int(parts[0]))
                mtime = time.localtime(int(parts[0]))
                print(f"{index}\t{mtime[0]}-{mtime[1]:02}-{mtime[2]:02} {mtime[3]:02}:{mtime[4]:02}.{mtime[5]:02}\t{parts[1]}")
                #print(f"{index}\t{date_time.tm_year}-{date_time.tm_mon:02}-{date_time.tm_mday:02} {date_time.tm_hour:02}:{date_time.tm_min:02}.{date_time.tm_sec:02}\t{parts[1]}")

    except Exception as e:
        print(f"Error reading history: {e}")


#"""
#
#def _show_mdns():
#    import wifi
#    import mdns
#
#    # Create an mDNS server instance
#    mdns_server = mdns.Server(wifi.radio)
#    
#    # Retrieve the hostname
#    mdns_name = mdns_server.hostname
#
#    # Print the mDNS hostname
#    print(f"mDNS Hostname: {mdns_name}")
#
#    # Find services advertised by this hostname
#    # services = mdns_server.find(service_type="_services._dns-sd._udp", protocol="_udp", timeout=1.0)
#    services = mdns_server.find(service_type="_http", protocol="_tcp", timeout=1.0)
#    #services = mdns_server.find(service_type="", protocol="", timeout=1.0) # rats. nothing.
#
#
#    # Print the found services
#    if services:
#        for service in services:
#            if service.hostname == mdns_name:
#                print(f"### US ###")
#            print(f"Service: {service.instance_name}")
#            print(f"  Hostname: {service.hostname}")
#            print(f"  Address: {service.ipv4_address}")
#            print(f"  Port: {service.port}")
#            print(f"  Type: {service.service_type}")
#            print(f"  Protocol: {service.protocol}")
#    else:
#        print("No mDNS services found")
#
#"""

def ifconfig(shell, cmdenv):
    import network
    import binascii

    # Initialize network interface
    n=('AP_IF','STA_IF')
    for i,lan in enumerate((network.AP_IF, network.STA_IF)):
        wlan = network.WLAN(lan) # network.STA_IF
        #wlan.active(True)

        # Get network interface details
        ip4_address, netmask, gateway, dns = wlan.ifconfig()
        mac_address = binascii.hexlify(wlan.config('mac'), ':').decode()
        try:
            hostname = wlan.config('hostname')
        except:
            hostname = None
        try:
            tx_power = wlan.config('txpower')
        except:
            tx_power = None

        # Print network interface details
        print(f"{n[i]}: inet {ip4_address}  netmask {netmask}  gateway {gateway}")
        print(f"\tether {mac_address}  (Ethernet)")
        print(f"\tHostname: {hostname}")
        print(f"\tDNS: {dns}")
        print(f"\tTX power: {tx_power} dBm")

        try:
            ap_info = wlan.status('rssi')
        except:
            ap_info = None
        if ap_info:
            print(f"\tSSID: {wlan.config('essid')}")
            print("\tBSSID: {}".format(mac_address))  # placeholder, needs actual BSSID
            print(f"\tChannel: {wlan.config('channel')}")
            #print(f"\tCountry: {wlan.config('country')}")
            print(f"\tRSSI: {ap_info}")
            #print(dir(wlan)) # mpy=['__class__', 'IF_AP', 'IF_STA', 'PM_NONE', 'PM_PERFORMANCE', 'PM_POWERSAVE', 'SEC_OPEN', 'SEC_OWE', 'SEC_WAPI', 'SEC_WEP', 'SEC_WPA', 'SEC_WPA2', 'SEC_WPA2_ENT', 'SEC_WPA2_WPA3', 'SEC_WPA3', 'SEC_WPA_WPA2', 'active', 'config', 'connect', 'disconnect', 'ifconfig', 'ipconfig', 'isconnected', 'scan', 'status']

        #_show_mdns()
        #del sys.modules["mdns"] # done. save space now.


def date(shell, cmdenv):
    now(shell, cmdenv)
    #date_time = time.localtime()
    #print( shell.get_desc(42).format( date_time.tm_year,date_time.tm_mon,date_time.tm_mday,date_time.tm_hour,date_time.tm_min,date_time.tm_sec ) ) # f"{date_time.tm_year}-{date_time.tm_mon:02}-{date_time.tm_mday:02} {date_time.tm_hour:02}:{date_time.tm_min:02}.{date_time.tm_sec:02}")
    #print( shell.get_desc(42).format(*time.localtime()[:6]))


def now(shell, cmdenv):
    if time.localtime()[0]<2024:
        #cio=shell.cio
        #cio.set_time()  # set the time if possible and not already set
        shell.cio.set_time(shell)  # set the time if possible and not already set
    #ret="{:04}-{:02}-{:02} {:02}:{:02}:{:02}".format(*time.localtime()[:6])
    ret=shell.get_desc(42).format(*time.localtime()[:6])
    if not cmdenv['sw'].get('op', False): print(ret)
    return ret


def sleep(shell, cmdenv): # not working
    if len(cmdenv['args']) < 2:
        shell._ea(cmdenv)
        return
    time.sleep(float(cmdenv['args'][1]))


def _sleep(shell, cmdenv): # not working
    if len(cmdenv['args']) < 2:
        shell._ea(cmdenv)
        return

    import alarm
    import microcontroller

    print("Entering deep sleep...")

    # Configure an alarm to wake up after specified period in seconds
    time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + int(cmdenv['args'][1]))

    # Exit the running code and enter deep sleep until the alarm wakes the device
    alarm.exit_and_deep_sleep_until_alarms(time_alarm)


def uptime(shell, cmdenv):
    t = time.monotonic()
    print(shell.get_desc(41).format( int(t // 3600), int((t % 3600) // 60), int(t % 60)  )) # f"Uptime: {int(t // 3600)} hours, {int((t % 3600) // 60)} minutes, {int(t % 60)} seconds") # 39 bytes


def _parse_url(url):
    if "://" not in url:
        url = "http://" + url
    protocol, _, host_path = url.partition("://")
    if "/" in host_path:
        host, path = host_path.split("/", 1)
        path = "/" + path
    else:
        host = host_path
        path = "/"
    
    if ":" in host:
        host, port = host.split(":")
        port = int(port)
    else:
        port = 80 if protocol == "http" else 443

    return protocol, host, port, path



def curl(shell, cmdenv):
    import ssl
    import socket
    gc.collect()
    if len(cmdenv['args']) < 2:
        print(shell.get_desc(37)) # "usage: curl [-I] [-O] [-i] [--data=data] [--output=outfile] <url>"
        return

    import ssl
    url = cmdenv['args'][-1]
    method = "GET"
    headers = {"Host": "", "Connection": "close"}
    data = None
    include_headers = cmdenv['sw'].get('i', False)

    ofn=cmdenv['sw'].get('output') if 'output' in cmdenv['sw'] else url.split('/')[-1] if 'O'  in cmdenv['sw'] else None

    # Parse command line arguments
    if cmdenv['sw'].get('I'):
        method = "HEAD"
        include_headers = True
    if cmdenv['sw'].get('data'):
        data = cmdenv['sw']['data']
        method = "POST"
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Content-Length"] = str(len(data))
    if cmdenv['sw'].get('user'):
        import ubinascii
        headers["Authorization"] = "Basic " + ubinascii.b2a_base64(cmdenv['sw'].get('user').encode('utf-8')).decode('utf-8').strip()


    # Parse the URL
    protocol, host, port, path = _parse_url(url)
    headers["Host"] = host

    try:
        # Create a socket and connect
        #print(f"looking up host {host} port {port}")
        addr_info = socket.getaddrinfo(host, port)[0]
        addr = addr_info[4]
        sock = socket.socket(addr_info[0], addr_info[1], addr_info[2])
        sock.connect(addr)

        # Wrap socket with SSL if using HTTPS
        if protocol == 'https':
            sock = ssl.wrap_socket(sock, server_hostname=host)

#        """ # Create a socket pool
#        pool = socketpool.SocketPool(wifi.radio)
#
#        # Create a socket and connect
#        addr_info = pool.getaddrinfo(host, port)[0]
#        addr = addr_info[4]
#        sock = pool.socket(addr_info[0], addr_info[1], addr_info[2])
#        sock.connect(addr)
#
#        # Wrap socket with SSL if using HTTPS
#        if protocol == 'https':
#            context = ssl.create_default_context()
#            sock = context.wrap_socket(sock, server_hostname=host)
#        """

        # Construct the HTTP request
        request_lines = [f"{method} {path} HTTP/1.1"]
        request_lines.extend(f"{header}: {value}" for header, value in headers.items())
        request_lines.append("")  # End of headers
        request_lines.append(data if data else "")  # Data for POST
        request = "\r\n".join(request_lines) + "\r\n"

        # Send HTTP request
        sock.write(request.encode('utf-8'))

        # Receive and print response headers
        body = b""

        while True:
            chunk = sock.read(1024)
            if not chunk:
                break
            body += chunk
            if b'\r\n\r\n' in body:
                break

        header_end = body.find(b'\r\n\r\n')
        headers = body[:header_end]
        body = body[header_end+4:]
        status=0
        try:
            status=int(headers.split(None,2)[1].decode('utf-8'))
        except:
            pass


        #headers, body= response.split(b'\r\n\r\n', 1)

        if include_headers:
            shell.fprint(headers,fn=ofn)
            shell.fprint(b'',fn=ofn)


        # Check for chunked transfer encoding
        if b"Transfer-Encoding: chunked" in headers:
            # Process the initial part of the body
            while body:
                length_str, body = body.split(b'\r\n', 1)
                chunk_length = int(length_str.decode('utf-8'), 16)
                if chunk_length == 0:
                    break

                # Ensure we have enough data to read the entire chunk
                while len(body) < chunk_length:

                    chunk = sock.read(1024)
                    if not chunk:
                        break
                    body += chunk

                # Print the chunk data
                chunk_data = body[:chunk_length] # .decode('utf-8')
                shell.fprint(chunk_data, fn=ofn, end=b'')

                # Move to the next chunk, skipping the trailing \r\n
                body = body[chunk_length + 2:]

                # If body is empty, read more data
                if not body:
                    chunk = sock.read(1024)
                    if not chunk:
                        break
                    body += chunk

        else:
            # Print the initial part of the body
            #shell.fprint(body.decode('utf-8'), fn=ofn, end=b'')
            shell.fprint(body, fn=ofn, end=b'')

            # Read and print the remaining non-chunked data
            while True:
                chunk = sock.read(1024)
                if not chunk:
                    break
                #shell.fprint(chunk.decode('utf-8'), fn=ofn, end='')
                shell.fprint(chunk, fn=ofn, end=b'')


        # Close the socket
        sock.close()
        wb=shell.fprint(None,fn=ofn) # close output file
        if ofn is not None:
            print(shell.get_desc(40).format(wb,ofn,url)) # "Wrote {wb}b to {ofn} from {url}")

    except Exception as e:
        print(shell.get_desc(39).format(url,host,port,e) ) # "Error fetching {url} from {host}:{port}: {e}") # 31 bytes less

    return status # e.g. 200


def wget(shell, cmdenv):
    return curl(shell, cmdenv)



def telnetd(shell, cmdenv): # usage: telnetd --port=23
    shell.cio.telnetd(shell,cmdenv['sw'].get('port', 23)) # tell our shell to open up the listening socket

   

def _termtype(shell, cmdenv): # +50, -58 bytes
    print("\033[c\033[>0c", end='')  # get type and extended type of terminal. responds with: 1b 5b 3f 36 32 3b 31 3b 32 3b 36 3b 37 3b 38 3b 39 63    1b 5b 3e 31 3b 31 30 3b 30 63
    #                                                                                         \033[?62;1;2;6;7;8;9c (Device Attributes DA)             \033[>1;10;0c (Secondary Device AttributesA)
    # 62: VT220 terminal.  1: Normal cursor keys.  2: ANSI terminal.  6: Selective erase.  7: Auto-wrap mode.  8: XON/XOFF flow control.  9: Enable line wrapping.
    # 1: VT100 terminal.  10: Firmware version 1.0.  0: No additional information.

def _scrsize(shell, cmdenv): # 70 bytes
    print("\033[s\0337\033[999C\033[999B\033[6n\r\033[u\0338", end='')  # ANSI escape code to save cursor position, move to lower-right, get cursor position, then restore cursor position: responds with \x1b[130;270R
    #ng: print("\033[18t", end='')  # get screen size: does nothing

def shupdate(shell, cmdenv):
    import os
    import sys
    mpy = 1 if 'sh.mpy' in os.listdir('/lib') else 0
    for fn in shell.get_desc(33+mpy).split(' '): # /lib/sh.py /lib/sh0.py /lib/sh1.py /lib/sh2.py - see also (34)
        cmdenv['args']=['curl',shell.get_desc(31+mpy)+fn] # https://raw.githubusercontent.com/gitcnd/mpy_shell/main  - see also (32)
        cmdenv['sw']['output']=fn
        curl(shell, cmdenv)
    print(shell.get_desc(38)) # re-run import shell to re-start the updated shell
    del sys.modules["sh"] # so we can re-run us later
    raise OSError( shell.get_desc(38) )



#def termtitle(shell, cmdenv):
#    if len(cmdenv['args']) < 2:
#        shell._ea(cmdenv)  # print("cat: missing file operand")
#    else:
#        print(f"\033]20;\007\033]0;{cmdenv['args'][1]}\007", end='')  # get current title, then set a new title: does nothing

