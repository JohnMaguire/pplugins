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


def test_plugininterface_add_message():
    msg = "TEST"

    with patch.object(Queue.Queue, 'put', return_Value=None) as mock_method:
        queue = Queue.Queue()

        pi = pplugins.PluginInterface(None, queue)
        pi.add_message(msg)

    mock_method.assert_called_once_with(msg)


@pytest.mark.parametrize("params,exp_block,exp_timeout", (
    ({}, True, None),
    ({'block': None, 'timeout': None}, None, None),
    ({'block': True, 'timeout': False}, True, False),
    ({'block': False, 'timeout': True}, False, True)
))
def test_plugininterface_get_event(params, exp_block, exp_timeout):
    return_value = 'TEST'
    with patch.object(
            Queue.Queue, 'get', return_value=return_value) as mock_method:
        queue = Queue.Queue()

        pi = pplugins.PluginInterface(queue, None)
        assert pi.get_event(**params) == return_value

    mock_method.assert_called_once_with(exp_block, exp_timeout)


@patch.multiple(pplugins.Plugin, __abstractmethods__=set())
@patch.object(pplugins.Plugin, 'run')
def test_plugin_constructor(mock_method):
    interface = "TEST"

    plugin = pplugins.Plugin(interface)
    assert plugin.interface == interface

    mock_method.assert_called_once_with()


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
    with patch.object(pplugins.PluginRunner, '_load_plugin',
                      return_value=plugin) as load_plugin_mock:
        pr = pplugins.PluginRunner('test', None, None)
        with pytest.raises(pplugins.PluginError) as excinfo:
            pr.run()

    # assert the overrided _load_plugin() got called
    load_plugin_mock.assert_called_once_with()

    # assert that an exception was raised that we were unable to find a plugin
    assert str(pr.plugin_class) in str(excinfo.value)
    assert 'Unable to find' in str(excinfo.value)


@patch.multiple(pplugins.PluginRunner, __abstractmethods__=set())
def test_pluginrunner_run():
    # Create mock plugin class and module
    class MyPlugin(pplugins.Plugin):
        def run(self):
            pass
    plugin_module = type('Module', (), {'MyPlugin': MyPlugin})

    pr = pplugins.PluginRunner(None, None, None)

    with patch.object(pplugins.PluginRunner, '_load_plugin',
                      return_value=plugin_module):
        pr.run()
