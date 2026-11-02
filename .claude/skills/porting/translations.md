# Translations of Perl into Python

Perl and Python differ in a few places that a port must translate rather than
copy:

- A global inline regex flag such as `(?i)` is only valid at the start of a
  Python pattern; in the middle of one, use the scoped form `(?i:...)`.
- Perl's `weaken` is ported as `weakref.proxy`. Check whether the object
  behind a proxy still exists with `Pyjo.Util.isalive`; `dir(proxy)` and
  `bool(proxy)` raise `ReferenceError` for a dead proxy. A `list` cannot be
  weakly referenced, so the parent of a node in the tree of `Pyjo.DOM` is a
  plain reference, and the garbage collector frees the cycles.
- `"\$"` in a double-quoted Perl string is a plain `$`; in Python it keeps the
  backslash.
- Overloaded operators become special methods: `""` is `__str__`, `bool` is
  `__bool__`, and `@{}` is `__getitem__`, `__iter__` and `__len__`.
  `to_string` is `to_str`, the counterpart of `to_bytes` in
  `Pyjo.String.Mixin`, and `to_unsafe_string` is `to_unsafe_str`.
  `to_hash` is `to_dict`, `to_array` is `to_list`, and a flat list of names
  and values, like the pairs of `Mojo::Parameters`, is a list of
  `(name, value)` tuples.
- Mojo's attributes and getter/setter methods are attributes and properties
  (`url.host`, `url.path`). A method without arguments that describes the
  object, like `is_abs` or `protocol`, is a property too: as a method,
  `if url.is_abs:` would always be true. A method that builds something,
  like `to_str`, `clone` or `names`, stays a method.
- Mojo's forms of an accessor with a list of arguments, an array reference
  and a hash reference are a `tuple`, a `list` and a `dict`:
  `url.query = ('a', 1)` replaces the parameters, `['a', 1]` appends
  them, and `{'a': 1}` merges them, as `query(a => 1)`, `query([a => 1])`
  and `query({a => 1})` do.
- A name followed by its data in Mojo's list of arguments, as a generator of
  `tx` in `Mojo::UserAgent::Transactor` with its options
  (`form => {a => 'b'}, charset => 'UTF-8'`), is a keyword argument
  (`form={'a': 'b'}, charset='UTF-8'`), and a hash reference of headers or
  the content before it are positional arguments. A callback that Mojo takes
  after them, as the request methods of `Mojo::UserAgent` do, is the keyword
  argument `cb` (`ua.get(url, {'DNT': 1}, form={'a': 'b'}, cb=cb)`), or the last
  positional argument, as the ported tests pass it.
- A Perl string of characters is a `str`, and bytes in Python are `bytes`,
  encoded with the charset of the module. Perl keeps bytes that do not decode
  as a byte string, which is a `str` of the characters 0-255 in Python:
  `.decode('latin-1')`.
  HTTP headers are such characters too, as `http.client` has them: bytes
  from the wire are decoded as ISO-8859-1.
- An environment variable `MOJO_*` is `PYJO_*`, and so are the ones that
  `prove` sets for the tests, as `HARNESS_ACTIVE`, which `Pyjo.Prove` sets as
  `PYJO_HARNESS_ACTIVE`.
- A name that Mojolicious takes from somewhere else, as `Mojo::Server::Hypnotoad`
  and `Mojo::Server::Morbo` are named after characters of Futurama, is a name
  that says what the module does, `Pyjo.Server.Hot` and `Pyjo.Server.Reload`,
  with a `# Renamed from Mojolicious:` comment; so are its environment
  variables (`PYJO_RELOAD_BACKEND`) and the jokes of its documentation. A
  script of Mojolicious, as `script/morbo`, is a `main` function of the module,
  a `pyjo-` command in `[project.scripts]` of `pyproject.toml` (`pyjo-reload`)
  and `python -m` of the module. It parses its options with `getopt` of
  `Pyjo.Util`, as the script does with the one of `Mojo::Util`, with the
  target `Pyjo.GetOpt.env` for an option that the script binds to `$ENV{...}`,
  as `PYJO_HOT_FOREGROUND` for `--foreground`, and its usage,
  which the script has in its SYNOPSIS, is the section of the docstring of the
  module with the name of the command, which `extract_usage(section=...)`
  reads, so that the help of the command and its documentation are one text.
  `script/mojo`, the command line interface of `Mojo::HelloWorld`, is `pyjo`,
  the `main` of `Pyjoyment.Commands`, and `python -m Pyjoyment`.
- A command of Mojolicious, as `Mojolicious::Command::daemon`, is a module of
  the package `Pyjoyment.Command` with the name of the command, as
  `Pyjoyment.Command.daemon`, and its usage, which Mojo extracts from the
  section SYNOPSIS of its POD, is the first literal block of the docstring of
  the module, which the class reads with `usage = extract_usage()`, with its
  options in a block that `format_usage` of `Pyjo.GetOpt` lays out, so that
  a new option needs no alignment by hand. Its
  options are parsed with `getopt` of `Pyjo.Util`, whose targets are a dict,
  as Python has no references to variables. The commands of the servers,
  `daemon` and `prefork`, parse them with `env_prefix='PYJO_'`, so that an
  option that is not given has the value of `PYJO_` and its name, as
  `PYJO_WORKERS`, the way Cobra and Viper of Go have it, which continues the
  variables that Mojo already has for some of them, as `MOJO_LISTEN` and
  `MOJO_INACTIVITY_TIMEOUT`; the environment of a container tunes the server
  without its command line. Other commands, as `get`, have no such
  variables, as `PYJO_METHOD` or `PYJO_VERBOSE` would surprise.
- PSGI is WSGI and ASGI: the command `psgi` is `wsgi`, and `asgi` is its
  counterpart, which return the application of `Pyjo.Server.WSGI` and
  `Pyjo.Server.ASGI`. `PYJO_WSGI` and `PYJO_ASGI` take the place of
  `PLACK_ENV`, as WSGI and ASGI have no environment variable of their own: a
  server imports the script of an application, which ends with
  `application = app.start()`, with its own arguments in `sys.argv`, so that
  the command has to be detected. The runtime of AWS Lambda imports the script
  the same way, and `AWS_LAMBDA_RUNTIME_API`, which it sets, detects the
  command `lambda`, whose module has the name of a keyword of Python, which
  only `importlib` imports. A script that runs as the main program with that
  variable, as the `bootstrap` of a custom runtime or the command of an image,
  is the runtime itself: the command finds the module that starts the
  application in the stack, outside of the frames of `Pyjo` and `Pyjoyment`,
  and runs the loop of the Runtime API when it is `__main__`, which
  `python -m MyApp` is too, and returns the handler for a runtime that imports
  the script otherwise.
- The generators of the command `generate` write projects for uv, where Mojo
  writes ones for ExtUtils::MakeMaker: `generate makefile` is
  `generate pyproject`, and `cpanify` is left out, as `uv publish` uploads to
  PyPI. An application is a package in the directory of its project, without
  `lib`, as `Pyjo.Prove -l` adds the current directory, and its
  `pyproject.toml` has no build system, as `uv init --app` makes it, since
  `Pyjo.Home` finds `templates` and `public` next to the package, which a
  wheel would leave behind; `MyApp/__main__.py` takes the place of
  `script/my_app`. A script of `Pyjoyment.Lite` has its dependencies in the
  `pyproject.toml` of `generate pyproject` next to it, as in Mojo, or in the
  inline metadata of PEP 723, which `generate dockerfile` installs where
  there is no `pyproject.toml`. A plugin is a distribution, built with
  hatchling, whose wheel has only its module, without the `__init__.py` of
  the namespace `Pyjoyment.Plugin`, which `extend_path` keeps open. A
  namespace finds its parts through the `__path__` of its parent package, so
  `Pyjoyment/__init__.py` extends its own before it imports its subpackages.
  `generate lambda-zip` runs uv itself, as what it writes is the build of a
  function, not a file of the project: `uv python install` with `--no-bin`,
  without which uv links the interpreter of Linux into `~/.local/bin`, in the
  place of the `python3.X` of the machine; the dependencies of the inline
  metadata of a script with `uv export --script`, as `uv pip install -r` of a
  script ignores its `[tool.uv.sources]`, and the ones of a project without
  `uv.lock` with `uv pip install -r pyproject.toml`, as `uv export` would
  write the lock; and the Python of the machine, which gives the tags of the
  wheels and compiles the bytecode, with `+gil`, as a version alone finds a
  free-threaded build too. `/var/task` and `/opt` are read-only, so the
  bytecode is compiled before, with the invalidation mode `unchecked-hash`,
  as a ZIP keeps the times of files in steps of two seconds, which the check
  of a timestamp does not match, and without it each cold start compiles
  every module it imports again, several times slower. The entries of a ZIP
  have their modes, as a file of Windows has none, no symbolic links, which
  the interpreter does not need, and fixed times, so that the same input
  gives the same hash. For the same reason the bytecode is compiled with
  `PYTHONHASHSEED=0`, as a set of strings, as `x in {'http', 'https'}`, is
  marshalled in the order of their hashes, and `_sysconfigdata_*.py` gets the
  prefix of Python on Lambda, `/opt/python` or `/var/task/python`, in the
  place of the temporary directory that uv writes into it, which is taken
  from the directory of the full version, `cpython-3.15.0-…`, not from the
  link of the minor version that uv makes next to it. Pyjoyment goes to a layer
  of its own, `pyjoyment.zip`, in `python/lib/python3.X/site-packages`, which
  the `site` of the Python of `python.zip` puts in its path, and so does the
  runtime of Python of Lambda of the same version, so that the same bytes serve
  a custom runtime and the runtime of Python, and a layer that is published
  once serves every function of that Python. The runtime of Python adds the
  directories of the layers in its `/var/runtime/bootstrap.py`, and only when
  `PYTHONPATH` is not set, so a function with `PYTHONPATH` does not get them,
  nor a wrapper of `AWS_LAMBDA_EXEC_WRAPPER`, which runs in the place of that
  bootstrap, nor `docker exec` of a test: the function of such a wrapper names
  the site-packages in `PYTHONPATH`. A file of the application that starts
  with `#!`, as such a wrapper, is executable in the ZIP, by a rule on its
  content, which gives the same bytes on Windows, whose files have no modes.
- `ojo` is the functions of the package `Pyjo`, which `from Pyjo import *`
  imports, and `perl -Mojo -E` is `python -m Pyjo`. A function imports the
  modules it uses when it is called, as every `import Pyjo.X` runs
  `Pyjo/__init__.py`. Its `u`, PUT, is `w`, as `u` is for characters, as in
  `Pyjo.String.Unicode`. `z`, which ojo does not have, is the builder of
  `Pyjo.JSON.Schema`, as `z` of zod: an object that imports the module when a
  method of the builder is read, as the class itself would need the import
  when `from Pyjo import *` runs, and that type checkers take for the class.
- Where Mojo uses an optional XS module for speed, as `Mojo::JSON` uses
  `Cpanel::JSON::XS`, the port uses the module of the standard library in its
  place and keeps the port of the pure-Perl code behind a `PYJO_NO_*`
  variable. Mojo's tests of the pure-Perl code set the variable, and those of
  the XS module run against the standard library.
- `TO_JSON` is `__json__`.
- A hash of Perl has no order, which `Mojo::JSON` makes up for by sorting the keys
  of an object, so that its output is the same each time. A `dict` keeps the order
  of its keys, which tells something, as the order of the parameters of a
  function in its JSON Schema, so `Pyjo.JSON`, `Pyjo.YAML` and `Pyjo.TOML` write
  the keys in that order, and sort them only with `sort_keys`.
- `Mojo::ByteStream` is `Pyjo.String.Unicode` for characters and
  `Pyjo.String.Bytes` for bytes. A Mojo test's `b(...)` is `u(...)` or
  `b(...)`, by what the string holds.
  Markup, which Mojo keeps from escaping as a `Mojo::ByteStream`, as a tag
  helper returns it, is `Pyjo.String.HTML`, `html(...)`: escaping leaves only
  what has the method `__html__`, so a string that `u()` or
  `Pyjo.Collection.join` makes is escaped.
- A function of `Mojo::Util`, and a method of `Mojo::ByteStream` or
  `Mojo::File`, is the one of `Pyjo.Util`, `Pyjo.String` or `Pyjo.File`, also
  in code of the framework that Mojo does not have, where the standard library
  would do the same: `b64_encode(data, '')` for
  `base64.b64encode(data).decode()`, `b64url_encode(data)` for
  `base64.urlsafe_b64encode(data).decode().rstrip('=')`, `sha1_sum`, `sha256_sum`,
  `hmac_sha256_sum`, `secure_compare`, `url_escape`, and
  `Pyjo.File.path(path).slurp()`, so that the framework does a thing one way
  and its values chain. The standard library stays where the function of
  Pyjoyment means something else: `b64_decode` leaves out what is not Base64,
  as `MIME::Base64` does, so a format that validates its Base64, as `!!binary`
  of YAML, decodes it with `base64.b64decode(..., validate=True)`.
- Perl code in a template of `Mojo::Template` is Python code in
  `Pyjo.Template`, and the templates of a Mojo test are translated with it:
  `@_` is `args`, a block of Perl in braces is a block of Python, with braces
  or with `:` and `end`, a statement modifier is a block of its own, and
  `begin` and `end` compile to a nested `def` that is defined before the
  statement that uses it, as a lambda cannot hold statements. The compiled
  code is not line for line the template, as the one of Mojo is, so a map
  gives the template lines of a traceback.
- An `ep` template is translated the same way: `$c` and `$self` are `c` and
  `self`, a value of the stash `$foo` is the variable `foo`, and a helper is
  a function, as `%= include('menubar')`. A helper that takes a block as its
  last argument, `content foo => begin`, closes its parenthesis after `end`:
  `%= content('foo', begin` and `% end)`. Python has one namespace where Perl
  has sigils, so a value of the stash hides the helper of its name, and the
  variable `c` hides the helper `c`; the template calls such a helper as a
  method of `c`, as `c.title('Welcome!')`.
- A tag helper takes the attributes of its tag as keyword arguments, after
  its positional ones, and a block of a template as the last positional
  argument, before them: `form_for login => (method => 'POST') => begin` is
  `%= form_for('login', begin` and `%= end, method='POST')`. An attribute that
  is a keyword of Python or has a dash goes with `**`, as
  `**{'class': 'menu'}`, and an attribute without a value is `None`. The
  attributes of an option or a group of `select_field` are a dict after its
  value, where Mojo takes a flat list of names and values.
- `use Mojolicious::Lite` is `from Pyjoyment.Lite import *`, which gives the
  module that imports it an application of its own, as Mojo makes one for the
  package that uses it: the functions are made for the module of the caller
  by `__getattr__` of `Pyjoyment.Lite` and kept in the module, so that a
  script that `load_app` runs again gets a new application. `get '/foo' =>
sub {...}` is `get('/foo', cb)` or the decorator `@get('/foo')`, as a route
  is a decorator of its callback, `group {...}` is `with group():`, and
  `app->start` is `app.start()`. The templates of the `__DATA__` section of
  a Lite script are in its docstring after a line `__DATA__`, as a variable
  at the end of the script comes after the code that serves them. Mojo makes
  the package a subclass of `Mojolicious` whose `new` returns its application,
  so that a route embeds it by its name, as `to('EmbeddedTestApp')`; Lite
  keeps such a class with the functions of the module, where the routes find
  it by the name of the module.
- `Test::Mojo` is `Pyjo.Test.Pyjo`, with the chains of methods of Mojo:
  `$t->get_ok('/')->status_is(200)` is `t.get_ok('/').status_is(200)`. Its
  attributes are attributes, so `$t->success(0)->or(...)` is an assignment
  followed by the call, and its handler gets the names of the functions of
  `Test::More`, as `is` and `is_deeply`, which the tests of Mojo check.
- A callback that Mojo calls with `$_` gets the element as its first
  argument. A method name in a string, as in `$collection->map('text')`, can
  name a property, which is how a Mojo attribute is ported.
- A method of `Mojo::Collection` that has the name of a `list` method, like
  `sort` and `reverse`, returns a new collection, as in Mojo, and
  `list.sort(collection)` sorts in place.
- `shift` and `unshift` of an array of Perl that is a queue, as the callbacks of
  `next_tick` of a reactor or the parts of a multipart form, are `popleft` and
  `extendleft` of a `collections.deque`, not `pop(0)` and an assignment to
  `[:0]` of a `list`, which move all the other items, so that a queue that the
  input makes long does not make the loop that empties it grow with its
  square. A queue that a limit keeps short, as the connections that
  `max_connections` keeps, stays a `list`.
- The four arguments of `substr` that cut the front of a buffer, as
  `substr $buffer, 0, $n, ''`, are `del buffer[:n]` of a `bytearray`, which
  CPython does without moving the rest, as Perl moves the start of the string,
  not a slice `buffer[n:]`, which copies the rest, and the buffer grows with
  `+=` of a `bytearray`, as `+=` of `bytes` copies the whole buffer too, so that
  a buffer of many pieces does not take the square of its length. A buffer that
  goes out, as `leftovers` of `Pyjo.Content`, is `bytes` of it.
- Perl's `split` is `Pyjo.String.Unicode.split`, not `str.split` or
  `re.split`: its pattern is a regular expression, a match of no length at
  the beginning makes no field, and the empty fields at the end are left out.
- `redo` in an `until` loop starts the body again without checking the
  condition. A `while` with `continue` checks it, so the port is a
  `while True:` inside an `if not ...:`.
- After a match of no length, Perl does not let the next `/gc` match be of no
  length at the same position, so `/\G\z/gc` fails right after
  `/\G\s*/gc` skipped nothing. A parser ported from Mojo that reports
  "before end of data" this way, as `Mojo::JSON` does, has to keep it where
  Mojo's tests expect it. A tokenizer that matches the text and then the tag
  of the same position in two matches, with a lazy `??` and this rule, has
  them as alternatives in Python.
- Python has no relative backreference like `\g{-2}`; a named group takes
  its place, and works also where the pattern is embedded in another one.
- Python's recursion limit is 1000 calls. A recursive parser that must reach
  a nesting depth like `Mojo::JSON`'s 512 makes one call for each level,
  not two.
- A function that works on bytes in Mojo, such as a checksum, Base64
  encoding, compression or `xor_encode`, takes `bytes`, and a Mojo test that
  passes it a literal like `'foo bar baz'` passes `b'foo bar baz'`.
- Perl's `\w` matches the combining marks of scripts such as Devanagari,
  Python's does not, so a regular expression that keeps word characters of
  any script tests the Unicode category of the character as well.
- Methods that Mojo makes in a loop with `monkey_patch`, such as the
  shortcuts of `Mojo::Headers`, are class attributes, one for each, made
  with a descriptor class.
- `None` is not `undef` everywhere: `time.gmtime(None)` is the current time,
  `gmtime(undef)` is the epoch. Python's `tm_wday` counts from Monday, Perl's
  from Sunday.
- A Perl scalar keeps the form it was given (`'1.0'` stays `'1.0'`), and a
  number stringifies without a trailing `.0`. A port converts input to `int`
  or `float`, and formats it the Perl way where the output depends on it.
  Where Mojo only stores and prints a value, like a parameter, the port stores
  it as a `str`.
- A Perl quirk that only a warning reveals is not ported. `undef` counts as `0`
  with a warning, so `Mojo::Date` reads an unknown month name as January;
  `Pyjo.Date` rejects the date.
- A flag that Mojo sets to `1` and leaves `undef` otherwise is `True` or
  `None`. A test of the end of a list, `is $cookies->[1], undef`, becomes
  `is_ok(len(cookies), 1)`, or `is_ok(collection.get(1), None)` for a
  `Pyjo.Collection`.
- A function or a method named after a keyword of Python gets a name that is
  not one, which the documentation uses, and the name with a trailing
  underscore is its alias, which the ported tests use, so that the diff of a
  newer Mojolicious applies to them: `raise` of `Mojo::Exception` is `throw`
  and `raise_`, and `finally` of `Mojo::Promise` is `lastly`, as Bluebird
  names it, and `finally_`; `continue` of `Mojolicious::Routes` and
  `Mojolicious::Controller` is `proceed` and `continue_`, and `or` of
  `Test::Mojo` is `otherwise` and `or_`. An attribute only
  gets the other name, as `not`
  of `Mojo::UserAgent::Proxy` is `no`, after `NO_PROXY`. The functions of
  `Pyjo.Test` are the exception: they have an `_ok` suffix, as `is_ok`.
- A name of a Perl package, as `Mojo::Exception` takes them, is a dotted name
  of a class in Python (`'MyApp.X.Foo'`), resolved by importing the longest
  prefix that is a module.
  A plugin or a controller that Mojolicious loads by its package name is the
  class that a module names `object`, as `Pyjoyment.Plugin.HeaderCondition`,
  or a class in a module, as `MyApp.Controller.Foo`.
- A helper of Mojolicious, which `Mojo::DynamicMethods` makes a method of the
  controller and the application, is a callable that `__getattr__` finds in
  the renderer, and a prefix of nested helpers is an attribute: `c.title('x')`,
  `c.log().debug(...)` and `c.reply.not_found()`.
- Perl's `@INC` is `sys.path`, and `%INC`, the files of the modules that
  are loaded, and the symbol table of packages are `sys.modules` and the
  `__file__` of a module, as `Pyjo.Home` and `Pyjo.Loader` use them; a module
  that is not loaded is not imported to find it.
- The `__DATA__` section of a Perl module is the `__DATA__` variable of a
  Python module, or its docstring after a line `__DATA__`, which a script of
  `Pyjoyment.Lite` uses, as its docstring is there before `app.start()`.
- `croak` of Carp reports the line of the caller, Python the line of the
  `raise`. Where Mojo's tests check the line that `croak` gives, as
  `load_class` of `Mojo::Loader` does, the port takes the frame of the caller
  from the traceback.
- Modules that a Mojo test loads from `t/mojo/lib` are written into a
  temporary directory by the test, as `Pyjo.Prove` runs every `.py` file
  under `t`, and are top-level there, as Python does not merge a regular
  package like `Mojo::` from every directory of `sys.path`. The modules of
  `t/mojolicious/lib`, the test applications and plugins of the framework,
  are in `tt/lib`, with `PyjoymentTest` for `MojoliciousTest`, and a test
  puts `tt/lib` in front of `sys.path`. The packages of a Mojo test that use
  `Mojolicious::Lite`, as `TestApp` of `embedded_lite_app.t`, are modules of
  `tt/lib` too, as an application of `Pyjoyment.Lite` is one of a module. The
  applications of `t/mojolicious/external` are in `tt/external`.
- A stack trace, Perl's `caller` frames, is a list of
  `traceback.FrameSummary`, the most recent first, as Mojo keeps it.
- `like` of `Test::More` stringifies what it checks, `like_ok` does not:
  a test of an object is `like_ok(str(obj), ...)`.
- `Test::More` writes to a copy of STDOUT that it makes when it starts,
  `Pyjo.Test` to `sys.stdout` at the time of the call. A test that replaces
  `sys.stdout` to capture the output of the code, as `local *STDOUT` does,
  checks the results after it gives `sys.stdout` back.
- A script that Mojo loads with `do`, taking the application from its value,
  as `load_app` of `Mojo::Server` does, starts its application, and `start`
  keeps it in `Pyjo.Server.loaded_app` when `PYJO_APP_LOADER` is set, where
  Mojo's `start` returns it; `MyApp.new().start()` chains as in Perl.
- A test that depends on the layout of its own source lines, as the context
  of `Mojo::Exception` does, is kept from the formatter with `# fmt: off`.
- Perl frees a temporary object at the end of the statement, Python as soon
  as nothing refers to it. Where an object holds a resource, like the
  temporary directory of `Pyjo.File.tempdir()`, an object made from it, like
  its `child()`, keeps it, so that `tempdir().child('x').spew(...)` works as in
  Perl.
- What Mojo calls on the class as a shortcut to its singleton, like
  `Mojo::IOLoop->timer`, is a function of the module bound to the singleton,
  `Pyjo.IOLoop.timer`.
- An object that holds a resource, like a socket or an I/O watcher, and that
  Perl closes in `DESTROY` when the port drops the last reference to it, as
  `Mojo::IOLoop` does with the acceptors and connections it deletes, is closed
  by the port where it drops it, as PyPy frees it only when its garbage
  collector runs. A resource that an object opens for itself, as the file of
  `path` in `Pyjo.Log`, is closed with the object by `weakref.finalize`.
- Perl closes the handles that are left at the end of the interpreter, in its
  global destruction; Python warns that they were not closed, as `__del__`
  does nothing while it finalizes. A class whose objects hold a resource until
  then, as `Pyjo.IOLoop`, `Pyjo.Server.Daemon` and `Pyjo.Asset.File`, keeps
  them in a `weakref.WeakSet` and closes them in an `atexit` handler of its
  module, which `Pyjo.IOLoop` follows with `gc.collect()`, so that the
  objects in cycles are freed while `__del__` still works. `weakref.finalize`
  calls the finalizers of the objects that are left in an exit function of
  its own, after which it calls none, also for the objects that the garbage
  collector frees then, so a handler that has to come before it, as the one
  of `Pyjo.Reactor.Asyncio`, which cancels the tasks that are left in a loop
  of its own and runs them to their end, as `asyncio.run` does, before it
  closes the loop, is registered after the first finalizer, as `atexit` runs
  the handlers in the reverse order.
- A method that Mojo calls on the class or on an object, like
  `Mojo::DOM->new_tag` and `$dom->new_tag`, is a descriptor that passes either
  of them.
- A method of Mojolicious with the name of a method of `Pyjo.Base`, like `set`
  of `Mojo::Cache`, replaces it in the class. Mojo's chain of an attribute and
  the method, `$cache->max_keys(1)->set(one => 1)`, is then an assignment
  followed by the call.
- Perl passes arguments by reference, so a callback can change a string of
  its caller through `$_[1]`; in Python, the caller passes a mutable object,
  like `io.StringIO`, and the callback changes it.
  A method that changes a string of its caller through a reference, as
  `match_partial(\$path)` of `Mojolicious::Routes::Pattern` removes what
  matched, returns the new string with its result: `captures, path =
pattern.match_partial(path)`.
- The name of the class of an object in a message, `blessed $self` or
  `ref $self`, is `module.qualname` of its class, as
  `Pyjo.EventEmitter.Pyjo_EventEmitter`.
- A callback is an argument in the order that suits Python, not necessarily
  the one of Mojo, and a call can also pass it as `cb`, where it is the only
  callback. A method that takes a callback, and means nothing else without
  it, is a decorator without it, and the decorated name is what the method
  returns with it: the id of a timer, a server or a connection of
  `Pyjo.IOLoop` or `Pyjo.UserAgent`, which `remove` takes, and the callback
  that `on` of `Pyjo.EventEmitter` subscribes. Where a call without the
  callback means something else, as a blocking request of
  `Pyjo.UserAgent`, there is no decorator. The callback is positional-only
  only where the keyword arguments of the method go on, to the callback, as
  in `map` of `Pyjo.Collection`, or somewhere else, as the attributes of
  `tag` of `Pyjo.DOM.HTML`. Where the order or the keyword differs from Mojo,
  a comment at the declaration says so.
- An object that undoes something when it goes away, like the one that
  `capture` of `Mojo::Log` returns, is a context manager: PyPy does not free
  it when the last reference goes, and `with` says where it ends. So is an
  object that holds a resource, as a socket, a file, a server or an event
  loop, whose `__exit__` does what its finalizer does, and the module
  documentation says what the end of the block releases. Such an object has a
  method `close` too, which `__exit__` calls, with `# Not in Mojolicious:`
  where Perl releases it in `DESTROY`: the context manager is an option, not a
  requirement, as for an object that lives longer than a block, as the user
  agent of an application, which closes it when it stops. It is an interface
  for the code that uses Pyjoyment, its tests and examples: the modules call
  `close` and the like themselves, as `with` costs more than a call. An
  object in a cycle, as a user agent with its server, is freed by the
  garbage collector at any point, even in the middle of what the event loop
  does, so a test that makes many of them releases them with `with`.
- An attribute with a default that Mojo builds on first use, like `format`
  and `handle` of `Mojo::Log`, or that comes from a call, like the limits
  that `Pyjo.Headers` and `Pyjo.Message` read from `PYJO_MAX_*`, is a
  property that builds and keeps it the first time it is read, as Mojo
  does: an object that never reads it, like most of those of a request,
  does not pay for the call. A default that is a constant is set by the
  constructor.
- `die` or `croak` with a message raises a `Pyjo.Exception`. An error of the
  system, `$!`, is the `OSError` itself, with the message of Mojo in front of
  its `strerror`.
- A callback returns a list in Perl and one value in Python. Where Mojo
  makes values of what a callback returns, as `then` of `Mojo::Promise` does,
  the return value is one value, `None` is none, as Perl's `return;`, and a
  promise of several values passes them on. Where the values are passed on as
  they are, as the first callback of `run` of `Pyjo.IOLoop.Subprocess` gives
  them to the second one, a tuple is several values.
- Perl's `fork` is `os.fork`, where it exists, and `POSIX::_exit` is
  `os._exit`, which leaves the buffers of `sys.stdout` and `sys.stderr`, so
  they are written before both. A process with threads may deadlock in the
  child of a fork, which Python warns about, so a pool of threads of the port,
  as the one of name resolution in `Pyjo.IOLoop.Client`, is stopped before a
  fork with `os.register_at_fork` and started again when it is needed.
- `async sub` of Mojo is an `async def` that the reactor runs as a promise,
  `Pyjo.Promise.coroutine`, and Mojo's `AWAIT_*` methods are `__await__`. A
  reactor without asyncio drives a coroutine that awaits promises of
  Pyjoyment; the asyncio reactor runs it as a task. Each step of it is an
  event that ends `one_tick`, as a step of an `async sub` is a callback of
  `next_tick` in Mojo, so that code that waits with `one_tick` for what it
  does, as a server that waits for the response of an action, does not wait
  for the next timer.
- A method that the base class of Mojo leaves to a subclass raises
  `NotImplementedError` with the message of Mojo's croak,
  `Method "x" not implemented by subclass`.
- Perl defers the handler of a signal to a safe point and returns from a
  system call that the signal interrupts. Python runs the handler in the
  middle of what the main thread does, where writing to a stream that is
  being written raises `RuntimeError`, and repeats the interrupted call until
  its timeout. So the handler of a server, as the ones of
  `Pyjo.Server.Prefork`, only notes the signal, which the main loop handles,
  and `signal.set_wakeup_fd` with a socket pair that the loop watches wakes it
  up. In the child of a fork, a reactor of asyncio that is not given a loop
  moves to a new one, as the selector of the loop of the parent, epoll or
  kqueue, is not the child's. Python clears in the child a signal that comes
  during the fork, and the child has the handlers of the parent until it sets
  its own, so a signal that the child must not miss, as QUIT of a worker of
  `Pyjo.Server.Prefork`, is blocked with `signal.pthread_sigmask` across the
  fork and unblocked once the child has its handler.
- The signals of the servers follow the conventions of containers, where
  Mojo follows the ones of nginx and unicorn: Docker and Kubernetes stop a
  server with TERM, so INT and TERM shut `Pyjo.Server.Daemon`,
  `Pyjo.Server.Prefork` and `Pyjo.Server.Hot` down gracefully, a second INT,
  as of Ctrl-C pressed twice, immediately, and QUIT immediately; HUP reloads,
  as in gunicorn and in `ExecReload` of systemd: a hot deployment in
  `Pyjo.Server.Hot`, where Mojo has USR2, which is left out, so that no
  signal keeps the meaning that Mojo gives it, a graceful restart of the
  workers in `Pyjo.Server.Prefork`, and nothing in `Pyjo.Server.Daemon`. A
  worker stops gracefully on TERM and ignores INT, which Ctrl-C sends to all
  the processes of the server. `shutdown_delay` keeps the server serving
  after INT or TERM, with the readiness of `Pyjoyment.Plugin.Health` failing,
  before it closes its listen sockets, so that a load balancer sends no more
  connections to it, which `generate kubernetes` sets in the place of a hook
  `preStop`. The manager of `Pyjo.Server.Prefork` counts it and tells the
  workers with USR1, not with a delay of TERM, as TERM of a worker is also its
  graceful restart, by HUP or `accepts`, whose readiness must not fail, and
  `Pyjo.Server.Hot` has no delay, as the new manager stops the old one with
  TERM. `graceful_timeout` of `Pyjo.Server.Prefork`
  is 25 seconds, where Mojo has 120, below the 30 seconds that Kubernetes
  gives a container to stop, so that the server forces its workers and stops
  by itself before the orchestrator kills it. The tests of Mojo that send
  these signals have `# Unlike Mojolicious:` comments. Windows has INT, TERM
  and BREAK only, and a TERM of another process terminates the process there
  without its handler, so BREAK, of Ctrl-Break, takes the place of QUIT, and
  a server stops from its console.
- `File::Spec` and `File::Basename` follow the system, so `Pyjo.File` has
  their rules of Unix and, on Windows, of `File::Spec::Win32` and of
  `MSWin32`, with the volume of a path and both separators. A file is read
  and written with `os.O_BINARY` there, as `sysread` and `syswrite` pass the
  bytes as they are, where the text mode of Windows writes `\n` as CRLF.
- `local` on an attribute, as `local $self->{running}`, is the value saved
  before and set back in a `finally`.
- `__del__`, the counterpart of `DESTROY`, does nothing when
  `sys.is_finalizing()`, as Mojo checks `${^GLOBAL_PHASE}`, and keeps its
  whole body in a `try`: at the end of the interpreter the globals of the
  module may already be `None`, even `sys`.
- Perl runs `DESTROY` when the last reference goes, at the end of a
  statement; the garbage collector of Python frees the objects in cycles at
  any allocation, even in the middle of what an event loop does, as inside
  `selector.register` of asyncio. A finalizer that changes an event loop, as
  one that closes a socket or removes an acceptor, cleans up through
  `Pyjo.Reactor._finalize`: at once, as `DESTROY`, unless it interrupted a
  frame of `Pyjo.IOLoop`, of a reactor, of asyncio or of `selectors`, where
  the cleanup waits for the next tick of the event loop, which every reactor
  runs at a point that is safe, and for the end of the interpreter. The
  garbage collector runs in any thread that allocates, as a thread of name
  resolution, whose frames do not show what the thread of the event loop
  does, so a finalizer outside of the thread of the reactor of its object,
  the main one for an object without a reactor, always waits for the next
  tick of that thread, which any of its reactors runs, as an object may
  belong to several event loops, and the asyncio reactor is woken up with
  `call_soon_threadsafe`; on Linux, epoll reports a socket closed in the
  middle of `add_reader` as `FileNotFoundError`. `t/stdlib/IOLoop_gc.py`
  makes the garbage collector run all the time.
- Each thread of Perl has a copy of the interpreter, with a `Mojo::IOLoop`
  singleton of its own; Python shares the module, so `Pyjo.IOLoop.singleton`
  is found with `__getattr__` of the module in a `threading.local`, the
  functions of the module, as `Pyjo.IOLoop.timer`, call their methods on it,
  and a reactor runs in the thread that made it. Threads run event loops of
  their own at the same time, as `t/stdlib/IOLoop_threading.py` checks.
- An optional module of Perl that Mojo uses when it is installed has a
  counterpart in the standard library, one of the port's own where the
  standard library has none, or is left out until something needs it:
  Net::DNS::Native is `getaddrinfo` in a thread that tells the reactor through
  a socket pair, IO::Socket::Socks is a SOCKS5 client in `Pyjo.IOLoop.Client`,
  which `PYJO_NO_SOCKS` turns off as `PYJO_NO_TLS` does TLS, and
  `socket_options` of IO::Socket::IP is `source_address`, as
  `socket.create_connection` has it. `SSL_hostname` and `SSL_verifycn_name`
  of IO::Socket::SSL are one `tls_hostname`, as Python has one
  `server_hostname` for SNI and for the verification.
- `tls_options` of IO::Socket::SSL is an `ssl.SSLContext`, `tls_context`, as
  asyncio takes `ssl=context`. OpenSSL chooses an ALPN protocol by the order
  of the server, IO::Socket::SSL by the order of the client.
- A timer of no time, as `next_tick` makes, runs in Mojo's reactor in the
  same tick as the I/O before it, so before the next I/O; asyncio runs a
  `call_later(0)` after the I/O of its next iteration, and a `call_soon`
  before it, so the asyncio reactor schedules such a timer with `call_soon`.
  The callbacks of `next_tick` run until none is left, as in Mojo, also the
  ones that they add, so code that tries again until something is there, as
  a body without a chunk yet, tries with a timer of no time, which lets the
  I/O and the timers of the next cycle run first.
- A callback that an asyncio loop keeps, as a timer or an I/O watcher,
  refers to the reactor weakly, so that the reactor and the loop it owns do
  not make a cycle: in a cycle the garbage collector may close the sockets of
  the loop before the loop itself, and closing the loop then fails.
- asyncio does not nest event loops, and it logs an exception that a
  callback raises instead of passing it on. Where Mojo runs the reactor from
  a callback, the port returns at once, and an exception that Mojo lets die
  out of `start` is kept by the reactor and raised after the loop stops.
  So code that the event loop calls never runs the event loop to wait: the
  `one_tick` of the asyncio reactor returns at once in a loop that runs, so a
  wait on it spins for ever, and `Pyjo.Reactor.Poll` would run the callbacks
  of other connections in the middle of the code that waits. A server that
  waits for a response, as `Pyjo.Server.WSGI`, waits only where the event
  loop does not run, and gives empty chunks of the body until it is there in
  the one that runs, and `Pyjo.App.WSGI` takes each chunk of the body of its
  application in a tick of its own, once the one before has been written,
  not in the middle of what the server writes. An application mounted in
  another one in the same process, as in the examples
  `mount_wsgi_inception.py` and `mount_asgi_inception.py`, is what catches
  such reentry in the tests, which a test in two processes would hide.
- A module that is not ported yet but uses a ported one follows its API: the
  lines that use it are taken from the target Mojolicious, and so is the
  expectation of a test of them that the target changed.
- The files that Mojolicious bundles in `lib/Mojolicious/resources` are in
  `Pyjoyment/resources`, with `pyjo` in the place of `mojo` in their paths, as
  `pyjo/logo-white.png` for `mojo/logo-white.png`. The artwork of Mojolicious,
  as its logo, the raptors, the favicon and the pinstripes, is not copied: it
  is under CC-BY-SA, and the license of Mojolicious does not grant its logo.
  Its place is taken by the artwork of Pyjoyment, in the same formats and
  sizes: a joystick for the logo, and a unicat, a cat with the horn of a
  unicorn and a rainbow, for the raptor, whose images are named after it,
  `failunicat.png` and `nounicat.png` for `failraptor.png` and `noraptor.png`.
  The code, templates and tests that use these paths have a
  `# Renamed from Mojolicious:` comment. Each image has its source next to it,
  an SVG of the same name, which is edited and rendered again with
  `rsvg-convert logo.svg -o logo.png`; `favicon.ico` holds the renders of
  `favicon.svg` at 48, 32 and 16 pixels. The text in them is set in Fredoka,
  under the SIL Open Font License, and converted to paths, so that the SVG
  needs no font.
- The JavaScript libraries that the bundled templates use, Bootstrap and
  highlight.js, are kept up to date on their own, not in the versions that
  Mojolicious bundles. `package.json` names their packages of npm, with exact
  versions that Renovate bumps, and maps the files of the packages to the files
  in `Pyjoyment/resources/public/pyjo`, under the names that Mojolicious gives
  them; `npm run bundle` copies them, after `npm ci --ignore-scripts`, which
  checks the packages against `package-lock.json` and runs none of their
  scripts:

  ```sh
  mise exec -- npm ci --ignore-scripts
  mise exec -- npm run bundle
  ```

  The workflow Bundle Check fails a pull request whose files do not match the
  lock, and commits them to a branch of Renovate, which cannot run the copy,
  with the token of the workflow; a push with that token starts no workflow, so
  the job starts Bundle Check, Build, Tests and Trunk Check on the commit with
  `workflow_dispatch`. Renovate keeps a major release for an approval in its
  Dependency Dashboard, as the tests do not run JavaScript: such a release is
  checked in a browser, and the templates follow its API. `bootstrap.js` is the
  bundle of Bootstrap, which has Popper, so Pyjoyment has no `popper.js`, and
  the build of highlight.js has Python among its languages. Each library has
  the text of its license in a `LICENSE` next to it. The stylesheet
  `mojo/mojo.css` is `pyjo/pyjo.css`, the theme of highlight.js
  `highlight-mojo-dark.css` is the one of Mojolicious, and `pyjoyment.min.js`,
  the language of highlight.js for the templates, is `mojolicious.min.js` with
  Python in the place of Perl; the copy leaves them as they are. Trunk does not
  lint or format any of them, so that a newer version replaces them as they
  are. The links of the pages are those of Pyjoyment. A bundled template has
  its markers as comments of the template, as `%# Renamed from Mojolicious:`.
