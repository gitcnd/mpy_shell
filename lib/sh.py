# sh.py

__version__ = '1.0.20240720'  # Major.Minor.Patch

# Created by Chris Drake.
# Linux-like shell interface for iMicroPython.  https://github.com/gitcnd/mpy_shell
# 
# Notes:
#  scripts:
#         This runtest script __name__ is: __main__
#         Error with __file__: name '__file__' is not defined
#  modules:
#         This test script __name__ is: test
#         This test script __file__ is located at: /lib/test.py
# 
# https://github.com/todbot/circuitpython-tricks
# Alternatives: if supervisor.runtime.serial_bytes_available:
# 
# terminalio.Terminal().read(1) # for connected LCD things ?
# sys.stdin.read(1)        # for serial?
# https://chatgpt.com/share/41987e5d-4c73-432e-95cf-1e434479c1c1
# 
# 1718841600 # 2024/06/20 
# TODO:
#  tab-completion on lib/part
#  semicolons in commands
#  only try setting time once
#  dir something*.gz
#  cp somethiong*.gz lib
#  . exec
#  from sh import run_blah
#  .bashrc
#   telnet authentication
#   remove sh1._write_toml => shell._rw_toml
# handle ^C in telnet
# add -S to ls

import os
import sys
import time
import select
import socket
import gc
import machine
import binascii


class CustomIO:
    def __init__(self):
        self.input_content = ""
        self.output_content = ""
        self.server_socket = None
        self.sockets = []  # Dict of open TCP/IP client_socket connections for both input and output ['sock'] is the socket. ['addr'] is the client address. ['buf'] is the socket buffer. ['r'], ['w'], ['e'] is the state
        self.outfiles = []  # List of open file objects for output
        self.infiles = []   # List of open file objects for input
        #self.socket_buffers = {}  # Dictionary to store buffers for each socket
        self.history_file = "/.history.txt"  # Path to the history file
        self.shell=None     # telnetd sets this, so we can use get_desc

        self._nbuf = ""
        self._line = ""
        self._cursor_pos = 0
        self._lastread = time.ticks_ms()
        self._esc_seq = ""
        self._reading_esc = False
        self._insert_mode = True  # Default to insert mode
        self._hist_loc = -1  # Start with the most recent command (has 1 added before use; 0 means last)

        # New global variables for terminal size and type
        self._TERM_WIDTH = 80
        self._TERM_HEIGHT = 24
        self._TERM_TYPE = ""
        self._TERM_TYPE_EX = ""
    
        self.iac_cmds = [ # These need to be sent with specific timing to tell the client not to echo locally and exit line mode
            # First set of commands from the server
            b'\xff\xfd\x18'  # IAC DO TERMINAL TYPE
            b'\xff\xfd\x20'  # IAC DO TSPEED
            b'\xff\xfd\x23'  # IAC DO XDISPLOC
            b'\xff\xfd\x27', # IAC DO NEW-ENVIRON
        
            # Second set of commands from the server
            b'\xff\xfa\x20\x01\xff\xf0'  # IAC SB TSPEED SEND IAC SE
            b'\xff\xfa\x27\x01\xff\xf0'  # IAC SB NEW-ENVIRON SEND IAC SE
            b'\xff\xfa\x18\x01\xff\xf0', # IAC SB TERMINAL TYPE SEND IAC SE
        
            # Third set of commands from the server
            b'\xff\xfb\x03'  # IAC WILL SUPPRESS GO AHEAD
            b'\xff\xfd\x01'  # IAC DO ECHO
            b'\xff\xfd\x1f'  # IAC DO NAWS
            b'\xff\xfb\x05'  # IAC WILL STATUS
            b'\xff\xfd\x06'  # IAC DO LFLOW
            b'\xff\xfb\x01'  # IAC WILL ECHO
        ]
        # no good - line mode problems still
        #self.iac_cmds = [ # These need to be sent with specific timing to tell the client not to echo locally and exit line mode
        #    bytes([255, 252, 34]), # dont allow line mode
        #    bytes([255, 251, 1])  # turn off local echo
        #]
    

        if time.time() < 1718841600:
            import network
            if network.WLAN(network.STA_IF).isconnected(): # self.get_wifi_ip(): 
                self.set_time()  # set the time if possible and not already set


    def get_wifi_ip(self):
        try:
            wlan = network.WLAN(network.STA_IF)
            wlan.active(True)
            return wlan.ifconfig()[0]
        except:
            return None

    # Initialize buffers for sockets
    def initialize_buffers(self):
        #self.socket_buffers = {sock: "" for sock in self.sockets}
        sock[2] = {sock: "" for sock in self.sockets}

    def _read_nonblocking(self):
        if select.select([sys.stdin], [], [], 0)[0]:
            self._nbuf += sys.stdin.read(1)
            #self._nbuf += sys.stdin.read() # hangs

            #print(f" got={self._nbuf} ") # cnd

            i = self._nbuf.find('\n') + 1
            if i < 1: i = None
            ret = self._nbuf[:i]
            self._nbuf = self._nbuf[len(ret):]
            return ret
        return None


    def ins_command(self,command,mv=True):
        # Replace this with the actual command execution logic
        if self._cursor_pos>0:
            print(f'\033[{self._cursor_pos}D', end='')  # Move cursor left by current cursor_pos
        print(f'{command}\033[K', end='')  # output the new line, and clear anything after it
        if mv:
            self._cursor_pos=len(command)
        else:
            m=len(command)-self._cursor_pos
            if m>0:
                print(f'\033[{m}D', end='')  # Move cursor back to same place it was
        self._line=command

    def get_history_line(self,n):
        with open(self.history_file, "r") as f:
            for i, line in enumerate(f):
                if i == n - 1:
                    return line.split('\t', 1)[1].strip()
        return None
    

    def search_history(self, pfx, hist_loc):
        with open(self.history_file, "rb") as f:
            f.seek(0, 2)  # Seek to the end of the file
            file_size = f.tell()
            remaining = file_size
            buffer_size = 64
            partial_line = b""
            #matches = []
            match=-1
            prevm=''
            match_idx = file_size - hist_loc * buffer_size

            while remaining > 0 or partial_line:
                read_size = min(buffer_size, remaining)
                f.seek(remaining - read_size)
                buffer = f.read(read_size)
                remaining -= read_size

                lines = buffer.split(b'\n')
                if partial_line:
                    lines[-1] += partial_line
                partial_line = lines[0] if remaining > 0 else b""

                for line in reversed(lines[1:] if remaining > 0 else lines):
                    try:
                        if line.strip():
                            decoded_line = line.decode('utf-8').split('\t', 1)[1].strip()
                            #print(f"considering line: {decoded_line}")
                            if decoded_line.startswith(pfx):
                                if decoded_line != prevm: # ignore duplicates
                                    match += 1
                                prevm=decoded_line
                                #matches.append(decoded_line)
                                #print(f"yes match={match} want={hist_loc} pfx='{pfx}'")
                                if match==hist_loc:
                                    return decoded_line
                            #else:
                            #   #print(f"no match={match} want={hist_loc} pfx='{pfx}'")
                    except IndexError as e:
                        print(f"possible history_file error: {e} for line: {line}")

                #if len(matches) > hist_loc:
                #    return matches[hist_loc]

        return None


    def _process_input(self, char):
        self._lastread = time.ticks_ms()
        
        if self._reading_esc:
            self._esc_seq += char
            if self._esc_seq[-1] in 'ABCDEFGH~Rnc': 
                response = self._handle_esc_sequence(self._esc_seq[2:])
                self._reading_esc = False
                self._esc_seq = ""
                if response:
                    return response
            elif time.ticks_ms() - self._lastread > 100:
                self._reading_esc = False
                self._esc_seq = ""
                return self._line, "esc", self._cursor_pos
        elif char == '\x1b':  # ESC sequence
            self._reading_esc = True
            self._esc_seq = char
        elif char == '\x03':  # ctrl-C ^C
            print("KeyboardInterrupt:")
            raise KeyboardInterrupt
        elif char in ['\x7f', '\b']:  # Backspace
            if self._cursor_pos > 0:
                self._line = self._line[:self._cursor_pos - 1] + self._line[self._cursor_pos:]
                self._cursor_pos -= 1
                print('\b \b' + self._line[self._cursor_pos:] + ' ' + '\b' * (len(self._line) - self._cursor_pos + 1), end='')
        elif char in ['\r', '\n']:  # Enter
            ret_line = self._line
            err='sh: !{}: event not found'
            if ret_line.startswith("!"): # put history into buffer
                if ret_line[1:].isdigit():
                    nth = int(ret_line[1:])
                    history_line = self.get_history_line(nth)
                    if history_line:
                        self.ins_command(history_line)
                    else:
                        print(err.format(nth)) # sh: !123: event not found
                        return '' # re-show the prompt
                else:
                    pfx = ret_line[1:]
                    history_line = self.search_history(pfx,0)
                    if history_line:
                        self.ins_command(history_line)
                    else:
                        print(err.format(pfx)) # sh: !{pfx}: event not found
                        return '' # re-show the prompt
            else:
                print('\r')
                self._line = ""
                self._cursor_pos = 0
                self._hist_loc = -1
                return ret_line, 'enter', self._cursor_pos

        elif char == '\001':  # repl exit
            return 'exit', 'enter', 0
        elif char == '\t':  # Tab
            #return self._line, 'tab', self._cursor_pos
            current_input = self._line[:self._cursor_pos]
            if any(char in current_input for char in [' ', '<', '>', '|']):
                # Extract the word immediately at the cursor
                last_space = current_input.rfind(' ') + 1
                #if last_space == -1:
                #    last_space = 0
                #else:
                #    last_space += 1
                word = current_input[last_space:self._cursor_pos]
        
                try:
                    for entry in os.listdir():
                        if entry.startswith(word):
                            self.ins_command(self._line[:self._cursor_pos] + entry[len(word):] + self._line[self._cursor_pos:])
                            break
                except OSError as e:
                    print(f"Error listing directory: {e}")

            else:
                from sh1 import _iter_cmds
                for cmd in _iter_cmds():
                    if cmd.startswith(current_input):
                         self.ins_command(self._line[:self._cursor_pos] + cmd[len(current_input):] + ' ' + self._line[self._cursor_pos:])
                         break
                del sys.modules["sh1"]

        else:
            if self._insert_mode:
                self._line = self._line[:self._cursor_pos] + char + self._line[self._cursor_pos:]
                print(f'\033[@{char}', end='')  # Print char and insert space at cursor position
            else:
                self._line = self._line[:self._cursor_pos] + char + self._line[self._cursor_pos + 1:]
                print(char, end='')
            self._cursor_pos += 1
        
        return None

    def _handle_esc_sequence(self, seq):

        if seq in ['A', 'B']:  # Up or Down arrow
            i = 1 if seq == 'A' else -1
            
            if seq == 'B' and self._hist_loc < 1:
                return
        
            self._hist_loc += i

            history_line = self.search_history(self._line[:self._cursor_pos], self._hist_loc)

            #print(f"arrow {seq} line {self._hist_loc} h={history_line}")
            
            if history_line:
                self.ins_command(history_line,mv=False)
            else:
                self._hist_loc -= i

            #return self._line, 'up' if seq == 'A' else 'down', self._cursor_pos
        elif seq == 'C':  # Right arrow
            if self._cursor_pos < len(self._line):
                self._cursor_pos += 1
                print('\033[C', end='')
        elif seq == 'D':  # Left arrow
            if self._cursor_pos > 0:
                self._cursor_pos -= 1
                print('\033[D', end='')
        elif seq == '3~':  # Delete
            if self._cursor_pos < len(self._line):
                self._line = self._line[:self._cursor_pos] + self._line[self._cursor_pos + 1:]
                print('\033[1P', end='')  # Delete character at cursor position
        elif seq == '2~':  # Insert
            self._insert_mode = not self._insert_mode
        elif seq in ['H', '1~']:  # Home
            if self._cursor_pos > 0:
                print(f'\033[{self._cursor_pos}D', end='')  # Move cursor left by current cursor_pos
            self._cursor_pos = 0
        elif seq in ['F', '4~']:  # End
            d=len(self._line) - self._cursor_pos
            if d>0:
                print(f'\033[{d}C', end='')  # Move cursor right by difference
            self._cursor_pos = len(self._line)
        elif seq == '1;5D':  # Ctrl-Left
            if self._cursor_pos > 0:
                prev_pos = self._cursor_pos
                while self._cursor_pos > 0 and self._line[self._cursor_pos - 1].isspace():
                    self._cursor_pos -= 1
                while self._cursor_pos > 0 and not self._line[self._cursor_pos - 1].isspace():
                    self._cursor_pos -= 1
                print(f'\033[{prev_pos - self._cursor_pos}D', end='')
        elif seq == '1;5C':  # Ctrl-Right
            if self._cursor_pos < len(self._line):
                prev_pos = self._cursor_pos
                while self._cursor_pos < len(self._line) and not self._line[self._cursor_pos].isspace():
                    self._cursor_pos += 1
                while self._cursor_pos < len(self._line) and self._line[self._cursor_pos].isspace():
                    self._cursor_pos += 1
                print(f'\033[{self._cursor_pos - prev_pos}C', end='')
        elif seq.endswith('R'):  # Cursor position report
            try:
                self._TERM_HEIGHT, self._TERM_WIDTH = map(int, seq[:-1].split(';'))
            except Exception as e:
                print("term-size set command {} error: {}; seq={}",format(seq[:-1],e,  binascii.hexlify(seq)  ))
            return self._line, 'sz', self._cursor_pos
        elif seq.startswith('>') and seq.endswith('c'):  # Extended device Attributes
            self._TERM_TYPE_EX = seq[1:-1]
            return seq, 'attr', self._cursor_pos
        elif seq.startswith('?') and seq.endswith('c'):  # Device Attributes
            self._TERM_TYPE = seq[1:-1]
            return seq, 'attr', self._cursor_pos
        return None


    def add_hist(self, line, retry=True):
        try:
            with open(self.history_file, 'a') as hist_file:
                hist_file.write(f"{int(time.time())}\t{line}\n")
        except OSError:
            # If an OSError is raised, the file system is read-only
            if retry:
                import storage
                try:
                    storage.remount("/", False)
                    add_hist(self, line, False)
                except: 
                    pass


    def readline(self):
        if self.input_content:
            line = self.input_content
            self.input_content = ""
            return line
        raise EOFError("No more input")

    def _del_old_socks(self,sockdel):
        for i in sockdel:
            client_socket=self.sockets[i]
            client_socket['sock'].close()
            print(f"Closed telnet client {i} IP {client_socket['addr']}")
            del self.sockets[i]

    def telnetd(self, shell, port=None): # see sh2.py which calls this via:    shell.cio.telnetd(shell,cmdenv['sw'].get('port', 23)) # tell our shell to open up the listening socket
        import network
        self.shell=shell

        sta_if = network.WLAN(network.STA_IF)
        sta_if.active(True)
        ip_address = sta_if.ifconfig()[0]

        # Create a non-blocking socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.setblocking(False)
        self.server_socket.bind((ip_address, port))
        self.server_socket.listen(1)

        self.tspassword='pass'
        print("Telnet server started on IP", ip_address, "port", port)



    # Read input from stdin, sockets, or files
    def read_input(self):

        # Read from input files
        for file in self.infiles:
            line = file.readline()
            if line:
                return line

        # Read from stdin
        chars=1 # keep doing this 'till we get nothing more
        while chars:
            #print("r1")
            chars = self._read_nonblocking()

            # Read from sockets
            sockdel=[]
            for i, client_socket in enumerate(self.sockets):
                client_socket['r'], _, client_socket['e'] = select.select([client_socket['sock']], [], [client_socket['sock']], 0)
                for s in client_socket['r']:
                    if 1:#try:
                        data = client_socket['sock'].recv(1024).decode('utf-8').rstrip('\000')
                        if data:
                            if 'a' in client_socket: # not authenticated yet
                                client_socket['a'] += data
                                if ord(client_socket['a'][-1]) == 0x0d or len(client_socket['a'])>63: # caution; neither client_socket['a'][-1]=='\n' nor client_socket['a'].endswith('\n') work here!
                                    client_socket['a'] = client_socket['a'][:-1] # .rstrip('\n') does not work here
                                    if client_socket['a'] == self.tspassword:
                                        import network
                                        del client_socket['a'] # this lets them in
                                        #client_socket['sock'].send()
                                        client_socket['buf']="\r\nWelcome to {} - {} Micropython {} on {}\r\n".format(network.WLAN(network.STA_IF).config('hostname'),os.uname().sysname,os.uname().version,os.uname().machine).encode('utf-8')
                                        print("",end='')
                                    else:
                                        try:
                                            client_socket['sock'].send(b'wrong.\r\n')
                                        except:
                                            pass
                                        sockdel.insert(0,i) # kick off the attempt
                            else:
                                chars = chars + data if chars else data
                        else:
                            print("EOF ", client_socket['addr'])
                            sockdel.insert(0,i) # remember to close it shortly (backwards from end, so index numbers don't change in the middle)
                    #except Exception as e:
                    #    print("read Exception ",e, "on ", client_socket['addr'])
                    #    continue
    
                for s in client_socket['e']:
                    print("Handling exceptional condition for", client_socket['addr'])
                    if i not in sockdel:
                        sockdel.insert(0,i) # remember to close it shortly (backwards from end, so index numbers don't change in the middle)
    
            self._del_old_socks(sockdel)
    
    
            if self.server_socket:# Accept new connections
                readable, _, exceptional = select.select([self.server_socket], [], [self.server_socket], 0)
                for s in exceptional:
                    print("server_socket err?",s)
                for s in readable:
                    # Handle new connection
                    client_sock, client_addr = self.server_socket.accept() # client_socket['sock'] is the socket, client_socket['addr'] is the address
                    self.sockets.append({
                        'sock': client_sock,
                        'addr': client_addr, 
                        'buf': b'', 
                        'r': "", 
                        'w': "", 
                        'e': "",
                        'a': "" # unauthenticated
                    })
        
                    print("Connection from", client_addr)
                    client_sock.setblocking(False)
        
                    # Tell the new connection to set up their terminal for us
                    for i, cmd in enumerate(self.iac_cmds + [b'Password: ']):
                        #print("sent: ", binascii.hexlify(cmd))
                        client_sock.send(cmd)
                        # Wait for the client to respond
                        time.sleep(0.1)
                        if i>2:
                            ready_to_read, _, _ = select.select([client_sock], [], [], 5)
                            if ready_to_read:
                                ignore = client_sock.recv(1024)
                                #if ignore:
                                #    print("got: ", binascii.hexlify(ignore))
                            else:
                                print(f"No response from client {client_addr} within timeout. Disconnected")
                                client_sock.close()
                                del self.sockets[-1]

            if chars:

                for char in chars:
                    response = self._process_input(char)
                    if response:
                        user_input, key, cursor = response
                        if key=='enter':
                            if len(user_input):
                                self.add_hist(user_input)
                            return user_input
                        elif key != 'sz': 
                            oops=f" (mode {key} not implimented)";
                            print(oops +  '\b' * (len(oops)), end='')

            elif time.ticks_ms()-self._lastread > 100:
                time.sleep(0.1)  # Small delay to prevent high CPU usage

        return None


    # Send characters to all sockets and files. should be called often with '' for flushing slow sockets (until it says all-gone)
    def send_chars_to_all(self, chars):
        if chars:
            chars = chars.replace('\r\n', '\n').replace('\n', '\r\n') # # Convert LF to CRLF (not breaking any existing ones)
            #if isinstance(chars, bytes):
            #    print("BAD");exit();#chars = chars.replace(b'\\n', b'\r\n')  # Convert LF to CRLF
            #else:
            #    chars = chars.replace('\\n', '\r\n')  # Convert LF to CRLF

            #chars= binascii.hexlify(chars)


            # Send to stdout
            sys.stdout.write(chars)
            # sys.stdout.flush() # AttributeError: 'FileIO' object has no attribute 'flush'

            # Send to all output files
            for file in self.outfiles:
                try:
                    file.write(chars)
                    file.flush()
                except Exception as e:
                    print(self.shell.get_desc('3').format(e)) #  File write exception: {}

        # Flag to check if any buffer has remaining data
        any_buffer_non_empty = False

        # Send to all sockets
        sockdel=[]
        for i, client_socket in enumerate(self.sockets):
            if 'a' in client_socket:
                continue # as-yet unauthenticated connection
            client_socket['buf'] += chars.encode('utf-8')
            if client_socket['buf']:
                _, client_socket['w'], client_socket['e'] = select.select([], [client_socket['sock']], [client_socket['sock']], 0)
                for s in client_socket['w']:
                    try:
                        bsent=client_socket['sock'].send(client_socket['buf'])
                        client_socket['buf'] = client_socket['buf'][bsent:]  # Fix partial sends by updating the buffer
                    except Exception as e:
                        print(self.shell.get_desc('4').format(e)) # Socket send exception: {}
                        sockdel.insert(0,i) # remember to close it shortly

            if client_socket['buf']: # Update the flag if there is still data in the buffer
                any_buffer_non_empty = True

            if len(client_socket['buf']) > 80:
                client_socket['buf'] = client_socket['buf'][-80:]  # Keep only the last 80 chars

        self._del_old_socks(sockdel)

        return any_buffer_non_empty


    # Method to open an output file
    def open_output_file(self, filepath):
        try:
            file = open(filepath, 'w')
            self.outfiles.append(file)
            #print("Output file opened successfully.")
        except Exception as e:
            print(self.shell.get_desc('5').format(e)) # Output file setup failed: {}

    # Method to open an input file
    def open_input_file(self, filepath):
        try:
            file = open(filepath, 'r')
            self.infiles.append(file)
            #print("Input file opened successfully.")
        except Exception as e:
            print(self.shell.get_desc('6').format(e)) # Input file setup failed: {}

    # Method to open a socket

    def open_socket(self, address, port, timeout=10): # GPT
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((address, port))
            self.sockets.append(sock)
            self.initialize_buffers()
        except Exception as e:
            print(self.shell.get_desc('7').format(e))  # Socket setup failed: {}

    """ # Method to open a listening socket on port 23 for Telnet
    def open_listening_socket(self, port=23):
        try:
            pool = socketpool.SocketPool(wifi.radio)
            server_sock = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
            server_sock.bind(("", port))
            server_sock.listen(1)
            print("Listening on {}:{} for incoming Telnet connections.".format(wifi.radio.ipv4_address,port))
            self.sockets.append(server_sock) # wrong approach - this is a listen, not a read or write socket...
            self.initialize_buffers()
        except Exception as e:
            print("Listening socket setup failed:", e)
    """

    # Method to flush buffers
    def flush(self):
        while self.send_chars_to_all(""):
            pass # time.sleep(0.1)  # Prevent a tight loop


    def set_time(self):
        import struct
        buf=b'\x1b' + 47 * b'\0'

        if 1: # try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(1)
            # Send NTP request
            sock.sendto(buf, (socket.getaddrinfo("pool.ntp.org", 123)[0][-1]))
            buf, _ = sock.recvfrom(48)
            rtc = machine.RTC()
            rtc.datetime( time.localtime(struct.unpack("!I", buf[40:44])[0] - 2208988800 - 946728000) ) # NTP timestamp starts from 1900, Unix from 1970
            #machine.RTC().datetime = time.localtime(struct.unpack("!I", buf[40:44])[0] - 2208988800) # NTP timestamp starts from 1900, Unix from 1970
        #except Exception as e:
        #    print(self.shell.get_desc('8').format(e))  # Failed to get NTP time: {}
        #finally:
            sock.close()
        print("Time set to: {:04}-{:02}-{:02} {:02}:{:02}:{:02}".format(*time.localtime()[:6]))
        self.add_hist("#boot")

class IORedirector:
    def __init__(self, custom_io):
        self.custom_io = custom_io
        self.old_input = None
        self.old_print = None

    def __enter__(self):
        import builtins
        self.old_input = builtins.input
        self.old_print = builtins.print
        builtins.input = self.custom_input
        builtins.print = self.custom_print

    def __exit__(self, exc_type, exc_val, exc_tb):
        import builtins
        builtins.input = self.old_input
        builtins.print = self.old_print

    def custom_input(self, prompt=''):
        self.custom_print(prompt, end='')
        while True:
            line = self.custom_io.read_input()
            if line is not None:
                return line.rstrip('\n')

    def custom_print(self, *args, **kwargs):
        sep = kwargs.get('sep', ' ')
        end = kwargs.get('end', '\n')
        output = sep.join(map(str, args)) + end
        self.custom_io.send_chars_to_all(output)



class sh:
    def __init__(self,cio=None):
        self.settings_file = "/settings.toml"
        self.cio=cio
        #self.get_desc=cio.get_desc
        #self.subst_env=cio.subst_env
        pass # self.history_file = "/history.txt"


    def _extr(shell,value_str):
        value_str = value_str.strip()
    
        # Handle different quote types
        if value_str.startswith("'") or value_str.startswith('"'):
            q = value_str[0]
            if value_str.startswith(f"{q}{q}{q}"):
                q = value_str[:3]
            
            end_idx = value_str.find(q, len(q))
            while end_idx != -1 and value_str[end_idx-1] == '\\':  # Check for escaped quote
                end_idx = value_str.find(q, end_idx + len(q))
            
            if end_idx == -1:
                raise ValueError("Unterminated string")
    
            return value_str[len(q):end_idx] # value_str[:end_idx + len(q)].strip()
        
        # Handle numeric and other literals
        else:
            return value_str.split('#', 1)[0].strip()


    def _rw_toml(shell, op, key, value=None):
        tmp = shell.settings_file.rsplit('.', 1)[0] + "_new." + shell.settings_file.rsplit('.', 1)[1] # /settings_new.toml
        old = shell.settings_file.rsplit('.', 1)[0] + "_old." + shell.settings_file.rsplit('.', 1)[1] # /settings_old.toml

        try:
            infile = open(shell.settings_file, 'r')
        except OSError:
            if op == 'w':
                open(shell.settings_file, 'w').close() # create empty one if missing
                infile = open(shell.settings_file, 'r')
            else:
                return None

        outfile = open(tmp, 'w') if op == "w" else None
    
        in_multiline = False
        extra_iteration = 0
        line = ''

        while True:
            if extra_iteration < 1:
                iline = infile.readline()
                if not iline:
                    extra_iteration = 1
                    iline = ''  # Trigger the final block execution
            elif extra_iteration == 2:
                extra_iteration = 0
            else:
                break

            line += iline
            iline = ''
            stripped_line = line.strip()

            if in_multiline:
                if stripped_line.endswith( in_multiline ) and not stripped_line.endswith(f'\\{in_multiline}'):
                    in_multiline = '' # tell it not to re-check next
                else:
                    continue

            if not stripped_line.startswith('#'):
                kv = stripped_line.split('=', 1)
                if not in_multiline == '': # not just ended a multiline
                    if len(kv) > 1 and ( kv[1].strip().startswith('"""') or kv[1].strip().startswith("'''")):
                        in_multiline = '"""' if kv[1].strip().startswith('"""') else "'''"
                        extra_iteration = 2 # skip reading another line, and go back to process this one (which might have the """ or ''' ending already on it) 
                        continue

                if len(kv) > 1 or extra_iteration == 1:
                    if kv[0].strip() == key or extra_iteration == 1:

                        if op != 'w':
                            ret= shell._extr(kv[1]).replace("\\u001b", "\u001b") if len(kv) > 1 else None # convert "\x1b[" to esc[ below
                            if ret is not None and ret[0] in '[{(':
                                import json
                                ret=json.loads(ret)
                            return ret

                        elif value == '':
                            line='' # Delete the variable
                            continue
                        elif key:
                            if isinstance(value,(dict, list, tuple)):
                                import json
                                line = '{} = {}\n'.format(key, json.dumps(value))
                            elif value[0] in '+-.0123456789"\'': # Update the variable
                                line = f'{key} = {value}\n'
                            else:
                                #line = f'{key} = "{value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")}"\n' 
                                line = '{} = "{}"\n'.format(key, value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t"))
                            key=None

            in_multiline = False
            if outfile:
                outfile.write(line)
            line=''


        infile.close()
        if outfile:
            outfile.close()
            # Replace old settings with the new settings
            import sh0  # load mv command
            sh0.mv(shell, {'sw': {}, 'args': ['mv', shell.settings_file, old]}) # '/settings_old.toml'
            sh0.mv(shell, {'sw': {}, 'args': ['mv', tmp, shell.settings_file]})
            del sys.modules['sh0']
    

    def os_getenv(shell, key, dflt=None):
        return shell._rw_toml('r',key) or dflt


    def subst_env(self, value):
        result = ''
        i = 0
        while i < len(value):
            if value[i] == '\\' and i + 1 < len(value) and value[i + 1] == '$':
                result += '$'
                i += 2
            elif value[i] == '$':
                i += 1
                i, expanded = self.exp_env(i,value)
                result += expanded
            else:
                result += value[i]
                i += 1
        return result


    # For reading help and error messages etc out of a text file
    def get_desc(self,keyword):
        with open(__file__.rsplit('.', 1)[0] + '.txt', 'r') as file:   # /lib/sh.txt
            for line in file:
                try:
                    key, description = line.split('\t', 1)
                    if key == str(keyword):
                        return self.subst_env(description.strip()).replace("\\n","\n").replace("\\t", "\t").replace("\\\\", "\\")
                except: 
                    return 'corrupt help file'

        return None


    # error-message expander helpers
    def _ea(shell, cmdenv):
        print(shell.get_desc('9').format(cmdenv['args'][0])) # {}: missing operand(s)

    def _ee(shell, cmdenv, e):
        print(shell.get_desc('10').format(cmdenv['args'][0],e)) # {}: {}


    def file_exists(self, filepath):
        try:
            os.stat(filepath)
            return True
        except OSError:
            return False


    def exp_env(self,start,value):
        if value[start] == '{':
            end = value.find('}', start)
            var_name = value[start + 1:end]
            if var_name.startswith('!'):
                var_name = self.os_getenv(var_name[1:], f'${{{var_name}}}')
                var_value = self.os_getenv(var_name, f'${{{var_name}}}')
            else:
                var_value = self.os_getenv(var_name, f'${{{var_name}}}')
            return end + 1, var_value
        else:
            end = start
            while end < len(value) and (value[end].isalpha() or value[end].isdigit() or value[end] == '_'):
                end += 1
            var_name = value[start:end]
            var_value = self.os_getenv(var_name, f'${var_name}')
            return end, var_value


    def parse_command_line(self, command_line):
        def split_command_o(command_line):
            # """Split command line into parts respecting quotes and escape sequences."""
            parts = []
            part = ''
            in_single_quote = False
            in_double_quote = False
            escape = False

            for char in command_line:
                if escape:
                    part += char
                    escape = False
                elif char == '\\':
                    escape = True
                elif char == '"' and not in_single_quote:
                    in_double_quote = not in_double_quote
                    part += char
                elif char == "'" and not in_double_quote:
                    in_single_quote = not in_single_quote
                    part += char
                elif char.isspace() and not in_single_quote and not in_double_quote:
                    if part:
                        parts.append(part)
                        part = ''
                elif char in '|<>':
                    if part:
                        parts.append(part)
                        part = ''
                    parts.append(char)
                else:
                    part += char

            if part:
                parts.append(part)
            return parts

        
        
        def split_command(command_line):
            # """Split command line into parts respecting quotes and escape sequences."""
            parts = []
            part = ''
            in_single_quote = False
            in_double_quote = False
            in_backticks = False
            in_subshell = 0
            escape = False
        
            i = 0
            while i < len(command_line):
                char = command_line[i]
                if escape:
                    part += char
                    escape = False
                elif char == '\\':
                    escape = True
                elif char == '"' and not in_single_quote and not in_backticks and in_subshell == 0:
                    in_double_quote = not in_double_quote
                    part += char
                elif char == "'" and not in_double_quote and not in_backticks and in_subshell == 0:
                    in_single_quote = not in_single_quote
                    part += char
                elif char == '`' and not in_single_quote and not in_double_quote and in_subshell == 0:
                    if in_backticks:
                        in_backticks = False
                        part += char
                        parts.append(part)
                        part = ''
                    else:
                        if part:
                            parts.append(part)
                            part = ''
                        in_backticks = True
                        part += char
                elif char == '$' and i + 1 < len(command_line) and command_line[i + 1] == '(' and not in_single_quote and not in_double_quote and not in_backticks:
                    if in_subshell == 0 and part:
                        parts.append(part)
                        part = ''
                    in_subshell += 1
                    part += char
                elif char == ')' and not in_single_quote and not in_double_quote and not in_backticks and in_subshell > 0:
                    in_subshell -= 1
                    part += char
                    if in_subshell == 0:
                        parts.append(part)
                        part = ''
                elif char.isspace() and not in_single_quote and not in_double_quote and not in_backticks and in_subshell == 0:
                    if part:
                        parts.append(part)
                        part = ''
                elif char in '|<>' and not in_single_quote and not in_double_quote and not in_backticks and in_subshell == 0:
                    if part:
                        parts.append(part)
                        part = ''
                    parts.append(char)
                else:
                    part += char
                i += 1
        
            if part:
                parts.append(part)
            return parts
        



        def substitute_backticks(value):
            # """Substitute commands within backticks and $(...) with their output."""
            def substitute(match):
                command = match.group(1)
                return self.execute_command(command)  # Placeholder for actual command execution

            while '`' in value or '$(' in value:
                if '`' in value:
                    start = value.find('`')
                    #print(f"` start={start} value={value}")
                    end = value.find('`', start + 1)
                    #print(f"` end={end} value={value}")
                    if end == -1:
                        break
                    command = value[start + 1:end]
                    #print(f"` command={command}")
                    value = value[:start] + self.execute_command(command) + value[end + 1:]
                    #print(f"` new value={value}")
                if '$(' in value:
                    start = value.find('$(')
                    #print(f"$( start={start} value={value}")
                    end = start + 2
                    #print(f"$( end={end} value={value}")
                    open_parens = 1
                    while open_parens > 0 and end < len(value):
                        if value[end] == '(':
                            open_parens += 1
                        elif value[end] == ')':
                            open_parens -= 1
                        end += 1
                    command = value[start + 2:end - 1]
                    command = value[start + 2:end]
                    #print(f"$( command={command}")
                    value = value[:start] + self.execute_command(command) + value[end:]
                    #print(f"$( new value={value}")
            return value

        
        def process_parts(parts):
            # """Process parts into switches and arguments."""
            #sw = {}
            #arg = []
            redirections = {'stdin': None, 'stdout': None, 'stderr': None}
            current_cmd = {'line': '', 'sw': {}, 'args': [], 'redirections': redirections, 'pipe_from': None}

            cmds = [current_cmd]
            i = 0
            while i < len(parts):
                part = parts[i]
                if part == '|':
                    current_cmd = {'line': '', 'sw': {}, 'args': [], 'redirections': {'stdin': None, 'stdout': None, 'stderr': None}, 'pipe_from': cmds[-1]}
                    cmds.append(current_cmd)
                elif part == '>':
                    redirections['stdout'] = parts[i + 1]
                    i += 1
                elif part == '>>':
                    redirections['stdout'] = {'append': parts[i + 1]}
                    i += 1
                elif part == '<':
                    redirections['stdin'] = parts[i + 1]
                    i += 1
                elif part.startswith('--'):
                    if '=' in part:
                        key, value = part[2:].split('=', 1)
                        if not (value.startswith("'") and value.endswith("'")):
                            value = self.subst_env(substitute_backticks(value))
                        current_cmd['sw'][key] = value
                        current_cmd['line'] += f" --{key}={value}"
                    else:
                        current_cmd['sw'][part[2:]] = True
                        current_cmd['line'] += ' ' + part
                elif part.startswith('-') and len(part) > 1:
                    j = 1
                    while j < len(part):
                        if part[j].isalpha():
                            current_cmd['sw'][part[j]] = True
                            j += 1
                        else:
                            current_cmd['sw'][part[j]] = part[j + 1:] if j + 1 < len(part) else True
                            break
                    current_cmd['line'] += ' ' + part
                else:
                    if not (part.startswith("'") and part.endswith("'")):
                        part = self.subst_env(substitute_backticks(part))
                    current_cmd['args'].append(part)
                    current_cmd['line'] += (' ' if current_cmd['line'] else '') + part

                i += 1

            return cmds

        parts = split_command(command_line)
        cmds = process_parts(parts)

        return cmds


    def human_size(self,size):
        # Convert bytes to human-readable format
        for unit in ['B', 'K', 'M', 'G', 'T']:
            if size < 1024:
                return f"{round(size):,}{unit}"
            size /= 1024
        return f"{round(size):,}P"  # Handle very large sizes as petabytes

    
    def execute_command(self,command):
        # """Execute a command and return its output. Placeholder for actual execution logic."""
        for _ in range(2): # optional alias expander
            parts = self.parse_command_line(command)
            cmdenv = parts[0]  # Assuming simple commands for mock execution
            cmd=cmdenv['args'][0]
            #print("executing: {}".format(cmdenv['line'])) #DBG

            alias = self.os_getenv(cmd)
            if alias is not None:
                command=alias + command[command.find(' '):] if ' ' in command else alias
            else:
                break

        # internal commands
        if cmd == 'exit':
            return 0


        #if cmd == 'echo':
        #    print( cmdenv['line'].split(' ', 1)[1] if ' ' in cmdenv['line'] else '') # " ".join(cmdenv['args'][1:])
        #elif cmd == 'sort':
        #    return "\n".join(sorted(cmdenv['args'][1:], reverse='-r' in cmdenv['sw']))
        #elif cmd == 'ls':
        #    return "file1.txt\nfile2.txt\nfile3.txt"


        for mod in ["sh0", "sh1", "sh2"]:
            gc.collect()
            module = __import__(mod)

            # sh_module = sys.modules['sh0']
            command_function = getattr(module, cmd,None)
            if command_function:
                #print(f"running {mod}.{cmd}")
                ret=command_function(self,cmdenv)  # Run the command
                del sys.modules[mod]
                gc.collect()
                return 1
                # return ret
                break
            del sys.modules[mod]
            gc.collect()

        print(self.get_desc('0').format(cmd)) # {} command not found
        return 1 # keep running
    



# Main function to demonstrate usage
def main():

    custom_io = CustomIO()
    #custom_io.open_socket('chrisdrake.com', 9887)
    #custom_io.open_output_file('/example.txt')
    #custom_io.open_input_file('/testin.txt')
    #NG: custom_io.open_listening_socket()  # Open listening socket on telnet port 23 - no code for accept() etc exists yet.


    # Use the custom context manager to redirect stdout and stdin
    with IORedirector(custom_io):

        shell = sh(custom_io)

        # see sh1.py/test() for argument parsing tests

        # test $VAR expansion
        #print(shell.subst_env("$GRN$HOSTNAME$NORM:{} cpy\$ ").format(os.getcwd()))
        # print("GET /lt.asp?cpy HTTP/1.0\r\nHost: chrisdrake.com\r\n\r\n")

        #ng: print("helpme");help("modules");print("grr")

        # test input
        run=1
        print("\033[s\0337\033[999C\033[999B\033[6n\r\033[u\0338", end='')  # Request terminal size.
        while run>0:
            run=1
            user_input = input(shell.subst_env("$GRN$HOSTNAME$NORM:{} mpy\$ ").format(os.getcwd())) # the stuff in the middle is the prompt
            if user_input:
                #print("#############")
                #print(''.join(f' 0x{ord(c):02X} ' if ord(c) < 0x20 else c for c in user_input))
                #print("#############")
                #hex_values = ' '.join(f'{ord(c):02x}' for c in user_input)
                #print("input=0x " + hex_values)
                # print(f"Captured input: {user_input}")
                # print(f"input=0x{' '.join(f'{ord(c):02x}' for c in user_input)}") # print(f"input=0x {user_input.hex()}")
                # print(shell.execute_command(user_input))
                run=2 # bypass the sleep 1 time
                try:
                    run=shell.execute_command(user_input) # IORedirector takes care of sending the "print" statements from these to the right place(s)
                except KeyboardInterrupt:
                    print("^C")
            if run>1: time.sleep(0.1)  # Perform other tasks here


    custom_io.flush()

# run it right now
main()
if "sh" in sys.modules:
    del sys.modules["sh"] # so we can re-run us later


### See also ###
# import storage
# storage.erase_filesystem()
#
# import storage
# storage.disable_usb_drive()
# storage.remount("/", readonly=False)
