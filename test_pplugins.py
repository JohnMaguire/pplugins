import inspect
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


def test_pluginerror_constructor():
    try:
        raise pplugins.PluginError("Generic error", "test")
    except pplugins.PluginError as e:
        assert e.plugin == "test"


def test_pluginerror_str():
    try:
        raise pplugins.PluginError("Generic error", "test")
    except pplugins.PluginError as e:
        assert str(e) == "Generic error (plugin: test)"


def test_plugininterface_add_message():
    msg = "TEST"

    with patch.object(Queue.Queue, 'put', return_Value=None) as mock_method:
        queue = Queue.Queue()

        pi = pplugins.PluginInterface(None, queue)
        pi.add_message(msg)

    mock_method.assert_called_once_with(msg)


@pytest.mark.parametrize("block,timeout,exp_block,exp_timeout", [
    (DEFAULT, DEFAULT, True, None),
    (None, None, None, None),
    (True, False, True, False),
    (False, True, False, True)
])
def test_plugininterface_get_event(block, timeout, exp_block, exp_timeout):
    return_value = 'TEST'
    with patch.object(
            Queue.Queue, 'get', return_value=return_value) as mock_method:
        queue = Queue.Queue()

        pi = pplugins.PluginInterface(queue, None)
        if (block, timeout) == (DEFAULT, DEFAULT):
            assert pi.get_event() == return_value
        else:
            assert pi.get_event(block, timeout) == return_value

    mock_method.assert_called_once_with(exp_block, exp_timeout)


@patch.multiple(pplugins.Plugin, __abstractmethods__=set())
@patch.object(pplugins.Plugin, 'run')
def test_plugin_constructor(mock_method):
    interface = "TEST"

    plugin = pplugins.Plugin(interface)
    assert plugin.interface == interface

    mock_method.assert_called_once_with()


@patch.multiple(pplugins.PluginRunner, __abstractmethods__=set())
def test_pluginrunner_constructor():
    plugin = "test-plugin"
    event_queue = "test-events"
    result_queue = "test-events"
    log_queue = "test-logs"

    pr = pplugins.PluginRunner(plugin, event_queue, result_queue, log_queue)

    assert pr.plugin == plugin
    assert pr.event_queue == event_queue
    assert pr.result_queue == result_queue
    assert pr.log_queue == log_queue

    # multiprocessing daemon flag
    assert pr.daemon is True


@patch.multiple(pplugins.PluginRunner, __abstractmethods__=set())
def test_pluginrunner__is_plugin():
    class Plugin(pplugins.Plugin):
        pass

    pr = pplugins.PluginRunner(None, None, None, None)

    assert pr._is_plugin(pplugins.Plugin) is False
    assert pr._is_plugin(Plugin) is True


@patch.multiple(pplugins.PluginRunner, __abstractmethods__=set(),
                _load_plugin=lambda _: None)
def test_pluginrunner__find_plugin_no_plugin_exception():
    with pytest.raises(pplugins.PluginError) as excinfo:
        pr = pplugins.PluginRunner('test', None, None, None)
        pr._find_plugin()

    assert 'Unable to find a Plugin class' in str(excinfo.value)


@patch.multiple(pplugins.PluginRunner, __abstractmethods__=set())
@patch.object(inspect, 'getmembers', return_value=[(0, "ABC"), (0, "CDE")])
@patch.object(pplugins.PluginRunner, '_load_plugin', return_value="MODULE")
def test_pluginrunner__find_plugin(mock_load, mock_getmembers):
    pr = pplugins.PluginRunner('test', None, None, None)
    plugin = pr._find_plugin()

    # make sure it called _load_plugin
    mock_load.assert_called_once_with()

    # verify it passed _is_plugin and the module returned from _load_plugin
    mock_getmembers.assert_called_once_with("MODULE", pr._is_plugin)

    # verify it returns the first item from getmembers
    assert plugin == "ABC"
