from pplugins.plugins import Plugin


class TestPlugin(Plugin):
    pass


def start(interface):
    TestPlugin(interface)
