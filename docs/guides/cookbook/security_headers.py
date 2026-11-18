"""
__DATA__

@@ index.html.ep
<!DOCTYPE html>
<html>
  <head>
    <title>Welcome</title>
    %= stylesheet('/app.css')
    %= javascript(begin
      document.addEventListener('DOMContentLoaded', () => console.log('Welcome!'));
    %= end)
  </head>
  <body><h1>Welcome</h1></body>
</html>
"""

from Pyjoyment.Lite import *


# A strict policy, tried out with the reports of the browsers while the default one is enforced, and a short HSTS
plugin(
    'SecurityHeaders',
    hsts={'max_age': 300},
    csp_report_only={
        'default-src': ["'self'"],
        'img-src': ["'self'", 'data:'],
        'frame-ancestors': ["'none'"],
    },
    reports='/csp-reports',
)


@get('/')
def index(c):
    c.render('index')


app.start()
