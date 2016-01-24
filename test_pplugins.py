import multiprocessing
import threading
import Queue

import pytest
from mock import patch

import pplugins

DEFAULT = "default"


def test_pluginerror():
    with pytest.raises(pplugins.PluginError) as exc_info:
        raise pplugins.PluginError("Generic error", "foo")

    assert exc_info.value.plugin == "foo"
    assert "foo" in str(exc_info.value)


def test_plugin_abstract():
    with pytest.raises(TypeError):
        pplugins.Plugin()


@patch.multiple(pplugins.Plugin, __abstractmethods__=set())
@patch.object(pplugins.Plugin, 'run')
def test_plugin_constructor(run_mock):
    interface = pplugins.PluginInterface(None, None)
    plugin = pplugins.Plugin(interface)

    # Assert that the interface is set on the plugin object
    assert plugin.interface == interface

    run_mock.assert_called_once_with()


def test_pluginrunner_abstract():
    with pytest.raises(TypeError):
        pplugins.PluginRunner()


@patch.multiple(pplugins.PluginRunner, __abstractmethods__=set())
def test_pluginrunner_constructor():
    pr = pplugins.PluginRunner(None, None, None)

    # multiprocessing daemon flag
    assert pr.daemon is True


@patch.multiple(pplugins.Plugin, __abstractmethods__=set())
@patch.multiple(pplugins.PluginRunner, __abstractmethods__=set())
def test_pluginrunner_run():
    pr = pplugins.PluginRunner(None, None, None)

    # assert plugin is called from pluginrunner
    class PluginStub(pplugins.Plugin):
        pass

    module = type('Module', (), {'PluginStub': PluginStub})

    with patch.object(pplugins.Plugin, '__init__', return_value=None), \
        patch.object(pplugins.PluginRunner, '_load_plugin',
                     return_value=module) as constructor_mock:
        pr.run()

    constructor_mock.assert_any_call()

    # ensure exceptions are caught
    class ErrorPluginStub(pplugins.Plugin):
        def __init__(self, _):
            raise Exception

    module = type('Module', (), {'ErrorPluginStub': ErrorPluginStub})
    with patch.object(pplugins.PluginRunner, '_load_plugin',
                      return_value=module):
        pr.run()

    # ensure exception is raised if a plugin can't be found
    module = type('Module', (), {})
    with pytest.raises(pplugins.PluginError) as excinfo, \
        patch.object(pplugins.PluginRunner, '_load_plugin',
                     return_value=module) as load_plugin_mock:
        pr.run()

    assert 'find' in str(excinfo.value)
    assert str(pr.plugin_class) in str(excinfo.value)

    # assert the overrided _load_plugin() got called
    load_plugin_mock.assert_called_once_with()


def test_pluginmanager_abstract():
    with pytest.raises(TypeError):
        pplugins.PluginManager()


@patch.multiple(pplugins.PluginManager, __abstractmethods__=set())
def test_pluginmanager_constructor():
    threads = threading.active_count()
    pplugins.PluginManager()

    # plugin manager should not have started the reaping thread when called
    # through the constructor
    assert threading.active_count() == threads


@patch.multiple(pplugins.PluginManager, __abstractmethods__=set())
def test_pluginmanager_contextmanager():
    threads = threading.active_count()
    with pplugins.PluginManager():
        # assert that reaping thread was started
        assert threading.active_count() == threads + 1

    # assert that reaping thread was stopped
    assert threading.active_count() == threads


@patch.multiple(pplugins.PluginRunner, __abstractmethods__=set())
@patch.multiple(pplugins.PluginManager, __abstractmethods__=set())
@patch.object(pplugins.PluginManager, 'reap_plugins', return_value=None)
@patch.object(multiprocessing.Process, 'start', return_value=None)
def test_pluginmanager_start_plugin(_, __):
    pm = pplugins.PluginManager()

    # test starting a plugin
    class PluginRunnerStub(pplugins.PluginRunner):
        def run(self):
            pass

    pm.plugin_runner = PluginRunnerStub
    pm.start_plugin('foo')
    assert 'foo' in pm.plugins

    # test plugin already running
    with pytest.raises(pplugins.PluginError) as excinfo:
            pm.start_plugin('foo')

    assert 'already running' in str(excinfo.value)

    # test error starting a plugin
    class PluginRunnerErrorStub(pplugins.PluginRunner):
        def __init__(self, _, __, ___):
            raise Exception

    pm.plugin_runner = PluginRunnerErrorStub
    with pytest.raises(Exception), patch.multiple(pm, plugins={}):
            pm.start_plugin('foo')


@patch.multiple(pplugins.PluginManager, __abstractmethods__=set())
@patch.object(pplugins.PluginManager, 'reap_plugins', return_value=None)
@patch.object(pplugins.PluginManager, '_stop_plugin', return_value=None)
def test_pluginmanager_stop_plugin(stop_plugin_mock, _):
    pm = pplugins.PluginManager()
    plugins = dict(test={'process': multiprocessing.Process()},
                   **pm.plugins)

    # non-existent plugin
    pm.stop_plugin('test')

    # cleanly
    pm.plugins = plugins
    with patch.object(multiprocessing.Process, 'is_alive', return_value=False):
        pm.stop_plugin('test')

    stop_plugin_mock.assert_called_once_with('test')
    assert pm.plugins == {}

    # forcefully
    plugins = dict(test={'process': multiprocessing.Process()},
                   **pm.plugins)
    pm.plugins = plugins
    with patch.object(multiprocessing.Process, 'is_alive',
                      return_value=True),  \
        patch.object(multiprocessing.Process, 'terminate',
                     return_value=None) as terminate_mock:
        pm.stop_plugin('test')

    terminate_mock.assert_called_once_with()
    assert pm.plugins == {}


@patch.object(pplugins.PluginManager, 'reap_plugins', return_value=None)
@patch.multiple(pplugins.PluginManager, __abstractmethods__=set())
def test_pluginmanager_process_messages(_):
    pm = pplugins.PluginManager()
    queue = Queue.Queue()
    pm.plugins = {'test': {'messages': queue}}

    # empty queue
    with patch.object(pplugins.PluginManager, '_process_message',
                      return_value=None) as process_message_mock:
        pm.process_messages()
    process_message_mock.assert_not_called()

    # with a message
    queue.put('test message')
    with patch.object(pplugins.PluginManager, '_process_message',
                      return_value=None) as process_message_mock:
        pm.process_messages()

    process_message_mock.assert_called_once_with('test', 'test message')


@patch.multiple(pplugins.PluginManager, __abstractmethods__=set())
def test_pluginmanager_reap_plugins():
    pm = pplugins.PluginManager()
    plugins = dict(test={'process': multiprocessing.Process()},
                   **pm.plugins)

    # reap dead processes
    pm.plugins = plugins
    with patch.object(multiprocessing.Process, 'is_alive', return_value=False):
        pm.reap_plugins()

    assert pm.plugins == {}

    # don't reap living processes
    pm.plugins = plugins
    with patch.object(multiprocessing.Process, 'is_alive', return_value=True):
        pm.reap_plugins()

    assert pm.plugins == plugins
