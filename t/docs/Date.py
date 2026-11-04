from Pyjo.Test import *


with subtest('Synopsis'):
    from Pyjo.Date import Date

    # Parse
    date = Date('Sun, 06 Nov 1994 08:49:37 GMT')
    is_ok(date.epoch, 784111777, 'date.epoch')

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Date

    import time

    # Parse
    date = Pyjo.Date.new('Sun, 06 Nov 1994 08:49:37 GMT')
    is_ok(date.epoch, 784111777, 'date.epoch')

    # Build
    date = Pyjo.Date.new(time.time() + 60)
    like_ok(str(date), r'^\w{3}, \d{2} \w{3} \d{4} \d{2}:\d{2}:\d{2} GMT$', 'date')

with subtest('new'):
    from datetime import UTC, datetime

    date = Pyjo.Date.new()
    isa_ok(date, Pyjo.Date.object, 'date')
    before = int(time.time())
    date = Pyjo.Date.new(datetime.now(UTC))
    ok(date.epoch >= before, 'datetime')
    date = Pyjo.Date.new('Sun Nov  6 08:49:37 1994')
    is_ok(date.epoch, 784111777, 'date.epoch')

with subtest('epoch'):
    epoch = date.epoch
    is_ok(epoch, 784111777, 'epoch')
    date.epoch = 784111777
    is_ok(date.epoch, 784111777, 'date.epoch')

with subtest('__bool__'):
    boolean = bool(date)
    is_ok(boolean, True, 'boolean')

with subtest('__float__'):
    number = float(date)
    is_ok(number, 784111777.0, 'number')

    # datetime.datetime(1994, 11, 6, 8, 49, 37, tzinfo=datetime.timezone.utc)
    is_ok(
        datetime.fromtimestamp(float(Pyjo.Date.new(784111777)), UTC),
        datetime(1994, 11, 6, 8, 49, 37, tzinfo=UTC),
        'datetime.fromtimestamp(float(date), UTC)',
    )

with subtest('__format__'):
    string = format(date, '%Y%m%d')
    is_ok(string, '19941106', 'format')
    string = f'{date:%Y%m%dT%H%M%SZ}'
    is_ok(string, '19941106T084937Z', 'f-string')

    # "19941106T084937Z"
    is_ok(f'{Pyjo.Date.new(784111777):%Y%m%dT%H%M%SZ}', '19941106T084937Z', 'example')

with subtest('__int__'):
    number = int(date)
    is_ok(number, 784111777, 'number')

with subtest('__str__'):
    string = str(date)
    is_ok(string, 'Sun, 06 Nov 1994 08:49:37 GMT', 'string')

with subtest('parse'):
    date = date.parse('Sun Nov  6 08:49:37 1994')
    is_ok(date.epoch, 784111777, 'date.epoch')
    before = int(time.time())
    date = date.parse(datetime.now(UTC))
    ok(date.epoch >= before, 'datetime')
    date = date.parse(datetime(1994, 11, 6, 8, 49, 37, 210000, tzinfo=UTC))
    is_ok(date.epoch, 784111777.21, 'datetime with microseconds')

    # Epoch
    is_ok(Pyjo.Date.new('784111777').epoch, 784111777, "Pyjo.Date.new('784111777').epoch")
    is_ok(Pyjo.Date.new('784111777.21').epoch, 784111777.21, "Pyjo.Date.new('784111777.21').epoch")

    # RFC 822/1123
    is_ok(
        Pyjo.Date.new('Sun, 06 Nov 1994 08:49:37 GMT').epoch,
        784111777,
        "Pyjo.Date.new('Sun, 06 Nov 1994 08:49:37 GMT').epoch",
    )

    # RFC 850/1036
    is_ok(
        Pyjo.Date.new('Sunday, 06-Nov-94 08:49:37 GMT').epoch,
        784111777,
        "Pyjo.Date.new('Sunday, 06-Nov-94 08:49:37 GMT').epoch",
    )

    # Ansi C asctime()
    is_ok(Pyjo.Date.new('Sun Nov  6 08:49:37 1994').epoch, 784111777, "Pyjo.Date.new('Sun Nov  6 08:49:37 1994').epoch")

    # RFC 3339
    is_ok(Pyjo.Date.new('1994-11-06T08:49:37Z').epoch, 784111777, "Pyjo.Date.new('1994-11-06T08:49:37Z').epoch")
    is_ok(Pyjo.Date.new('1994-11-06T08:49:37').epoch, 784111777, "Pyjo.Date.new('1994-11-06T08:49:37').epoch")
    is_ok(
        Pyjo.Date.new('1994-11-06T08:49:37.21Z').epoch,
        784111777.21,
        "Pyjo.Date.new('1994-11-06T08:49:37.21Z').epoch",
    )
    is_ok(
        Pyjo.Date.new('1994-11-06T08:49:37+01:00').epoch,
        784108177,
        "Pyjo.Date.new('1994-11-06T08:49:37+01:00').epoch",
    )
    is_ok(
        Pyjo.Date.new('1994-11-06T08:49:37-01:00').epoch,
        784115377,
        "Pyjo.Date.new('1994-11-06T08:49:37-01:00').epoch",
    )

with subtest('strftime'):
    import Pyjo.Collection

    string = Pyjo.Date.new(784111777).strftime('%Y-%m-%d')
    is_ok(string, '1994-11-06', 'string')

    # "19941106T084937Z"
    is_ok(Pyjo.Date.new(784111777).strftime('%Y%m%dT%H%M%SZ'), '19941106T084937Z', 'example')

    # "1994, 2014"
    is_ok(
        Pyjo.Collection.c(Pyjo.Date.new(784111777), Pyjo.Date.new(1408567500)).map('strftime', '%Y').join(', '),
        '1994, 2014',
        'map',
    )

with subtest('to_datetime'):
    dt = date.to_datetime()
    is_ok(dt, datetime(1994, 11, 6, 8, 49, 37, 210000, tzinfo=UTC), 'dt')

    # datetime.datetime(1994, 11, 6, 8, 49, 37, tzinfo=datetime.timezone.utc)
    is_ok(
        Pyjo.Date.new(784111777).to_datetime(),
        datetime(1994, 11, 6, 8, 49, 37, tzinfo=UTC),
        'Pyjo.Date.new(784111777).to_datetime()',
    )

with subtest('to_rfc3339'):
    string = date.to_rfc3339()
    is_ok(string, '1994-11-06T08:49:37.21Z', 'string')

    # "1994-11-06T08:49:37Z"
    is_ok(Pyjo.Date.new(784111777).to_rfc3339(), '1994-11-06T08:49:37Z', 'Pyjo.Date.new(784111777).to_rfc3339()')

    # "1994-11-06T08:49:37.21Z"
    is_ok(
        Pyjo.Date.new(784111777.21).to_rfc3339(),
        '1994-11-06T08:49:37.21Z',
        'Pyjo.Date.new(784111777.21).to_rfc3339()',
    )

with subtest('to_str'):
    string = date.to_str()
    is_ok(string, 'Sun, 06 Nov 1994 08:49:37 GMT', 'string')

    # "Sun, 06 Nov 1994 08:49:37 GMT"
    is_ok(Pyjo.Date.new(784111777).to_str(), 'Sun, 06 Nov 1994 08:49:37 GMT', 'Pyjo.Date.new(784111777).to_str()')

done_testing()
