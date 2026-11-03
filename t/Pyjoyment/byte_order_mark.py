import Pyjo.File
import Pyjo.Template
import Pyjo.Test.Pyjo
import Pyjoyment

from Pyjo.Test import *


# Not in Mojolicious: the files that Windows tools write, with a byte order mark of UTF-8, or in UTF-16 with one, as
# Windows PowerShell writes them, whose byte order mark switches UTF-8 to its encoding, where Mojo decodes it as U+FEFF
ENCODINGS = {
    'UTF-8': lambda text: text.encode('UTF-8'),
    'UTF-8 with a byte order mark': lambda text: b'\xef\xbb\xbf' + text.encode('UTF-8'),
    'UTF-16LE with a byte order mark': lambda text: b'\xff\xfe' + text.encode('UTF-16LE'),
    'UTF-16BE with a byte order mark': lambda text: b'\xfe\xff' + text.encode('UTF-16BE'),
    'UTF-16LE with a byte order mark and CRLF': lambda text: (
        b'\xff\xfe' + text.replace('\n', '\r\n').encode('UTF-16LE')
    ),
}

CONFIGS = {
    'Config': ('conf', "{'name': '♥', 'list': [1, 2]}\n"),
    'JSONConfig': ('json', '{"name": "♥", "list": [1, 2]}\n'),
    'YAMLConfig': ('yml', 'name: ♥\nlist:\n  - 1\n  - 2\n'),
    'TOMLConfig': ('toml', 'name = "♥"\nlist = [1, 2]\n'),
    'INIConfig': ('ini', 'name = ♥\n[list]\na = 1\n'),
}

dir = Pyjo.File.tempdir()

with subtest('Configuration files'):
    for plugin, (extension, text) in CONFIGS.items():
        for encoding, data in ENCODINGS.items():
            file = dir.child(f'myapp.{extension}').spew(data(text))
            config = Pyjoyment.new().plugin(plugin, file=file.to_str())
            is_ok(config['name'], '♥', f'{plugin} of {encoding}')

with subtest('Template files'):
    for encoding, data in ENCODINGS.items():
        file = dir.child('hello.ep').spew(data('<p><%= "♥" %></p>\n'))
        # The line endings of a template file stay
        newline = '\r\n' if 'CRLF' in encoding else '\n'
        is_ok(Pyjo.Template.new().render_file(file), f'<p>♥</p>{newline}', f'render_file of {encoding}')

        templates = dir.child('templates').make_path()
        templates.child('ep.html.ep').spew(data('<p><%= "♥" %></p>\n'))
        templates.child('py.html.py').spew(
            data('from Pyjo.String.Template import t\n\n\ndef render(c):\n    return t("<p>{heart}</p>", heart="♥")\n')
        )
        app = Pyjoyment.new()
        app.log.level = 'fatal'
        app.renderer.paths = [templates.to_str()]
        app.routes.get('/ep', {'template': 'ep'})
        app.routes.get('/py', {'template': 'py'})
        test = Pyjo.Test.Pyjo.new(app)
        test.get_ok('/ep').status_is(200).content_is(f'<p>♥</p>{newline}', f'EP of {encoding}')
        test.get_ok('/py').status_is(200).content_is('<p>♥</p>', f'PyRenderer of {encoding}')

done_testing()
