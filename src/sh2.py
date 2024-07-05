# sh2.py

__version__ = '1.0.20240626'  # Major.Minor.Patch

# Created by Chris Drake.
# Linux-like shell interface for CircuitPython.  https://github.com/gitcnd/cpy_shell
# 
# This is a separate module for holding some commands.
# it is separate to save RAM

import gc
import time
import wifi
#import ipaddress
import socketpool


def free(shell, cmdenv):
    try:
        gc.collect()
        total_memory = gc.mem_alloc() + gc.mem_free()
        free_memory = gc.mem_free()
        used_memory = gc.mem_alloc()
        print(f"Total Memory: {total_memory} bytes")
        print(f"Used Memory: {used_memory} bytes")
        print(f"Free Memory: {free_memory} bytes")
    except Exception as e:
        shell._ee(cmdenv, e)  # print(f"free: {e}")


def wc(shell, cmdenv):
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
                date_time = time.localtime(int(parts[0]))
                print(f"{index}\t{date_time.tm_year}-{date_time.tm_mon:02}-{date_time.tm_mday:02} {date_time.tm_hour:02}:{date_time.tm_min:02}.{date_time.tm_sec:02}\t{parts[1]}")

    except Exception as e:
        print(f"Error reading history: {e}")


def _show_mdns():
    import wifi
    import mdns

    # Create an mDNS server instance
    mdns_server = mdns.Server(wifi.radio)
    
    # Retrieve the hostname
    mdns_name = mdns_server.hostname

    # Print the mDNS hostname
    print(f"mDNS Hostname: {mdns_name}")

    # Find services advertised by this hostname
    # services = mdns_server.find(service_type="_services._dns-sd._udp", protocol="_udp", timeout=1.0)
    services = mdns_server.find(service_type="_http", protocol="_tcp", timeout=1.0)
    #services = mdns_server.find(service_type="", protocol="", timeout=1.0) # rats. nothing.


    # Print the found services
    if services:
        for service in services:
            if service.hostname == mdns_name:
                print(f"### US ###")
            print(f"Service: {service.instance_name}")
            print(f"  Hostname: {service.hostname}")
            print(f"  Address: {service.ipv4_address}")
            print(f"  Port: {service.port}")
            print(f"  Type: {service.service_type}")
            print(f"  Protocol: {service.protocol}")
    else:
        print("No mDNS services found")


def ifconfig(shell, cmdenv):
    import wifi
    import mdns

    # Get network interface details
    ip4_address = wifi.radio.ipv4_address
    netmask = wifi.radio.ipv4_subnet
    gateway = wifi.radio.ipv4_gateway
    mac_address = wifi.radio.mac_address
    hostname = wifi.radio.hostname
    dns = wifi.radio.ipv4_dns
    tx_power = wifi.radio.tx_power
    mdns_server = mdns.Server(wifi.radio)
    mdnshostname=mdns_server.hostname

    # Format MAC address
    mac_address_str = ':'.join(['{:02x}'.format(b) for b in mac_address])

    # Print network interface details
    print(f"wifi0: inet {ip4_address}  netmask {netmask}  gateway {gateway}")
    print(f"\tether {mac_address_str}  (Ethernet)")
    print(f"\tHostname: radio:{hostname} mDNS:{mdnshostname}")
    #if dns:
    print(f"\tDNS: {dns}")
    print(f"\tTX power: {tx_power} dBm")
    print(f"\tSSID: {wifi.radio.ap_info.ssid}")
    print("\tBSSID: {}".format(':'.join([f'{b:02x}' for b in wifi.radio.ap_info.bssid])))
    #print(':'.join([f'{b:02x}' for b in wifi.radio.ap_info.bssid]))
    print(f"\tChannel: {wifi.radio.ap_info.channel}")
    print(f"\tCountry: {wifi.radio.ap_info.country}")
    print(f"\tRSSI: {wifi.radio.ap_info.rssi}")
    _show_mdns()
    #del sys.modules["mdns"] # done. save space now.



def date(shell, cmdenv):
    date_time = time.localtime()
    print(f"{date_time.tm_year}-{date_time.tm_mon:02}-{date_time.tm_mday:02} {date_time.tm_hour:02}:{date_time.tm_min:02}.{date_time.tm_sec:02}")


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
    print(f"Uptime: {int(t // 3600)} hours, {int((t % 3600) // 60)} minutes, {int(t % 60)} seconds")


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
    if len(cmdenv['args']) < 2:
        print("usage: curl [-I] [-i] [--data=data] <url>")
        return

    import ssl
    url = cmdenv['args'][-1]
    method = "GET"
    headers = {"Host": "", "Connection": "close"}
    data = None
    include_headers = cmdenv['sw'].get('i', False)

    # Parse command line arguments
    if cmdenv['sw'].get('I'):
        method = "HEAD"
        include_headers = True
    if cmdenv['sw'].get('data'):
        data = cmdenv['sw']['data']
        method = "POST"
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Content-Length"] = str(len(data))

    # Parse the URL
    protocol, host, port, path = _parse_url(url)
    headers["Host"] = host

    try:
        # Create a socket pool
        pool = socketpool.SocketPool(wifi.radio)

        # Create a socket and connect
        addr_info = pool.getaddrinfo(host, port)[0]
        addr = addr_info[4]
        sock = pool.socket(addr_info[0], addr_info[1], addr_info[2])
        sock.connect(addr)

        # Wrap socket with SSL if using HTTPS
        if protocol == 'https':
            context = ssl.create_default_context()
            sock = context.wrap_socket(sock, server_hostname=host)

        # Construct the HTTP request
        request_lines = [f"{method} {path} HTTP/1.1"]
        request_lines.extend(f"{header}: {value}" for header, value in headers.items())
        request_lines.append("")  # End of headers
        request_lines.append(data if data else "")  # Data for POST
        request = "\r\n".join(request_lines) + "\r\n"

        # Send HTTP request
        sock.send(request.encode('utf-8'))

        # Receive and print response headers
        response = b""
        buffer = bytearray(1024)
        while True:
            nbytes = sock.recv_into(buffer)
            if nbytes == 0:
                break
            response += buffer[:nbytes]
            if b'\r\n\r\n' in response:
                break

        response_str = response.decode('utf-8')
        headers, body= response_str.split('\r\n\r\n', 1)
        if include_headers:
            print(headers)
            print()


        # Check for chunked transfer encoding
        if "Transfer-Encoding: chunked" in headers:
            # Process the initial part of the body
            while body:
                length_str, body = body.split('\r\n', 1)
                chunk_length = int(length_str, 16)
                if chunk_length == 0:
                    break

                # Ensure we have enough data to read the entire chunk
                while len(body) < chunk_length:
                    nbytes = sock.recv_into(buffer)
                    if nbytes == 0:
                        break
                    body += buffer[:nbytes].decode('utf-8')

                # Print the chunk data
                chunk_data = body[:chunk_length]
                print(chunk_data, end='')

                # Move to the next chunk, skipping the trailing \r\n
                body = body[chunk_length + 2:]

                # If body is empty, read more data
                if not body:
                    nbytes = sock.recv_into(buffer)
                    if nbytes == 0:
                        break
                    body += buffer[:nbytes].decode('utf-8')

        else:
            # Print the initial part of the body
            print(body, end='')

            # Read and print the remaining non-chunked data
            while True:
                nbytes = sock.recv_into(buffer)
                if nbytes == 0:
                    break
                print(buffer[:nbytes].decode('utf-8'), end='')

        # Close the socket
        sock.close()

    except Exception as e:
        print(f"Error fetching {url}: {e}")


def wget(shell, cmdenv):
    return curl(shell, cmdenv)

