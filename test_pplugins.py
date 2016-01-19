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
def test_plugin_constructor():
    interface = "TEST"

    with patch.object(pplugins.Plugin, 'run') as mock_method:
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
