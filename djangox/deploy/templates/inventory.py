from pathlib import Path
import sys

sys.path.append(Path(__file__).parent.as_posix())

from production import print_servers
from production import servers


if __name__ == '__main__':
    print_servers()
