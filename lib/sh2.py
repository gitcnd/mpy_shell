# sh2.py

__version__ = '1.0.20240803'  # Major.Minor.Patch

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
    # t = time.monotonic() # circuitpython
    # print(shell.get_desc(41).format( int(t // 3600), int((t % 3600) // 60), int(t % 60)  )) # f"Uptime: {int(t // 3600)} hours, {int((t % 3600) // 60)} minutes, {int(t % 60)} seconds") # 39 bytes

    # linux:
    # 00:07:59 up 1 day,  9:38,  0 users,  load average: 0.52, 0.58, 0.59


    import time
    uptime_us = time.ticks_us()
    # Convert microseconds to milliseconds, seconds, etc.
    uptime_ms = uptime_us // 1000
    uptime_seconds = uptime_ms // 1000
    uptime_minutes = uptime_seconds // 60
    uptime_hours = uptime_minutes // 60
    uptime_days = uptime_hours // 24
    
    # Print the uptime in a readable format
    print(shell.get_desc(41).format( uptime_days, uptime_hours % 24, uptime_minutes % 60, uptime_seconds % 60)) # Uptime: {} days, {} hours, {} minutes, {} seconds  f"Uptime: {uptime_days} days, {uptime_hours % 24} hours, {uptime_minutes % 60} minutes, {uptime_seconds % 60} seconds"


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


def set_time(shell, cmdenv):
    print(f"current: {time.gmtime()}")
    shell.cio.set_time(shell)  # set the time if possible and not already set
    print(f"now: {time.gmtime()}")


def curl(shell, cmdenv):
    import socket,os
    gc.collect()
    time_reset=None
    if len(cmdenv['args']) < 2:
        print(shell.get_desc(37)) # usage: curl [-I] [-O] [-i] [-s] [-q] [--data=data] [--file=/path/uploadfile.txt] [--output=outfile] [--user=username:password] <url>
        return

    url = cmdenv['args'][-1]
    method = "GET"
    headers = {"Host": "", "Connection": "close"}
    data = None
    upfile = None
    wb, status = None, None
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
    if cmdenv['sw'].get('file'):
        upfile = cmdenv['sw']['file']
        try:
            fstat=os.stat(upfile)
        except Exception as e:
            print(shell.get_desc(10).format(cmdenv['args'][0],e)) # {}: {}
            return
        method = "POST"
        headers["Content-Type"] = "application/octet-stream"
        headers["Content-Disposition"] = f"attachment; filename={upfile}"
        headers["Content-Length"] = str(fstat[6])
        mtime = time.gmtime(fstat[7])
        headers["modified"] = f"{mtime[0]}-{mtime[1]:02}-{mtime[2]:02}T{mtime[3]:02}:{mtime[4]:02}:{mtime[5]:02}Z"  # "modified": "2023-08-07T13:45:00Z"
    if cmdenv['sw'].get('user'):
        import ubinascii
        headers["Authorization"] = "Basic " + ubinascii.b2a_base64(cmdenv['sw'].get('user').encode('utf-8')).decode('utf-8').strip()


    # Parse the URL
    protocol, host, port, path = _parse_url(url)
    headers["Host"] = host

    if 1: #try:
        # Create a socket and connect
        #print(f"looking up host {host} port {port}")
        addr_info = socket.getaddrinfo(host, port)[0]
        addr = addr_info[4]
        sock = socket.socket(addr_info[0], addr_info[1], addr_info[2])
        sock.connect(addr)

        # Wrap socket with SSL if using HTTPS
        if protocol == 'https':
            import ssl
            print(f"this might lock uip... new micropython bug? host={host}")
            sock = ssl.wrap_socket(sock, server_hostname=host) # this locks up?
            print("worked")

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

        # Send file if --file=
        if upfile:
            with open(upfile, 'rb') as file:
                while True:
                    request = file.read(1024)
                    if not request:
                        break
                    sock.write(request)
            print(shell.get_desc(83).format(fstat[6],upfile,url)) # $GRN Wrote {}b from {} to {} $NORM

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

    
        if ofn is not None: # get the file date
            dstart = headers.find(b"Last-Modified:") # Last-Modified: Thu, 01 Aug 2024 00:50:11 GMT
            if dstart != -1:
                import machine
                dend = headers.find(b'\r\n', dstart)
                if dend == -1: dend = len(headers)
                
                # Extract the file date string
                # print('Last-Modified:',headers[dstart + 14 :dend].strip().decode())
                _, day, month_str, year, time_str, _ = headers[dstart + 14 :dend].strip().decode().split()
                # print(f"day={day}, mo={month_str}, y={year}, time_str={time_str}")
                month_map = { 'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12 }
                hour, minute, sec = map(int, time_str.split(':'))
                # print(f"hour={hour}, minute={minute}, sec={sec}")
                file_time = (int(year), int(month_map[month_str]), int(day), 0, hour, minute, sec , 0)

                time_reset=[time.ticks_ms(), time.mktime(time.gmtime())] # moment we changed the clock
                # print(f"ft={file_time}, now={time_reset[1]}")
                machine.RTC().datetime(file_time) # temp set the time to the date on the incoming file
                # print(f"set={time.gmtime()}")



        if include_headers and 'q' not in cmdenv['sw']:
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
                if 'q' not in cmdenv['sw']:
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
            if 'q' not in cmdenv['sw']:
                shell.fprint(body, fn=ofn, end=b'')

            # Read and print the remaining non-chunked data
            while True:
                chunk = sock.read(1024)
                if not chunk:
                    break
                #shell.fprint(chunk.decode('utf-8'), fn=ofn, end='')
                if 'q' not in cmdenv['sw']:
                    shell.fprint(chunk, fn=ofn, end=b'')


        # Close the socket
        sock.close()
        wb=0
        if 'q' not in cmdenv['sw']:
            wb=shell.fprint(None,fn=ofn) # close output file

        if ofn is not None and 's' not in cmdenv['sw']:
            print(shell.get_desc(40).format(wb,ofn,url)) # "Wrote {wb}b to {ofn} from {url}")

    #except Exception as e:
    #    print(shell.get_desc(39).format(url,host,port,e) ) # "Error fetching {url} from {host}:{port}: {e}") # 31 bytes less

    if time_reset is not None:
        #print(f"rbefore={time.gmtime()}")

        diff_ms = time.ticks_diff(time.ticks_ms(), time_reset[0])
        seconds = diff_ms // 1000
        microseconds = (diff_ms % 1000) * 1000
        machine.RTC().datetime( (lambda t: (t[0], t[1], t[2], 0, t[3], t[4], t[5], microseconds))(time.gmtime(time_reset[1] + seconds)) )

        #new_time=time_reset[1] + int((time.ticks_diff(time.ticks_ms(), time_reset[0])/1000)+0.5)
        #dif=int((time.ticks_diff(time.ticks_ms(), time_reset[0])/1000)+0.5) 
        #print(f"rnow={time_reset[1]} dif={dif}s")
        #machine.RTC().datetime(time.gmtime(time_reset[1] + dif )) # return time to close-to-correct now
        #machine.RTC().datetime(time.gmtime(time_reset[1] + int((time.ticks_diff(time.ticks_ms(), time_reset[0])/1000)+0.5) )) # return time to close-to-correct now
        #print(f"rset={time_reset[1]}")
        #print(f"rnow={time.gmtime()}")

    gc.collect()
    return status, wb, ofn # e.g. 200


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
        print(fn)
        cmdenv['args']=['curl',shell.get_desc(31+mpy)+fn] # https://raw.githubusercontent.com/gitcnd/mpy_shell/main  - see also (32)
        cmdenv['sw']['output']=fn
        curl(shell, cmdenv)
    print(shell.get_desc(38)) # re-run import shell to re-start the updated shell
    del sys.modules["sh"] # so we can re-run us later
    raise OSError( shell.get_desc(38) )



def backup(shell, cmdenv):
    import os

    def bsend(fn,url):
        cmdenv['args']=['curl',url ] # shell.get_desc(31+mpy)+fn] # https://raw.githubusercontent.com/gitcnd/mpy_shell/main  - see also (32)
        cmdenv['sw']['file']=fn
        cmdenv['sw']['q']=True
        curl(shell, cmdenv)

    def spider(path,url):
        for entry in os.listdir(path):
            full_path = path + "/" + entry if path != "/" else "/" + entry # full_path = os.path.join(path, entry)
            if os.stat(full_path)[0] & 0x4000: # if os.path.isdir(full_path):
                spider(full_path,url)
            else:
                bsend(full_path,url)

    spider("/","http://172.22.1.66/carnet/up.asp?root=" + shell._rw_toml('r',"HOSTNAME"))





#def termtitle(shell, cmdenv):
#    if len(cmdenv['args']) < 2:
#        shell._ea(cmdenv)  # print("cat: missing file operand")
#    else:
#        print(f"\033]20;\007\033]0;{cmdenv['args'][1]}\007", end='')  # get current title, then set a new title: does nothing

