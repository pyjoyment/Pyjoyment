"""
Pyjoyment.Static - Serve static files
=====================================
::

    from Pyjoyment.Static import Static

    static = Static()
    static.classes.append('MyApp.Controller.Foo')
    static.paths.append('/home/sri/public')

    # Or import the module, as in Google Python Style Guide

    import Pyjoyment.Static

    static = Pyjoyment.Static.new()
    static.classes.append('MyApp.Controller.Foo')
    static.paths.append('/home/sri/public')

:mod:`Pyjoyment.Static` is a static file server with ``Range``,
``If-Modified-Since`` and ``If-None-Match`` support, based on
`RFC 7232 <https://tools.ietf.org/html/rfc7232>`_ and
`RFC 7233 <https://tools.ietf.org/html/rfc7233>`_.

A file of :attr:`paths` with a precompressed variant next to it, as
``app.css.gz`` of ``gzip -k``, is served as the variant to the clients whose
``Accept-Encoding`` takes its encoding, with the encodings and the extensions
of :attr:`encodings`. A variant older than its file is ignored, and a
``Range`` request gets the file.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Static <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Static.pm>`_
of Mojolicious 9.49.
"""

import Pyjo.Asset
import Pyjo.Asset.File
import Pyjo.Asset.Memory
import Pyjo.Base
import Pyjo.Date
import Pyjo.File
import Pyjo.Loader

from Pyjo.Util import encode, md5_sum, trim

import os
import re
import stat

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast


if TYPE_CHECKING:
    import Pyjoyment.Controller


# Bundled files
_PUBLIC = Pyjo.File.path(__file__).sibling('resources', 'public')
_EXTRA = {'/'.join(file.to_rel(_PUBLIC).to_list()): file.realpath().to_str() for file in _PUBLIC.list_tree()}


class Pyjoyment_Static(Pyjo.Base.object):
    """
    :mod:`Pyjoyment.Static` inherits all methods from :mod:`Pyjo.Base` and
    implements the following new ones.
    """

    def __init__(self) -> None:
        """::

            static = Pyjoyment.Static.new()

        Construct a new :mod:`Pyjoyment.Static` object.
        """
        self.asset_dir = 'assets'
        """::

            dir = static.asset_dir
            static.asset_dir = 'assets'

        Subdirectory used for all static assets, defaults to ``assets``.
        """

        # Not in Mojolicious: the Cache-Control of the files
        self.cache_control: str | Callable[[Pyjoyment.Controller.object, str], str | None] | None = None
        """::

            cache_control = static.cache_control
            static.cache_control = 'public, max-age=60'
            static.cache_control = lambda c, rel: 'no-cache' if rel.endswith('.html') else 'public, max-age=60'

        ``Cache-Control`` of the files that are served, also with ``304``,
        unless the response has one already, or a function that gets the
        controller and the path of the file, relative to :attr:`paths` and
        without :attr:`prefix`, and returns it, or ``None`` for none,
        defaults to ``None``. The files of :attr:`immutable` get theirs. ::

            # Revalidate every file after a minute
            static.cache_control = 'public, max-age=60'
        """

        self.classes = ['__main__']
        """::

            classes = static.classes
            static.classes = ['__main__']

        Classes to use for finding files in ``DATA`` sections with
        :mod:`Pyjo.Loader`, first one has the highest precedence, defaults to
        ``__main__``. Only files with exactly one extension will be used, like
        ``index.html``. Note that for files to be detected, these classes need
        to have already been loaded and added before :meth:`warmup` is called,
        which usually happens automatically during application startup. ::

            # Add another class with static files in DATA section
            static.classes.append('Pyjoyment.Plugin.Fun')

            # Add another class with static files in DATA section and higher precedence
            static.classes.insert(0, 'Pyjoyment.Plugin.MoreFun')
        """

        # Not in Mojolicious: the precompressed variants of the files
        self.encodings = {'br': '.br', 'zstd': '.zst', 'gzip': '.gz'}
        """::

            encodings = static.encodings
            static.encodings = {'gzip': '.gz'}

        Encodings of the precompressed variants of the files of :attr:`paths`
        and the extensions of their files, in their order of preference,
        defaults to ``{'br': '.br', 'zstd': '.zst', 'gzip': '.gz'}``, as
        ``brotli -k``, ``zstd -k`` and ``gzip -k`` write them. A request
        whose ``Accept-Encoding`` takes an encoding gets the variant with its
        ``Content-Encoding``, and the ``Content-Type`` of the file. ::

            # Serve the files as they are only
            static.encodings = {}
        """

        self.extra = dict(_EXTRA)
        """::

            extra = static.extra
            static.extra = {'foo/bar.txt': '/home/sri/myapp/bar.txt'}

        Paths for extra files to be served from locations other than
        :attr:`paths`, such as the images used by the built-in exception and
        not found pages. Note that extra files are only served if no better
        alternative could be found in :attr:`paths` and :attr:`classes`. ::

            # Remove built-in favicon
            del static.extra['favicon.ico']
        """

        # Not in Mojolicious: the files that never change
        self.immutable: str | re.Pattern[str] | None = None
        """::

            immutable = static.immutable
            static.immutable = r'\\.[0-9a-f]{12}\\.[^/.]+$'

        Regular expression of the paths of the files, relative to
        :attr:`paths` and without :attr:`prefix`, whose names have a hash of
        their content, as the ones of a bundler, and never change, so that
        they are served with ``Cache-Control: public, max-age=31536000,
        immutable`` in place of :attr:`cache_control`, defaults to ``None``.
        The assets of the ``development`` mode are served with
        ``Cache-Control: no-cache`` still. ::

            # The names of ManifestStaticFilesStorage of Django
            static.immutable = re.compile(r'\\.[0-9a-f]{12}\\.[^/.]+$')
        """

        self.paths: list[str] = []
        """::

            paths = static.paths
            static.paths = ['/home/sri/public']

        Directories to serve static files from, first one has the highest
        precedence. ::

            # Add another "public" directory
            static.paths.append('/home/sri/public')

            # Add another "public" directory with higher precedence
            static.paths.insert(0, '/home/sri/themes/blue/public')
        """

        self.prefix: str | None = None
        """::

            prefix = static.prefix
            static.prefix = '/static'

        Prefix to use for all static files, defaults to ``None``. This can be
        very useful for production deployments where the reverse proxy server
        should take over serving static files.
        """

        self._assets: dict[str, str] | None = None
        self._index: dict[str, str] | None = None

    def asset_path(self, asset: str) -> str:
        """::

            path = static.asset_path('/app.js')

        Get static asset path.
        """
        if not asset.startswith('/'):
            asset = f'/{asset}'
        if self._assets is None:
            self._assets = {}
        return self.file_path(f'/{self.asset_dir}{self._assets.get(asset, asset)}')

    def dispatch(self, c: 'Pyjoyment.Controller.object') -> bool | None:
        """::

            boolean = static.dispatch(Pyjoyment.Controller.new())

        Serve static file for :mod:`Pyjoyment.Controller` object.
        """
        # Method (GET or HEAD)
        req = c.req
        method = req.method
        if method != 'GET' and method != 'HEAD':
            return None

        # Canonical path
        stash = c.stash()
        path = req.url.path
        path = path.new(stash['path']) if stash.get('path') else path.clone()
        if not (parts := path.canonicalize().parts):
            return None

        # Serve static file and prevent path traversal
        canon_path = '/'.join(parts)
        if re.search(r'^\.\./|\\', canon_path) or not self.serve(c, canon_path):
            return None
        stash['mojo.static'] = True

        # Development assets will be rebuilt a lot, do not let browsers cache them
        if c.app.mode == 'development' and canon_path.startswith(self.asset_dir):
            c.res.headers.cache_control = 'no-cache'

        return bool(c.rendered())

    def file(self, rel: str) -> Pyjo.Asset.File.object | Pyjo.Asset.Memory.object | None:
        """::

            asset = static.file('images/logo.png')
            asset = static.file('../lib/MyApp.py')

        Build :mod:`Pyjo.Asset.File` or :mod:`Pyjo.Asset.Memory` object for a
        file, relative to :attr:`paths` or from :attr:`classes`, or return
        ``None`` if it doesn't exist. Note that this method uses a relative
        path, but does not protect from traversing to parent directories. ::

            content = static.file('foo/bar.html').slurp()
        """
        if self._index is None:
            self.warmup()

        # Search all paths
        parts = rel.split('/')
        for path in self.paths:
            if asset := _get_file(Pyjo.File.path(path, *parts).to_str()):
                return asset

        # Search DATA
        if asset := self._get_data_file(rel):
            return asset

        # Search extra files
        extra = self.extra
        return _get_file(extra[rel]) if rel in extra else None

    def file_path(self, file: str) -> str:
        """::

            path = static.file_path('/index.html')

        Get static file path with :attr:`prefix` if it has been configured.
        """
        if not file.startswith('/'):
            file = f'/{file}'
        if not (prefix := self.prefix):
            return file
        return f'{prefix}{file}'

    def is_fresh(
        self, c: 'Pyjoyment.Controller.object', *, etag: str | None = None, last_modified: float | None = None
    ) -> bool:
        """::

            boolean = static.is_fresh(Pyjoyment.Controller.new(), etag='abc')
            boolean = static.is_fresh(Pyjoyment.Controller.new(), etag='W/"def"')

        Check freshness of request by comparing the ``If-None-Match`` and
        ``If-Modified-Since`` request headers to the ``ETag`` and
        ``Last-Modified`` response headers.

        These options are currently available:

        etag ::

            etag='abc'
            etag='W/"abc"'

        Add ``ETag`` header before comparing.

        last_modified ::

            last_modified=epoch

        Add ``Last-Modified`` header before comparing.
        """
        res_headers = c.res.headers
        if last_modified:
            res_headers.last_modified = Pyjo.Date.new(last_modified).to_str()
        if etag:
            etag = etag if etag.startswith('W/"') else f'"{etag}"'
            res_headers.etag = etag

        # Unconditional
        req_headers = c.req.headers
        match = req_headers.if_none_match
        if not (since := req_headers.if_modified_since) and not match:
            return False

        # If-None-Match
        if etag is None:
            etag = res_headers.etag or ''
        if match and not any(e == etag or f'W/{e}' == etag for e in (trim(m) for m in match.split(','))):
            return False

        # If-Modified-Since
        last = last_modified if last_modified else res_headers.last_modified
        if not last or not since:
            return bool(match)
        return (_epoch(last) or 0) <= (_epoch(since) or 0)

    def serve(self, c: 'Pyjoyment.Controller.object', rel: str) -> bool | None:
        """::

            boolean = static.serve(Pyjoyment.Controller.new(), 'images/logo.png')
            boolean = static.serve(Pyjoyment.Controller.new(), '../lib/MyApp.py')

        Serve a specific file, relative to :attr:`paths` or from
        :attr:`classes`. Note that this method uses a relative path, but does
        not protect from traversing to parent directories.
        """
        # Prefix
        if prefix := self.prefix:
            rel = f'/{rel}'
            if not rel.startswith(f'{prefix}/'):
                return None
            rel = rel[len(prefix) + 1 :]

        if not (asset := self.file(rel)):
            return None
        c.app.types.content_type(c, file=rel)

        # Not in Mojolicious: the precompressed variant of the file, with the Content-Type of the file, which
        # serve_asset keeps
        if asset.is_file and self.encodings:
            asset = self._variant(c, cast(Pyjo.Asset.File.object, asset))

        # Not in Mojolicious: the Cache-Control of the file, also of a 304, as RFC 9111 has it
        headers = c.res.headers
        if not headers.cache_control:
            if (immutable := self.immutable) is not None and re.search(immutable, rel):
                headers.cache_control = 'public, max-age=31536000, immutable'
            elif callable(cache_control := self.cache_control):
                if value := cache_control(c, rel):
                    headers.cache_control = value
            elif cache_control:
                headers.cache_control = cache_control

        return bool(self.serve_asset(c, asset))

    def serve_asset(self, c: 'Pyjoyment.Controller.object', asset: Pyjo.Asset.object) -> Any:
        """::

            static.serve_asset(Pyjoyment.Controller.new(), Pyjo.Asset.File.new())

        Serve a :mod:`Pyjo.Asset.File` or :mod:`Pyjo.Asset.Memory` object with
        ``Range``, ``If-Modified-Since`` and ``If-None-Match`` support.
        """
        # Content-Type
        if asset.is_file:
            c.app.types.content_type(c, file=cast(Pyjo.Asset.File.object, asset).path)

        # Last-Modified and ETag
        res = c.res
        res.code = 200
        res.headers.accept_ranges = 'bytes'
        # Whole seconds, as Perl gives the time of a file, and as an HTTP date has it
        mtime = int(asset.mtime)
        etag = md5_sum(str(mtime).encode())
        # Not in Mojolicious: a representation with a Content-Encoding, as a precompressed variant, has an ETag of its
        # own, as the original and its variant can have the same mtime
        if encoding := res.headers.content_encoding:
            etag = f'{etag}-{encoding}'
        if self.is_fresh(c, etag=etag, last_modified=mtime):
            res.code = 304
            return res

        # Range
        content: Any = res.content
        if not (range := c.req.headers.range):
            content.asset = asset
            return content

        # Not satisfiable
        if not (size := asset.size):
            res.code = 416
            return res
        if not (m := re.match(r'^bytes=(\d+)?-(\d+)?', range)):
            res.code = 416
            return res
        start = int(m[1]) if m[1] is not None else 0
        end = int(m[2]) if m[2] is not None and int(m[2]) < size else size - 1
        if start > end:
            res.code = 416
            return res

        # Satisfiable
        res.code = 206
        res.headers.content_length = end - start + 1
        res.headers.content_range = f'bytes {start}-{end}/{size}'
        asset.start_range = start
        asset.end_range = end
        content.asset = asset
        return content

    def warmup(self) -> None:
        """::

            static.warmup()

        Prepare static files from :attr:`classes` and static assets for future
        use.
        """
        # DATA sections
        index: dict[str, str] = {}
        self._index = index
        for cls in reversed(self.classes):
            for key in cast(dict[str, Any], Pyjo.Loader.data_section(cls) or {}):
                index[key] = cls

        # Static assets
        assets: dict[str, str] = {}
        self._assets = assets
        asset_dir = self.asset_dir
        for path in self.paths:
            asset_path = Pyjo.File.path(path, asset_dir)
            if not asset_path.is_dir:
                continue

            for asset_file in asset_path.list_tree():
                parts = asset_file.to_rel(asset_path).to_list()
                filename = parts.pop()
                prefix = '/'.join(parts)

                if not (m := re.match(r'^([^.]+)\.([^.]+)\.(.+)$', filename)):
                    continue
                checksum = m[2]
                short = f'/{m[1]}.{m[3]}' if prefix == '' else f'/{prefix}/{m[1]}.{m[3]}'
                long = '/' + '/'.join([*parts, filename])

                if short not in assets or checksum == 'development':
                    assets[short] = long

    def _get_data_file(self, rel: str) -> Pyjo.Asset.Memory.object | None:
        # Protect files without extensions and templates with two extensions
        if not re.search(r'\.\w+$', rel) or re.search(r'\.\w+\.\w+$', rel):
            return None

        # Find file
        cls = (self._index or {}).get(rel)
        if cls is None or (data := Pyjo.Loader.data_section(cls, rel)) is None:
            return None
        data = cast(str | bytes, data)
        asset = Pyjo.Asset.Memory.new()
        asset.add_chunk(data if isinstance(data, bytes) else encode('UTF-8', data))
        return asset

    # Not in Mojolicious: the precompressed variant of a file that the request takes, or the file
    def _variant(self, c: 'Pyjoyment.Controller.object', asset: Pyjo.Asset.File.object) -> Pyjo.Asset.File.object:
        # Variants, without the ones older than the file, in whole seconds, as brotli copies the mtime with utime
        path = asset.path
        mtime = int(asset.mtime)
        variants: list[tuple[str, str]] = []
        for encoding, ext in self.encodings.items():
            try:
                st = os.stat(variant := f'{path}{ext}')
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode) and int(st.st_mtime) >= mtime and os.access(variant, os.R_OK):
                variants.append((encoding, variant))
        if not variants:
            return asset

        # A cache keeps the representations apart, also the one of the file
        res_headers = c.res.headers
        res_headers.append('Vary', 'Accept-Encoding')

        # A range is of the file, as a client that resumes a download has the file in mind
        req_headers = c.req.headers
        if req_headers.range or not (accepted := _accept_encoding(req_headers.accept_encoding)):
            return asset

        # The highest quality, then the order of the encodings, unless the file is preferred
        best: tuple[float, str, str] | None = None
        for encoding, variant in variants:
            q = accepted.get(encoding, accepted.get('*', 0.0))
            if q > 0 and (best is None or q > best[0]):
                best = (q, encoding, variant)
        if best is None or best[0] < accepted.get('identity', 0.0):
            return asset
        res_headers.content_encoding = best[1]
        asset.close()
        return Pyjo.Asset.File.new(path=best[2])


# Not in Mojolicious: the qualities of the encodings of Accept-Encoding, with x-gzip as gzip, as RFC 9110 has it, and
# an invalid quality as 0
def _accept_encoding(header: str | None) -> dict[str, float]:
    accepted: dict[str, float] = {}
    for part in (header or '').split(','):
        name, *params = (trim(p) for p in part.split(';'))
        if not name:
            continue
        q = 1.0
        for param in params:
            if re.match(r'^q\s*=', param, re.IGNORECASE):
                m = re.match(r'^q\s*=\s*([01](?:\.\d{0,3})?)$', param, re.IGNORECASE)
                q = min(float(m[1]), 1.0) if m else 0.0
        name = name.lower()
        accepted['gzip' if name == 'x-gzip' else name] = q
    return accepted


def _epoch(date: Any) -> float | None:
    return Pyjo.Date.new(date).epoch


def _get_file(path: str) -> Pyjo.Asset.File.object | None:
    return Pyjo.Asset.File.new(path=path) if os.path.isfile(path) and os.access(path, os.R_OK) else None


new = Pyjoyment_Static.new
object = Pyjoyment_Static
Static = Pyjoyment_Static
