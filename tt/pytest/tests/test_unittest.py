import Pyjo.Test
import Pyjo.Test.Pyjo

from Pyjo.File import curfile

import unittest


def setUpModule():
    unittest.enterModuleContext(Pyjo.Test.raise_failures())


class TestMyApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = cls.enterClassContext(Pyjo.Test.Pyjo.new(curfile().dirname().sibling('myapp.py')))

    def test_index(self):
        self.t.get_ok('/').status_is(200).content_is('Hello')

    def test_wrong_content(self):
        self.t.get_ok('/').status_is(200).content_is('Bye')

    def test_skip_all(self):
        Pyjo.Test.plan(skip_all='not today')
