import Pyjo.Test
import Pyjo.Test.Pyjo

from notes.models import Note

import unittest

from config.server import app
from django.core.signals import request_finished, request_started
from django.db import close_old_connections
from django.test import TestCase


def setUpModule():
    unittest.enterModuleContext(Pyjo.Test.raise_failures())


# The requests of Pyjoyment reach the WSGIHandler of Django in the transaction of the test, whose handlers of
# request_started and request_finished would close its connection, so they are detached, as the test client of Django
# detaches them for its own requests
class ServerTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.t = cls.enterClassContext(Pyjo.Test.Pyjo.new(app))
        for signal in (request_started, request_finished):
            signal.disconnect(close_old_connections)
            cls.addClassCleanup(signal.connect, close_old_connections)

    def test_notes(self):
        Note.objects.create(text='first')
        self.t.get_ok('/').status_is(200).content_like(r'^1 notes')
        self.t.post_ok('/notes', form={'text': 'second'}).status_is(200).json_is('/notes', ['first', 'second'])

    def test_probes(self):
        self.t.get_ok('/livez').status_is(200)
        self.t.get_ok('/readyz').status_is(200)
        self.t.get_ok('/static/notes/notes.css').status_is(404)
        self.assertEqual(Note.objects.count(), 0)
