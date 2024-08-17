# sh2.py

__version__ = '1.0.20240809'  # Major.Minor.Patch

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


def _tpad(mtime): # convert from file times into esp32 setting time format
    return(int(mtime[0]), int(mtime[1]), int(mtime[2]), 0, int(mtime[3]), int(mtime[4]), int(mtime[5]), 0)

def _ftime(shell, fn, sw):
    import os
    try:
        fstat=os.stat(fn)
    except Exception as e:
        print(shell.get_desc(10).format(fn,e)) # {}: {}
        return ''
    mtime = time.gmtime(fstat[7])
    if sw:
        return(_tpad(mtime)) # file_time = (int(year), int(month_map[month_str]), int(day), 0, hour, minute, sec , 0)
    else:
        return f"{mtime[0]}-{mtime[1]:02}-{mtime[2]:02}T{mtime[3]:02}:{mtime[4]:02}:{mtime[5]:02}Z"  # "2023-08-07T13:45:00Z"

def _reset_time(time_reset, reset):
    import machine
    if reset: # fix our clock which was temporarily changed earlier
        diff_ms = time.ticks_diff(time.ticks_ms(), time_reset[0])
        #seconds = diff_ms // 1000
        #microseconds = (diff_ms % 1000) * 1000
        #print("time_reset", time_reset)
        machine.RTC().datetime( (lambda t: (t[0], t[1], t[2], 0, t[3], t[4], t[5], (diff_ms % 1000) * 1000))(time.gmtime(time_reset[1] + diff_ms // 1000)) )
        #new_time=time_reset[1] + int((time.ticks_diff(time.ticks_ms(), time_reset[0])/1000)+0.5)
        #dif=int((time.ticks_diff(time.ticks_ms(), time_reset[0])/1000)+0.5) 
        #print(f"rnow={time_reset[1]} dif={dif}s")
        #machine.RTC().datetime(time.gmtime(time_reset[1] + dif )) # return time to close-to-correct now
        #machine.RTC().datetime(time.gmtime(time_reset[1] + int((time.ticks_diff(time.ticks_ms(), time_reset[0])/1000)+0.5) )) # return time to close-to-correct now
        #print(f"rset={time_reset[1]}")
        #print(f"rnow={time.gmtime()}")
    else:
        ret=[time.ticks_ms(), time.mktime(time.gmtime())] # moment we changed the clock
        #print("time_set", time_reset)
        machine.RTC().datetime(time_reset) # temp set the time to the date on the incoming file
        return ret


def touch(shell, cmdenv): # 225 bytes
    if len(cmdenv['args']) < 2:
        shell._ea(cmdenv) # print("touch: missing file operand")
    else:
        time_reset=None
        # path = cmdenv['args'][1]
        if 'reference' in cmdenv['sw']:
            time_reset=_reset_time( _ftime( shell, cmdenv['sw']['reference'],1), 0) # set clock to the time on the file
        elif 'date' in cmdenv['sw']:
            time_reset=_reset_time( _tpad( cmdenv['sw']['date'].split(',') ), 0) # set clock to the specified time
        for path in cmdenv['args'][1:]:
            try:
                try:
                    # Try to open the file in read-write binary mode
                    with open(path, 'r+b') as file:
                        first_char = file.read(1)
                        if first_char:
                            file.seek(0)
                            file.write(first_char)
                        else:
                            raise OSError(2, '') # 'No such file or directory')  # Simulate file not found to recreate it
                except OSError as e:
                    if e.args[0] == 2:  # Error code 2 corresponds to "No such file or directory"
                        with open(path, 'wb') as file:
                            pass  # Do nothing after creating the file
                    else:
                        raise e  # Re-raise the exception if it is not a "file not found" error
            except Exception as e:
                shell._ee(cmdenv, e)  # print(f"{}: {e}")
        if time_reset:
            _reset_time(time_reset,1) # reset clock


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
        fstat=os.stat(upfile)
        method = "POST"
        headers["Content-Type"] = "application/octet-stream"
        headers["Content-Disposition"] = f"attachment; filename={upfile}"
        headers["Content-Length"] = str(fstat[6])
        headers["modified"] = _ftime(shell, upfile,0) # f"{mtime[0]}-{mtime[1]:02}-{mtime[2]:02}T{mtime[3]:02}:{mtime[4]:02}:{mtime[5]:02}Z"  # "modified": "2023-08-07T13:45:00Z"
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
            print(f"might lockup (micropython bug)")
            sock = ssl.wrap_socket(sock, server_hostname=host) # this locks up?
            #print("worked")

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
        if data:
            request_lines.append(data)  # Data for POST
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
            if status != 200:
                print(headers.decode('utf-8'))
                return status, wb, ofn
            dstart = headers.find(b"Last-Modified:") # Last-Modified: Thu, 01 Aug 2024 00:50:11 GMT
            if dstart != -1:
                import machine
                dend = headers.find(b'\r\n', dstart)
                if dend == -1: dend = len(headers)
                
                # Extract the file date string
                # print('Last-Modified:',headers[dstart + 14 :dend].strip().decode())
                _, day, month_str, year, time_str, _ = headers[dstart + 14 :dend].strip().decode().split()
                month_map = { 'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12 }
                #hour, minute, sec = map(int, time_str.split(':'))
                #file_time = (int(year), int(month_map[month_str]), int(day), 0, hour, minute, sec , 0)
                #time_reset=_reset_time(file_time,0) # remember "now", then set the clock back to the date on the incoming file
                #t=[ year, month_map[month_str], day,  map(int, time_str.split(':') ) ]
                h, m, s = time_str.split(':')
                time_reset=_reset_time( _tpad([ year, month_map[month_str], day, h, m, s ])  ,0) # remember "now", then set the clock back to the date on the incoming file

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
                    if len(body) > 2048: # flush it out of RAM now
                        if 'q' not in cmdenv['sw']:
                            shell.fprint(body[:1024], fn=ofn, end=b'')
                            body=body[1024:]
                            chunk_length = chunk_length - 1024

                # Print the chunk data
                chunk_data = body[:chunk_length] # .decode('utf-8')   # This slice returns a new sequence containing the elements from the beginning of body up to (but not including) the index chunk_length.
                if 'q' not in cmdenv['sw']:
                    shell.fprint(chunk_data, fn=ofn, end=b'')

                # Move to the next chunk, skipping the trailing \r\n
                body = body[chunk_length + 2:]                        # This slice returns a new sequence starting from the index chunk_length + 2 to the end of body.

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
        _reset_time(time_reset,1)

    gc.collect()
    return status, wb, ofn # e.g. 200


def wget(shell, cmdenv):
    return curl(shell, cmdenv)


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
    burl=cmdenv['sw'].get('url', shell._rw_toml('r',["BACKUP_URL"],subst=True,default='')) + cmdenv['sw'].get('tag', '')
    if burl is None or burl=='':
        print(shell.get_desc(84)) # re-run import shell to re-start the updated shell
        return

    def bsend(fn,url):
        cmdenv['args']=['curl',url ] # shell.get_desc(31+mpy)+fn] # https://raw.githubusercontent.com/gitcnd/mpy_shell/main  - see also (32)
        cmdenv['sw']['file']=fn
        cmdenv['sw']['q']=True
        curl(shell, cmdenv)

    def do_or_send(path,url):
        if os.stat(path)[0] & 0x4000: # if os.path.isdir(full_path):
            spider(path,url)
        else:
            bsend(path,url)
   
    def spider(path,url):
        for entry in os.listdir(path):
            full_path = path + "/" + entry if path != "/" else "/" + entry # full_path = os.path.join(path, entry)
            do_or_send(full_path,url)

    for path in cmdenv['args'][1:] if len(cmdenv['args']) > 1 else [os.getcwd()]:
        do_or_send(path,burl)
        # spider("/",burl)



#def termtitle(shell, cmdenv):
#    if len(cmdenv['args']) < 2:
#        shell._ea(cmdenv)  # print("cat: missing file operand")
#    else:
#        print(f"\033]20;\007\033]0;{cmdenv['args'][1]}\007", end='')  # get current title, then set a new title: does nothing

