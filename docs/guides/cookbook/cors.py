from Pyjoyment.Lite import *


# The pages of the frontend, also of its development server, read the API with the cookies of the session
ORIGINS = ['https://app.example.com', 'http://localhost:5173']
plugin('AllowedHosts', hosts=['api.example.com', 'localhost'], origins=ORIGINS)
plugin('CORS', origins=ORIGINS, credentials=True, paths=['/api'])


@get('/api/user')
def user(c):
    c.render(json={'name': c.session('name')})


app.start()
