#!/usr/bin/env python3
import os
from pathlib import Path
import sys

root = Path(__file__).parent
venv_python = root / '.venv' / 'bin' / 'python'
if not os.environ.get('DJANGOX_CONTROL_REEXEC') and venv_python.exists():
    os.environ['DJANGOX_CONTROL_REEXEC'] = '1'
    command = venv_python.as_posix()
    os.execv(command, [command, __file__, *sys.argv[1:]])

from djangox.deploy.control import app


if __name__ == '__main__':
    os.chdir(root)
    app()
