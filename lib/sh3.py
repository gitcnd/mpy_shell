# sh3.py

__version__ = '1.0.20240801'  # Major.Minor.Patch

# Created by Chris Drake.
# Linux-like shell interface for CircuitPython.  https://github.com/gitcnd/cpy_shell
# 
# This is a separate module for holding some commands.
# it is separate to save RAM


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
    import time
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



def create(shell, cmdenv):
    if len(cmdenv['args']) < 2:
        shell._ea(cmdenv)  # print("cat: missing file operand")
    else:
        path = cmdenv['args'][1]
        try:
            with open(path, 'wb') as file:
                print(shell.get_desc(52)) # "Enter text to write to the file. Press ^D (Ctrl+D) to end.")
                import sys
                while True:
                    try:
                        line = sys.stdin.read(1) # no echo
                        # line = input()
                        if line=='\x04': break # mpy ^D
                        #file.write(line.encode('utf-8') + b'\n')
                        file.write(line.encode('utf-8'))
                    except EOFError:
                        break
        except Exception as e:
            shell._ee(cmdenv, e)  # print(f"cat: {e}")


def espnow(shell, cmdenv): # usage: espnowreceiver --op=send --channel=9 --msg="some message"
    import network, espnow
    op=cmdenv['sw'].get('op', 'rec') # send or rec

    # A WLAN interface must be active to send()/recv()
    sta = network.WLAN(network.STA_IF)  # Or network.AP_IF
    sta.active(True)
    chan = int(cmdenv['sw'].get('channel', -1))
    if chan >= 0: sta.config(channel=chan)  # Set a specific WLAN channel
    #sta.disconnect()       # For ESP8266

    e = espnow.ESPNow()
    e.active(True)
    if op == 'send':
        msg=cmdenv['sw'].get('msg', 'Hello espnow world; at ' + now(shell, cmdenv)) # default message
        peer = b'\xff\xff\xff\xff\xff\xff'  # broadcast mac address to all esp32's (not esp8266)
        try:
            e.add_peer(peer)      # Must add_peer() before send()
        except: # OSError: (-12395, 'ESP_ERR_ESPNOW_EXIST')
            pass
        e.send(peer, msg)
        print(f"Sent: {msg}")
    else:
        print(shell.get_desc(35).format( shell.get_desc(36).format(chan) if chan >= 0 else "") ) # f"Listening for espnow packets{cm}. Hit ^C to stop:")  # cm=f" on channel {chan}" if chan >= 0 else ""

        while True:
            host, msg = e.recv()
            if msg:             # msg == None if timeout in recv()
                print(f"From: {host} got: {msg}")
                if msg == b'end' or cmdenv['sw'].get('one', False):
                    break
    e.active(False)

# Below not finished
def espnowreceiver(shell, cmdenv): # usage: espnowreceiver --channel=9
    cmdenv['sw']['op']='rec'
    espnow(shell, cmdenv)  # same as alias

def espnowsender(shell, cmdenv): # usage: espnowreceiver --channel=9
    cmdenv['sw']['op']='send'
    espnow(shell, cmdenv)  # same as alias



def scani2c(shell, cmdenv):
    if not 'scl' in cmdenv['sw'] or not 'sda' in cmdenv['sw']:
        print(shell.get_desc(69)) # "usage: scani2c --scl=<scl pin number> --sda=<sda pin number>"
    else:
        from machine import I2C, Pin
        bus=int(cmdenv['sw']['bus']) if 'bus' in cmdenv['sw'] else 0
        scl=int(cmdenv['sw']['scl'])
        sda=int(cmdenv['sw']['sda'])
        i2c = I2C(bus,scl=scl,sda=sda)
        print(shell.get_desc(70).format(bus,scl,sda)) # Scanning I2C devices on bus{} scl=gpio{} sda=gpio{}
        devices = i2c.scan()

        if devices:
            print(shell.get_desc(71).format(devices)) # "I2C devices found:", devices
        else:
            print(shell.get_desc(72)) # No I2C devices found

