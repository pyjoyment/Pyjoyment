import os
import sys


# The mock of t/lib/OneLiner.py for python -m Pyjo, which Python imports at its start from PYTHONPATH, for a shell that
# runs the interpreter of python itself, as PowerShell, whose functions would not pass the standard input of a pipe on
if __name__ == '__main__':
    from Pyjo.Test import plan

    plan(skip_all='helper module, not a test')
else:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    import OneLiner

    OneLiner.setup()
