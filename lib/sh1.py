# sh1.py

__version__ = '1.0.20240808'  # Major.Minor.Patch

# Created by Chris Drake.
# Linux-like shell interface for CircuitPython.  https://github.com/gitcnd/cpy_shell
# 
# This is a separate module for holding some commands.
# it is separate to save RAM
# 3942+4180

import gc
import sys
import os


def reboot(shell, cmdenv):
    import machine
    import time
    #print("Rebooting...") # Anything over 7 bytes is less to do a print(shell.get_desc(...)) on
    print(shell.get_desc(27)) # Rebooting... (this is 5 bytes less than above)
    machine.deepsleep(100)  # Sleep for 100 milliseconds - causes esp32 to reset
    time.sleep(150)
    machine.reset()

def reason(shell, cmdenv):
    import machine
    r = machine.reset_cause()
    print(shell.get_desc(26).format(r,shell.get_desc(20+r))) # CPU last reset reason {}: {} reset


def echo(shell, cmdenv):
    print( cmdenv['line'].split(' ', 1)[1] if ' ' in cmdenv['line'] else '') # " ".join(cmdenv['args'][1:])

def free(shell, cmdenv):
    try:
        gc.collect()
        total_memory = gc.mem_alloc() + gc.mem_free()
        free_memory = gc.mem_free()
        used_memory = gc.mem_alloc()
        #print(f"Total Memory: {total_memory} bytes")
        #print(f"Used Memory: {used_memory} bytes")
        #print(f"Free Memory: {free_memory} bytes")
        print(shell.get_desc(81).format(total_memory,used_memory,free_memory))
    except Exception as e:
        shell._ee(cmdenv, e)  # print(f"free: {e}")


def man(shell,cmdenv):
    if len(cmdenv['args']) > 1:
        keyword = cmdenv['args'][1]
        description = shell.get_desc(keyword)
        if description:
            print(shell.subst_env(f"${{WHT}}{keyword}${{NORM}} - " + description)) # we deliberately want the description $VARS to be expanded
        else:
            print(shell.get_desc(1).format(keyword))       # f"No manual entry for {keyword}"
    else:
        print(shell.get_desc(2))                       # "Usage: man [keyword]"


def _iter_cmds():
    for mod in ["sh0", "sh1", "sh2", "sh3"]:
        gc.collect()
        module = __import__(mod)
        for name in dir(module):
            if not name.startswith("_"):
                obj = getattr(module, name)
                if callable(obj):
                    yield name
        if mod != "sh1":
            del sys.modules[mod]
        gc.collect()


def help(shell, cmdenv):
    try:
        commands = []
        for mod in ["sh0", "sh1", "sh2", "sh3"]:
            gc.collect()
            module = __import__(mod)
            for name in dir(module):
                if not name.startswith("_"):
                    obj = getattr(module, name)
                    if callable(obj):
                        commands.append(name)
            if mod != "sh1":
                del sys.modules[mod]
            gc.collect()

        if cmdenv.get('args', [])[1:] == ["all"]:
            for cmd in sorted(commands):
                #print(f"Manual for {cmd}:")
                man(shell, {'args': ['man', cmd]})
                print()
        else:
            print("Available commands:")
            for cmd in sorted(commands):
                print(f"  {cmd}")
    except Exception as e:
        shell._ee(cmdenv, e)  # print(f"help: {e}")


def which(shell, cmdenv):
    if len(cmdenv['args']) < 2:
        shell._ea(cmdenv)
        return

    command = cmdenv['args'][1]

    # Check for inbuilt commands
    try:
        for cmd in _iter_cmds():
            if command == cmd:
                print(f"{command}: (inbuilt)")
                return
    except Exception as e:
        print(f"Error checking inbuilt commands: {e}")

    # Check if the argument contains a "/" or "./" prefix and if it exists as a file
    if "/" in command or command.startswith("./"):
        try:
            os.stat(command)
            print(command)
            return
        except OSError:
            pass

    # Check /bin/ and /lib/ directories for .py or .mpy files
    for directory in ["/bin", "/lib"]:
        for ext in ["mpy", "py"]: # cpy runs the .mpy in preference
            path = f"{directory}/{command}.{ext}"
            try:
                os.stat(path)
                print(path)
                return
            except OSError:
                pass

    # If no match found
    print(f"{command}: command not found")


def run(shell,cmdenv):
    if len(cmdenv['args']) < 2:
        shell._ea(cmdenv)
        return

    file_path = cmdenv['args'][1]

    in_docstring = False
    block = ""
    extra_iteration = False

    with open(file_path, 'r') as f:
        while True:
            if not extra_iteration:
                line = f.readline()
                if not line:
                    extra_iteration = True
                    line = '\n'  # Trigger the final block execution
            else:
                break

            stripped_line = line.strip()

            if in_docstring:
                if stripped_line.endswith('"""') or stripped_line.endswith("'''"):
                    in_docstring = False
                continue

            if stripped_line.startswith('"""') or stripped_line.startswith("'''"):
                in_docstring = True
                continue

            if '#' in line:
                line = line.split('#', 1)[0]

            if line.strip():
                block += line + '\n'
                try:
                    exec(block)
                    block = ""
                except SyntaxError:
                    # If compile fails, continue adding lines to the block
                    continue
                #except Exception as e:
                #    print(f"Error executing block: {e}")
                #    break



# def test(shell,cmdenv):
# 
#     # test arg parsing
#     test_cases = [
#         r'ls --test=5 -abc "file name with spaces" $HOSTNAME $HOME | grep "pattern" > output.txt',
#         r'sort -n -k2,3 < input.txt',
#         r'echo `ls -a` | sort -r',
#         r'echo `ls` | sort -r',
#         r'ls $(echo out)',
#         r'echo $(sort $(echo "-r" `echo - -n`) -n)'
#     ]
#     test_cases = [ r'alias dir="ls -Flatr"' ,  r'alias dir="echo $RED hime $NORM"', r"alias dir='echo $RED hime $NORM'", ]
# 
#     for command_line in test_cases:
#         print(f"\n\033[32;1mTest case: {command_line}\033[0m")
#         cmds = shell.parse_command_line(command_line)
#         for i, cmdenv in enumerate(cmds):
#             print(f"Command {i + 1}:")
#             print("  Line:", cmdenv['line'])
#             print("  Switches:", cmdenv['sw'])
#             print("  Arguments:", cmdenv['args'])
#             print("  Redirections:", cmdenv['redirections'])
#             print("  Pipe from:", cmdenv['pipe_from'])
#         print()
#         gc.collect()
# 
#     return "ok\n"
# 
# def run2(shell, cmdenv):
#     if len(cmdenv['args']) < 2:
#         shell._ea(cmdenv)
#         return
# 
#     file_path = cmdenv['args'][1]
# 
#     in_docstring = False
#     block = ""
#     extra_iteration = False
#     open_brackets = 0
#     open_parentheses = 0
#     open_braces = 0
#     in_quote = False
#     quote_char = ''
# 
#     def is_in_string(line, in_quote, quote_char):
#         escape = False
#         for char in line:
#             if char == '\\' and not escape:
#                 escape = True
#             elif char == quote_char and not escape:
#                 in_quote = not in_quote
#             else:
#                 escape = False
#         return in_quote
# 
#     with open(file_path, 'r') as f:
#         while True:
#             if not extra_iteration:
#                 line = f.readline()
#                 if not line:
#                     extra_iteration = True
#                     line = '\n'  # Trigger the final block execution
#             else:
#                 break
# 
#             stripped_line = line.strip()
# 
#             # Handle docstrings
#             if in_docstring:
#                 if stripped_line.endswith('"""') or stripped_line.endswith("'''"):
#                     in_docstring = False
#                 continue
# 
#             if stripped_line.startswith('"""') or stripped_line.startswith("'''"):
#                 in_docstring = True
#                 continue
# 
#             # Check for string literals and handle comments safely
#             if not in_quote:
#                 temp_line = ''
#                 for i, char in enumerate(line):
#                     if char in ('"', "'"):
#                         if not in_quote:
#                             in_quote = True
#                             quote_char = char
#                         elif quote_char == char and (i == 0 or line[i-1] != '\\'):
#                             in_quote = False
#                     if not in_quote and char == '#':
#                         temp_line = line[:i]
#                         break
#                     temp_line += char
#                 line = temp_line
# 
#             # Remove trailing comments outside string literals
#             stripped_line = line.strip()
#             
#             if not stripped_line and not extra_iteration:
#                 continue
# 
#             block += line
# 
#             # Track open quotes
#             in_quote = is_in_string(line, in_quote, quote_char)
# 
#             if in_quote:
#                 continue
# 
#             # Track open brackets
#             open_brackets += line.count('[') - line.count(']')
#             open_parentheses += line.count('(') - line.count(')')
#             open_braces += line.count('{') - line.count('}')
# 
#             # Check if the line ends with a backslash indicating continuation
#             if stripped_line.endswith('\\'):
#                 continue
# 
#             # If we are inside a block, we shouldn't execute yet
#             if open_brackets > 0 or open_parentheses > 0 or open_braces > 0 or stripped_line.endswith(':'):
#                 continue
# 
#             try:
#                 exec(block)
#                 block = ""
#             except SyntaxError:
#                 # If compile fails, continue adding lines to the block
#                 continue
#             #except Exception as e: # this interferes with errors in the original code
#             #    print(f"Error executing block: {e}")
#             #    break


def edit(shell, cmdenv):
    if len(cmdenv['args']) < 2:
        shell._ea(cmdenv)  # print("cat: missing file operand")
    else:
        try:
            import pye
            pye.pye(cmdenv['args'][1])
            del sys.modules['pye']
        except Exception as e:
            shell._ee(cmdenv, e)  # print(f"edit: {e}")


def cat(shell, cmdenv):
    if len(cmdenv['args']) < 2:
        shell._ea(cmdenv)  # print("cat: missing file operand")
    else:
        for path in cmdenv['args'][1:]:
            try:
                with open(path, 'rb') as file:
                    while True:
                        chunk = file.read(64)
                        if not chunk:
                            break
                        print(chunk.decode('utf-8'), end='')
            except Exception as e:
                shell._ee(cmdenv, e)  # print(f"cat: {e}")


def alias(shell, cmdenv):
    if len(cmdenv['args']) < 2:
        cat(shell, {'sw': {}, 'args': ['alias', '/settings.toml']}) # all aliases are stored in /settings.toml
        #shell._ea(cmdenv)
        return
    if "=" not in cmdenv['line']:
        print(shell._rw_toml('r',[cmdenv['args'][-1]])) # print existing
    else:
        key, value = cmdenv['line'].split(' ', 1)[1].strip().split('=', 1) # discard the prefix. Note that the = is not allowed to have spaces.
        shell._rw_toml('w', [key], value)

def export(shell, cmdenv):
    alias(shell, cmdenv)  # same as alias
def set(shell, cmdenv):
    alias(shell, cmdenv)  # same as alias

        
# Test or create a shadow password
def _chkpass(shell, op, pwd, cur=None): # Caution: this must live in sh1.py (called from sh.py)
    import ubinascii
    import uhashlib
    if op == 'chk':
        stored_data = cur.split('$')
        if stored_data[1] != '5':
            print(shell.get_desc(50)) # Unsupported hash algorithm in existing password.  Expected linux shadow format 5 (salted sha256)
            return
        hasher = uhashlib.sha256()
        hasher.update(stored_data[2].encode() + pwd.encode()) # Hash the input password with the stored salt
        return ubinascii.b2a_base64(hasher.digest()).decode().strip() == stored_data[3] # check it matched the current password
    else: # hash and return new password
        salt = ubinascii.b2a_base64(os.urandom(32)).decode().strip()
        hasher = uhashlib.sha256()
        hasher.update(salt.encode() + pwd.encode())
        return '$5${}${}$'.format(salt, ubinascii.b2a_base64(hasher.digest()).decode().strip())

def _readpw(prompt):
    p=''
    print(prompt,end='')
    while True:
        c = sys.stdin.read(1) # wrong call - should be shell.cio.something?
        if c == '\r' or c == '\n':  # End of input
            break
        if c:
            p +=c
            sys.stdout.write('*')
    return p

def passwd(shell, cmdenv):
    import ubinascii
    import uhashlib
    cur = shell._rw_toml('r', ['PASSWORD']) # password (used by telnetd etc) lives in /settings.toml key named PASSWORD
    if cur:
        pwd = _readpw(shell.get_desc(44)) # Enter current password:
        print('')
        if not _chkpass(shell,'chk',pwd,cur):
            import time
            print(shell.get_desc(47)) # Wrong current password
            time.sleep(2)
            return False

    pwd = _readpw(shell.get_desc(45)) # Enter new password:
    rpt = _readpw(shell.get_desc(46)) # Repeat new password:
    if pwd != rpt:
        print(shell.get_desc(49)) # Repeat password did not match
    else:
        #if pwd=='':
        #    shell._rw_toml('w', 'PASSWORD', value=None)
        #else:
        shell._rw_toml('w', ['PASSWORD'], value=_chkpass(shell, 'create', pwd))
        print(shell.get_desc(48)) # New password saved in /settings.toml


def telnetd(shell, cmdenv): # usage: telnetd --port=23
    shell.cio.telnetd(shell,cmdenv['sw'].get('port', 23)) # tell our shell to open up the listening socket


def sort(shell,cmdenv):  # 53 bytes
    return "\n".join(sorted(cmdenv['args'][1:], reverse='-r' in cmdenv['sw']))


def clear(shell, cmdenv):
    print("\033[2J\033[H", end='')  # ANSI escape codes to clear screen


def cls(shell, cmdenv):
    print("\033[2J", end='')  # ANSI escape code to clear screen

   
""" Unused at present

def _termtype(shell, cmdenv): # +50, -58 bytes
    print("\033[c\033[>0c", end='')  # get type and extended type of terminal. responds with: 1b 5b 3f 36 32 3b 31 3b 32 3b 36 3b 37 3b 38 3b 39 63    1b 5b 3e 31 3b 31 30 3b 30 63
    #                                                                                         \033[?62;1;2;6;7;8;9c (Device Attributes DA)             \033[>1;10;0c (Secondary Device AttributesA)
    # 62: VT220 terminal.  1: Normal cursor keys.  2: ANSI terminal.  6: Selective erase.  7: Auto-wrap mode.  8: XON/XOFF flow control.  9: Enable line wrapping.
    # 1: VT100 terminal.  10: Firmware version 1.0.  0: No additional information.

def _scrsize(shell, cmdenv): # 70 bytes
    print("\033[s\0337\033[999C\033[999B\033[6n\r\033[u\0338", end='')  # ANSI escape code to save cursor position, move to lower-right, get cursor position, then restore cursor position: responds with \x1b[130;270R
    #ng: print("\033[18t", end='')  # get screen size: does nothing

"""
