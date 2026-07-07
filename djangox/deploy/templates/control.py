#!/usr/bin/env python3
import os
from pathlib import Path

root = Path(__file__).parent

from djangox.deploy.control import app


if __name__ == '__main__':
    os.chdir(root)
    app()
