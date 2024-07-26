# sh3.py

__version__ = '1.0.20240727'  # Major.Minor.Patch

# Created by Chris Drake.
# Linux-like shell interface for CircuitPython.  https://github.com/gitcnd/cpy_shell
# 
# This is a separate module for holding some commands.
# it is separate to save RAM


def create(shell, cmdenv):
    if len(cmdenv['args']) < 2:
        shell._ea(cmdenv)  # print("cat: missing file operand")
    else:
        path = cmdenv['args'][1]
        try:
            with open(path, 'wb') as file:
                print(shell.get_desc(52)) # "Enter text to write to the file. Press ^D (Ctrl+D) to end.")
                while True:
                    try:
                        line = input()
                        if line=='\x04': break # mpy ^D
                        file.write(line.encode('utf-8') + b'\n')
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
