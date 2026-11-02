use v5.14;

use Mojo::URL;

# 'ssh+git://git@github.com/pyjoyment/Pyjoyment.git'
my $url = Mojo::URL->new('https://github.com/pyjoyment/Pyjoyment');
say $url->scheme('ssh+git')->userinfo('git')->path($url->path . '.git')->to_unsafe_string;

# 'https://pypi.org/search/?q=Pyjoyment&o=&c=Programming+Language+%3A%3A+Python'
say Mojo::URL->new('https://pypi.org/search/')->query(q => 'Pyjoyment', o => '', c => 'Programming Language :: Python');
