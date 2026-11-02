import Pyjo.URL


# 'ssh+git://git@github.com/pyjoyment/Pyjoyment.git'
url = Pyjo.URL.new('https://github.com/pyjoyment/Pyjoyment')
print(url.set(scheme='ssh+git', userinfo='git', path=f'{url.path}.git').to_unsafe_str())

# 'https://pypi.org/search/?q=Pyjoyment&o=&c=Programming+Language+%3A%3A+Python'
url = Pyjo.URL.new('https://pypi.org/search/')
print(url.set(query=[('q', 'Pyjoyment'), ('o', ''), ('c', 'Programming Language :: Python')]))
