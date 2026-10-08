"""Run recalc with Windows socket compatibility patch."""
import socket
import sys

# Patch for Windows (no AF_UNIX)
if not hasattr(socket, 'AF_UNIX'):
    socket.AF_UNIX = None

skills_path = r'C:\Users\geoff\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\594e699b-7b54-4142-b821-eca5ebb2d32c\df8960fd-9154-4194-8e6c-8ad1c53133c8\skills\xlsx\scripts'
sys.path.insert(0, skills_path)

# Patch soffice module before recalc imports it
import office.soffice as soffice_mod


def patched_get_soffice_env():
    import os
    return os.environ.copy()

soffice_mod.get_soffice_env = patched_get_soffice_env

# Now run recalc
target = r'C:\Users\geoff\OneDrive\Brookfield Gardens\Brookfield_Gardens_Financial_Model.xlsx'
sys.argv = ['recalc.py', target, '120']

import recalc

recalc.main()
