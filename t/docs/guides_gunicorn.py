import Pyjo.IOLoop
import Pyjoyment.Command.Author.generate.dockerfile
import Pyjoyment.Command.prefork
import Pyjoyment.Command.prethread

from Pyjo.File import curfile
from Pyjo.Test import *

import pathlib
import re


# The table of docs/guides/gunicorn.rst, whose options and variables are the ones of the commands, and its numbers
GUIDE = curfile().dirname().dirname().sibling('docs', 'guides', 'gunicorn.rst').slurp().decode()
TOOLKIT = pathlib.Path(curfile().dirname().dirname().sibling('Pyjo').to_str())
rows = re.findall(r'^    \* - (.+?)\n      - (.+?)(?=\n    \* |\n\n)', GUIDE, re.M | re.S)
usages = {
    'prefork': Pyjoyment.Command.prefork.object.usage,
    'prethread': Pyjoyment.Command.prethread.object.usage,
    'dockerfile': Pyjoyment.Command.Author.generate.dockerfile.object.usage,
}


def options(usage):
    # The short and the long names of the options of a usage
    return dict(re.findall(r'^\s+(-\w), --([\w-]+)', usage, re.M))


with subtest('Options'):
    is_ok(rows[0], ('gunicorn', 'Pyjoyment'), 'header')
    prefork = options(usages['prefork'])
    for gunicorn, pyjoyment in rows[1:]:
        usage = usages['prethread' if 'prethread' in pyjoyment else 'prefork']
        if 'generate dockerfile' in pyjoyment:
            usage = usages['dockerfile']
        for short in re.findall(r'(?:``|\s)(-\w)\b', pyjoyment):
            like_ok(usage, re.compile(rf'^\s+{short}, --', re.M), f'{gunicorn}: {short}')
        for name in re.findall(r'PYJO_(\w+)', pyjoyment):
            long = name.lower().replace('_', '-')
            # The variable of an option, or one that the toolkit reads
            if long not in prefork.values():
                found = any(f'PYJO_{name}' in file.read_text() for file in TOOLKIT.rglob('*.py'))
                ok(found, f'{gunicorn}: PYJO_{name} of the toolkit')
            else:
                pass_ok(f'{gunicorn}: PYJO_{name} of --{long}')

with subtest('Restarts of workers'):
    like_ok(
        usages['prefork'],
        r'-a, --accepts <number> +Number of connections for workers to\n +accept, less up to half at random,',
        'jitter in the usage',
    )
    numbers = re.search(r'``-a 1000`` replaces a\nworker after (\d+) to (\d+) connections, (\d+) on average', GUIDE)
    is_deeply_ok([int(n) for n in numbers.groups()], [500, 1000, 750], '-a 1000')
    # --max-requests 1000 --max-requests-jitter 100 is 1000 to 1100, 1050 on average, as -a 1400 is 700 to 1400
    low = 1400 - 1400 // 2
    is_ok((low + 1400) / 2, (1000 + 1100) / 2, '-a 1400')
    like_ok(GUIDE, r'``-a 1400``, 700 to 1400', '-a 1400 in the guide')
    loop = Pyjo.IOLoop.new(max_accepts=1000)
    ok(500 <= loop.max_accepts <= 1000, 'max_accepts of the event loop')

done_testing()
