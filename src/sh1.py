# sh1.py

__version__ = '1.0.20240626'  # Major.Minor.Patch

# Created by Chris Drake.
# Linux-like shell interface for CircuitPython.  https://github.com/gitcnd/cpy_shell
# 
# This is a separate module for holding some commands.
# it is separate to save RAM

import gc
import sys
import os



def man(shell,cmdenv):
    if len(cmdenv['args']) > 1:
        keyword = cmdenv['args'][1]
        description = shell.get_desc(keyword)
        if description:
            print(shell.subst_env(f"\n${{WHT}}{keyword}${{NORM}} - " + description)) # we deliberately want the description $VARS to be expanded
        else:
            print(shell.get_desc('1').format(keyword))       # f"No manual entry for {keyword}"
    else:
        print(shell.get_desc('2'))                       # "Usage: man [keyword]"


def _iter_cmds():
    for mod in ["sh0", "sh1", "sh2"]:
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
        for mod in ["sh0", "sh1", "sh2"]:
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


def test(shell,cmdenv):

    # test arg parsing
    test_cases = [
        r'ls --test=5 -abc "file name with spaces" $HOSTNAME $HOME | grep "pattern" > output.txt',
        r'sort -n -k2,3 < input.txt',
        r'echo `ls -a` | sort -r',
        r'echo `ls` | sort -r',
        r'ls $(echo out)',
        r'echo $(sort $(echo "-r" `echo - -n`) -n)'
    ]
    test_cases = [ r'alias dir="ls -Flatr"' ,  r'alias dir="echo $RED hime $NORM"', r"alias dir='echo $RED hime $NORM'", ]

    for command_line in test_cases:
        print(f"\n\033[32;1mTest case: {command_line}\033[0m")
        cmds = shell.parse_command_line(command_line)
        for i, cmdenv in enumerate(cmds):
            print(f"Command {i + 1}:")
            print("  Line:", cmdenv['line'])
            print("  Switches:", cmdenv['sw'])
            print("  Arguments:", cmdenv['args'])
            print("  Redirections:", cmdenv['redirections'])
            print("  Pipe from:", cmdenv['pipe_from'])
        print()
        gc.collect()

    return "ok\n"


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


def run2(shell, cmdenv):
    if len(cmdenv['args']) < 2:
        shell._ea(cmdenv)
        return

    file_path = cmdenv['args'][1]

    in_docstring = False
    block = ""
    extra_iteration = False
    open_brackets = 0
    open_parentheses = 0
    open_braces = 0
    in_quote = False
    quote_char = ''

    def is_in_string(line, in_quote, quote_char):
        escape = False
        for char in line:
            if char == '\\' and not escape:
                escape = True
            elif char == quote_char and not escape:
                in_quote = not in_quote
            else:
                escape = False
        return in_quote

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

            # Handle docstrings
            if in_docstring:
                if stripped_line.endswith('"""') or stripped_line.endswith("'''"):
                    in_docstring = False
                continue

            if stripped_line.startswith('"""') or stripped_line.startswith("'''"):
                in_docstring = True
                continue

            # Check for string literals and handle comments safely
            if not in_quote:
                temp_line = ''
                for i, char in enumerate(line):
                    if char in ('"', "'"):
                        if not in_quote:
                            in_quote = True
                            quote_char = char
                        elif quote_char == char and (i == 0 or line[i-1] != '\\'):
                            in_quote = False
                    if not in_quote and char == '#':
                        temp_line = line[:i]
                        break
                    temp_line += char
                line = temp_line

            # Remove trailing comments outside string literals
            stripped_line = line.strip()
            
            if not stripped_line and not extra_iteration:
                continue

            block += line

            # Track open quotes
            in_quote = is_in_string(line, in_quote, quote_char)

            if in_quote:
                continue

            # Track open brackets
            open_brackets += line.count('[') - line.count(']')
            open_parentheses += line.count('(') - line.count(')')
            open_braces += line.count('{') - line.count('}')

            # Check if the line ends with a backslash indicating continuation
            if stripped_line.endswith('\\'):
                continue

            # If we are inside a block, we shouldn't execute yet
            if open_brackets > 0 or open_parentheses > 0 or open_braces > 0 or stripped_line.endswith(':'):
                continue

            try:
                exec(block)
                block = ""
            except SyntaxError:
                # If compile fails, continue adding lines to the block
                continue
            #except Exception as e: # this interferes with errors in the original code
            #    print(f"Error executing block: {e}")
            #    break



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


def _write_toml(shell, key, value=None):
    import sh0  # load mv command
    ifn = '/settings.toml'
    tmp = '/settings_new.toml'

    with open(ifn, 'r') as infile, open(tmp, 'w') as outfile:
        in_multiline = False
        extra_iteration = 0
        line = ''

        while True:
            #print(f"L extra_iteration={extra_iteration} n_multiline={in_multiline} ")
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

            #print(f"line='{line}'")

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
                        if value == '':
                            line='' # Delete the variable
                            continue
                        else:
                            if value[0] in '+-.0123456789"\'': # Update the variable
                                line = f'{key} = {value}\n'
                            else:
                                line = f'{key} = "{value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")}"\n' 
                            key=None

            in_multiline = False
            #print(f"wrote '{line}'")
            outfile.write(line)
            line=''

    #print("done.")

    # Replace old settings with the new settings
    sh0.mv(shell, {'sw': {}, 'args': ['mv', ifn, '/settings_old.toml']})
    sh0.mv(shell, {'sw': {}, 'args': ['mv', tmp, ifn]})
    del sys.modules['sh0']


def alias(shell, cmdenv):
    if len(cmdenv['args']) < 2:
        cat(shell, {'sw': {}, 'args': ['alias', '/settings.toml']}) # all aliases are stored in /settings.toml
        #shell._ea(cmdenv)
        return
    key, value = cmdenv['line'].split(' ', 1)[1].strip().split('=', 1) # discard the prefix. Note that the = is not allowed to have spaces.
    _write_toml(shell,key, value)

def export(shell, cmdenv):
    alias(shell, cmdenv)  # same as alias
def set(shell, cmdenv):
    alias(shell, cmdenv)  # same as alias

def create(shell, cmdenv):
    if len(cmdenv['args']) < 2:
        shell._ea(cmdenv)  # print("cat: missing file operand")
    else:
        path = cmdenv['args'][1]
        try:
            with open(path, 'wb') as file:
                print("Enter text to write to the file. Press ^D (Ctrl+D) to end.")
                while True:
                    try:
                        line = input()
                        file.write(line.encode('utf-8') + b'\n')
                    except EOFError:
                        break
        except Exception as e:
            shell._ee(cmdenv, e)  # print(f"cat: {e}")

