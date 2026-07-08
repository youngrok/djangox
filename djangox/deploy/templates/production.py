from pathlib import Path
import sys

sys.path.append(Path(__file__).parent.as_posix())

from conf import Conf
from djangox.deploy.ssh import connect
from djangox.deploy.ssh import ssm_port_forwarded_servers


target = sys.argv[1] if __name__ == '__main__' and len(sys.argv) > 1 else None
servers = ssm_port_forwarded_servers(Conf, target not in ['list', 'servers'])


if __name__ == '__main__':
    raise SystemExit(connect(Conf, servers, target))
