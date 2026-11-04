"""
Pyjo.Date - HTTP date
=====================
::

    from Pyjo.Date import Date

    # Parse
    date = Date('Sun, 06 Nov 1994 08:49:37 GMT')
    print(date.epoch)

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Date

    import time

    # Parse
    date = Pyjo.Date.new('Sun, 06 Nov 1994 08:49:37 GMT')
    print(date.epoch)

    # Build
    date = Pyjo.Date.new(time.time() + 60)
    print(date)

:mod:`Pyjo.Date` implements HTTP date and time functions, based on :rfc:`7230`,
:rfc:`7231` and :rfc:`3339`.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::Date <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojo/Date.pm>`_
of Mojolicious 9.49.

Classes
-------
"""

import Pyjo.Base
import Pyjo.String.Mixin
import Pyjo.String.Unicode

import calendar
import re
import time

from datetime import UTC, datetime
from typing import Self


RFC3339_RE = re.compile(
    r"""
  ^(\d+)-(\d+)-(\d+)\D+(\d+):(\d+):(\d+(?:\.\d+)?)   # Date and time
  (?:Z|([+-])(\d+):(\d+))?$                          # Offset
""",
    re.X | re.I,
)

DAYS = ('Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat')
MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
MONTH_NUMBERS = {name: number for number, name in enumerate(MONTHS)}


class Pyjo_Date(Pyjo.Base.object, Pyjo.String.Mixin.object):
    """
    :mod:`Pyjo.Date` inherits all methods from :mod:`Pyjo.Base` and
    :mod:`Pyjo.String.Mixin` and implements the following new ones.
    """

    epoch: int | float | None

    def __init__(self, date: str | float | datetime | None = None) -> None:
        """::

            date = Pyjo.Date.new()
            date = Pyjo.Date.new('Sun Nov  6 08:49:37 1994')
            date = Pyjo.Date.new(datetime.now(UTC))

        Construct a new :mod:`Pyjo.Date` object and :meth:`parse` date if necessary.
        """

        self.epoch = int(time.time())
        """::

            epoch = date.epoch
            date.epoch = 784111777

        Epoch seconds, defaults to the current time.
        """

        if date is not None:
            self.parse(date)

    def __bool__(self) -> bool:
        """::

            boolean = bool(date)

        Always true.
        """
        return True

    # Not in Mojolicious: the epoch for the standard library
    def __float__(self) -> float:
        """::

            number = float(date)

        The epoch, for the standard library. Before Python 3.15,
        :meth:`datetime.datetime.fromtimestamp` and :func:`time.gmtime` take only an
        ``int`` or a ``float``, not an object that converts to one, so they get
        ``float(date)``. ::

            # datetime.datetime(1994, 11, 6, 8, 49, 37, tzinfo=datetime.timezone.utc)
            datetime.fromtimestamp(float(Pyjo.Date.new(784111777)), UTC)
        """
        return float(self.epoch or 0)

    # Not in Mojolicious: the format of strftime, as datetime of the standard library has it, in the place of the one of
    # a string of Pyjo.String.Mixin
    def __format__(self, format_spec: str) -> str:
        """::

            string = format(date, '%Y%m%d')
            string = f'{date:%Y%m%dT%H%M%SZ}'

        Format date with :meth:`strftime`, as :meth:`datetime.datetime.__format__`
        does, or as :meth:`to_str` without a format. ::

            # "19941106T084937Z"
            f'{Pyjo.Date.new(784111777):%Y%m%dT%H%M%SZ}'
        """
        if not format_spec:
            return self.to_str()
        return self.strftime(format_spec).to_str()

    # Not in Mojolicious: the epoch for the standard library
    def __int__(self) -> int:
        """::

            number = int(date)

        The epoch in whole seconds, for the standard library.
        """
        return int(self.epoch or 0)

    def __str__(self) -> str:
        """::

            string = str(date)

        Alias for :meth:`to_str`.
        """
        return self.to_str()

    def parse(self, date: str | float | datetime) -> Self:
        """::

            date = date.parse('Sun Nov  6 08:49:37 1994')
            date = date.parse(datetime.now(UTC))

        Parse date. A :class:`datetime.datetime` gives its timestamp, so a naive
        one is local time, as for :meth:`datetime.datetime.timestamp`. ::

            # Epoch
            print(Pyjo.Date.new('784111777').epoch)
            print(Pyjo.Date.new('784111777.21').epoch)

            # RFC 822/1123
            print(Pyjo.Date.new('Sun, 06 Nov 1994 08:49:37 GMT').epoch)

            # RFC 850/1036
            print(Pyjo.Date.new('Sunday, 06-Nov-94 08:49:37 GMT').epoch)

            # Ansi C asctime()
            print(Pyjo.Date.new('Sun Nov  6 08:49:37 1994').epoch)

            # RFC 3339
            print(Pyjo.Date.new('1994-11-06T08:49:37Z').epoch)
            print(Pyjo.Date.new('1994-11-06T08:49:37').epoch)
            print(Pyjo.Date.new('1994-11-06T08:49:37.21Z').epoch)
            print(Pyjo.Date.new('1994-11-06T08:49:37+01:00').epoch)
            print(Pyjo.Date.new('1994-11-06T08:49:37-01:00').epoch)
        """
        # Not in Mojolicious: datetime of the standard library
        if isinstance(date, datetime):
            timestamp = date.timestamp()
            self.epoch = int(timestamp) if timestamp.is_integer() else timestamp
            return self

        date = str(date)

        # epoch (784111777)
        if re.search(r'^\d+$|^\d+\.\d+$', date):
            self.epoch = float(date) if '.' in date else int(date)
            return self

        # RFC 822/1123 (Sun, 06 Nov 1994 08:49:37 GMT)
        # RFC 850/1036 (Sunday, 06-Nov-94 08:49:37 GMT)
        offset = 0
        if m := re.search(r'^\w+\W+(\d+)\W+(\w+)\W+(\d+)\W+(\d+):(\d+):(\d+)\W*\w+$', date):
            day, month, year, h, mi, s = m[1], MONTH_NUMBERS.get(m[2]), m[3], m[4], m[5], m[6]

        # RFC 3339 (1994-11-06T08:49:37Z)
        elif m := RFC3339_RE.search(date):
            year, month, day, h, mi, s = m[1], int(m[2]) - 1, m[3], m[4], m[5], m[6]
            if m[7]:
                offset = ((int(m[8]) * 3600) + (int(m[9]) * 60)) * (-1 if m[7] == '+' else 1)

        # ANSI C asctime() (Sun Nov  6 08:49:37 1994)
        elif m := re.search(r'^\w+\s+(\w+)\s+(\d+)\s+(\d+):(\d+):(\d+)\s+(\d+)$', date):
            month, day, h, mi, s, year = MONTH_NUMBERS.get(m[1]), m[2], m[3], m[4], m[5], m[6]

        # Invalid
        else:
            self.epoch = None
            return self

        epoch = _timegm(float(s), int(mi), int(h), int(day), month, int(year))
        self.epoch = epoch + offset if epoch is not None and epoch + offset >= 0 else None
        return self

    # Not in Mojolicious: strftime of datetime of the standard library, as a method that chains, which Collection.map
    # calls by its name
    def strftime(self, format: str) -> Pyjo.String.Unicode.object:
        """::

            string = date.strftime('%Y-%m-%d')

        Format date in UTC with the directives of
        :meth:`datetime.datetime.strftime`. ::

            # "19941106T084937Z"
            Pyjo.Date.new(784111777).strftime('%Y%m%dT%H%M%SZ')

            # "1994, 2014"
            Pyjo.Collection.c(Pyjo.Date.new(784111777), Pyjo.Date.new(1408567500)).map('strftime', '%Y').join(', ')
        """
        return Pyjo.String.Unicode.new(self.to_datetime().strftime(format))

    # Not in Mojolicious: datetime of the standard library
    def to_datetime(self) -> datetime:
        """::

            dt = date.to_datetime()

        Turn date into a :class:`datetime.datetime` in UTC, for the standard library. ::

            # datetime.datetime(1994, 11, 6, 8, 49, 37, tzinfo=datetime.timezone.utc)
            Pyjo.Date.new(784111777).to_datetime()
        """
        return datetime.fromtimestamp(self.epoch or 0, UTC)

    # Renamed from Mojolicious: to_datetime, the name of the conversion to the
    # datetime of the standard library here
    def to_rfc3339(self) -> str:
        """::

            string = date.to_rfc3339()

        Render :rfc:`3339` date and time. ::

            # "1994-11-06T08:49:37Z"
            Pyjo.Date.new(784111777).to_rfc3339()

            # "1994-11-06T08:49:37.21Z"
            Pyjo.Date.new(784111777.21).to_rfc3339()
        """
        # RFC 3339 (1994-11-06T08:49:37Z)
        epoch = self.epoch or 0
        t = time.gmtime(epoch)
        string = f'{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}T{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}'
        m = re.search(r'(\.\d+)$', _number(epoch))
        return string + (m[1] if m else '') + 'Z'

    def to_str(self) -> str:
        """::

            string = date.to_str()

        Render date suitable for HTTP messages. ::

            # "Sun, 06 Nov 1994 08:49:37 GMT"
            Pyjo.Date.new(784111777).to_str()
        """
        # RFC 7231 (Sun, 06 Nov 1994 08:49:37 GMT)
        t = time.gmtime(self.epoch or 0)
        # Python counts the days of the week from Monday, Perl from Sunday
        day, month = DAYS[(t.tm_wday + 1) % 7], MONTHS[t.tm_mon - 1]
        return f'{day}, {t.tm_mday:02d} {month} {t.tm_year:04d} {t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d} GMT'


def _number(number: int | float) -> str:
    # A number as Perl stringifies it: no ".0" for a whole float
    return repr(number) if isinstance(number, float) and not number.is_integer() else str(int(number))


def _timegm(s: float, mi: int, h: int, day: int, month: int | None, year: int) -> int | float | None:
    # Time::Local's timegm, with None instead of an exception for a value out of
    # range

    # Years 0 to 99 are within 50 years of the current one, 100 to 999 count
    # from 1900
    if year < 100:
        this_year = time.localtime().tm_year
        year += this_year - this_year % 100
        if year > this_year + 50:
            year -= 100
        elif year <= this_year - 50:
            year += 100
    elif year < 1000:
        year += 1900

    # Unlike Mojolicious: an unknown month name is invalid, where Perl takes undef
    # as 0, January, with a warning; and a year after 9999 is invalid, where
    # datetime, which calendar.timegm uses, ends
    if month is None or not 0 <= month <= 11 or year > 9999:
        return None
    month_days = calendar.monthrange(2000 if calendar.isleap(year) else 2001, month + 1)[1]
    if not (1 <= day <= month_days and 0 <= h <= 23 and 0 <= mi <= 59 and 0 <= s < 60):
        return None

    epoch = calendar.timegm((year, month + 1, day, h, mi, int(s), 0, 0, 0))
    return epoch + (s - int(s)) if s != int(s) else epoch


new = Pyjo_Date.new
object = Pyjo_Date
Date = Pyjo_Date
