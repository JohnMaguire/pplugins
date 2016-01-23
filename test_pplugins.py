from contextlib import nested
import multiprocessing
import threading
import Queue

import pytest
from mock import patch

import pplugins

DEFAULT = "default"


def test_pluginmanager_abstract():
    with pytest.raises(TypeError):
        pplugins.PluginManager()


def test_pluginrunner_abstract():
    with pytest.raises(TypeError):
        pplugins.PluginRunner()


def test_plugin_abstract():
    with pytest.raises(TypeError):
        pplugins.Plugin()


def test_pluginerror_plugin_property():
    try:
        raise pplugins.PluginError("Generic error", "test")
    except pplugins.PluginError as e:
        assert e.plugin == "test"


def test_pluginerror_str_contains_plugin_name():
    plugin_name = "test"

    try:
        raise pplugins.PluginError(None, plugin_name)
    except pplugins.PluginError as e:
        assert plugin_name in str(e)


@patch.multiple(pplugins.Plugin, __abstractmethods__=set())
@patch.object(pplugins.Plugin, 'run')
def test_plugin_constructor(run_mock):
    interface = pplugins.PluginInterface(None, None)
    plugin = pplugins.Plugin(interface)

    # Assert that the interface is set on the plugin object
    assert plugin.interface == interface

    run_mock.assert_called_once_with()


@patch.multiple(pplugins.PluginRunner, __abstractmethods__=set())
def test_pluginrunner_daemon_flag():
    pr = pplugins.PluginRunner(None, None, None)

    # multiprocessing daemon flag
    assert pr.daemon is True


@pytest.mark.parametrize("plugin", (
    type('Module', (), {}),
    # Testing that pplugins.Plugin doesn't count as a valid plugin
    pplugins,
))
@patch.multiple(pplugins.PluginRunner, __abstractmethods__=set())
def test_pluginrunner_run_exception(plugin):
    pr = pplugins.PluginRunner('test', None, None)
    with patch.object(pplugins.PluginRunner, '_load_plugin',
                      return_value=plugin) as load_plugin_mock:
        with pytest.raises(pplugins.PluginError) as excinfo:
            pr.run()

    # assert the overrided _load_plugin() got called
    load_plugin_mock.assert_called_once_with()

    # assert that an exception was raised that we were unable to find a plugin
    assert str(pr.plugin_class) in str(excinfo.value)
    assert 'Unable to find' in str(excinfo.value)


@pytest.fixture(params=["EmptyPlugin", "ErrorPlugin"])
def plugin(request):
    class EmptyPlugin(pplugins.Plugin):
        def run(self):
            pass

    class ErrorPlugin(pplugins.Plugin):
        def run(self):
            raise Exception

    # yeah, yeah, it's eval()
    return type('Module', (), {request.param: eval(request.param)})


@patch.multiple(pplugins.PluginRunner, __abstractmethods__=set())
def test_pluginrunner_run(plugin):
    pr = pplugins.PluginRunner(None, None, None)
    with patch.object(pplugins.PluginRunner, '_load_plugin',
                      return_value=plugin):
        pr.run()


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
    with nested(
            patch.object(multiprocessing.Process, 'is_alive',
                         return_value=True),
            patch.object(multiprocessing.Process, 'terminate',
                         return_value=None),
    ) as (_, terminate_mock):
        pm.stop_plugin('test')

    terminate_mock.assert_called_once_with()
    assert pm.plugins == {}
