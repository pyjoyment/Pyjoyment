import Pyjo.Collection
import Pyjo.Date
import Pyjo.String.Unicode

from Pyjo.Test import *

from datetime import UTC, datetime, timedelta, timezone
from email.utils import format_datetime, parsedate_to_datetime


with subtest('From datetime'):
    is_ok(Pyjo.Date.new(datetime(1994, 11, 6, 8, 49, 37, tzinfo=UTC)).epoch, 784111777, 'aware, UTC')
    dt = datetime(1994, 11, 6, 9, 49, 37, tzinfo=timezone(timedelta(hours=1)))
    is_ok(Pyjo.Date.new(dt).epoch, 784111777, 'aware, other time zone')
    dt = datetime(1994, 11, 6, 8, 49, 37)
    is_ok(Pyjo.Date.new(dt).epoch, int(dt.timestamp()), 'naive is local time, as datetime.timestamp')
    dt = datetime(1994, 11, 6, 8, 49, 37, 330000, tzinfo=UTC)
    is_ok(Pyjo.Date.new(dt).epoch, 784111777.33, 'microseconds')
    is_ok(Pyjo.Date.new().parse(dt).to_rfc3339(), '1994-11-06T08:49:37.33Z', 'parse')

with subtest('To datetime'):
    dt = Pyjo.Date.new(784111777).to_datetime()
    isa_ok(dt, datetime, 'dt')
    is_ok(dt, datetime(1994, 11, 6, 8, 49, 37, tzinfo=UTC), 'right value')
    is_ok(dt.tzinfo, UTC, 'aware, UTC')
    is_ok(Pyjo.Date.new(784111777.33).to_datetime().microsecond, 330000, 'microseconds')
    is_ok(Pyjo.Date.new('garbage').to_datetime(), datetime(1970, 1, 1, tzinfo=UTC), 'no epoch is the epoch, as to_str')

with subtest('Roundtrip'):
    date = Pyjo.Date.new('Sun, 06 Nov 1994 08:49:37 GMT')
    is_ok(Pyjo.Date.new(date.to_datetime()).epoch, date.epoch, 'Pyjo.Date -> datetime -> Pyjo.Date')

with subtest('Numbers'):
    date = Pyjo.Date.new(784111777.33)
    is_ok(float(date), 784111777.33, 'float')
    is_ok(int(date), 784111777, 'int')
    is_ok(datetime.fromtimestamp(float(date), UTC).microsecond, 330000, 'datetime.fromtimestamp(float(date))')

with subtest('Format'):
    date = Pyjo.Date.new(784111777.33)
    is_ok(f'{date:%Y%m%dT%H%M%SZ}', '19941106T084937Z', 'f-string, as the time stamp of Signature Version 4 of AWS')
    is_ok(format(date, '%Y%m%d'), '19941106', 'format')
    is_ok('{:%a, %d %b %Y}'.format(date), 'Sun, 06 Nov 1994', 'str.format')  # noqa: UP032
    is_ok(f'{date:%f}', '330000', 'microseconds')
    is_ok(f'{date}', 'Sun, 06 Nov 1994 08:49:37 GMT', 'no format is to_str')
    is_ok(f'{date:%Y-%m-%d}', f'{date.to_datetime():%Y-%m-%d}', 'as datetime in UTC')
    is_ok(f'{Pyjo.Date.new("garbage"):%Y}', '1970', 'no epoch is the epoch, as to_str')
    is_ok(type(format(date, '%Y')), str, 'format gives a str')

with subtest('strftime'):
    date = Pyjo.Date.new(784111777.33)
    isa_ok(date.strftime('%Y'), Pyjo.String.Unicode.object, 'a string that chains')
    is_ok(date.strftime('%Y%m%dT%H%M%SZ'), '19941106T084937Z', 'right format')
    is_ok(date.strftime('%Y-%m-%d'), date.to_datetime().strftime('%Y-%m-%d'), 'as datetime in UTC')
    is_ok(date.strftime('%Y%m%d').encode(), b'19941106', 'chain')
    is_ok(
        Pyjo.Collection.c(date, Pyjo.Date.new(1408567500)).map('strftime', '%Y').join(', '),
        '1994, 2014',
        'Collection.map by the name of the method',
    )

with subtest('email.utils'):
    date = Pyjo.Date.new(784111777)
    is_ok(parsedate_to_datetime(str(date)), date.to_datetime(), 'parsedate_to_datetime')
    is_ok(format_datetime(date.to_datetime(), usegmt=True), str(date), 'format_datetime')

done_testing()
