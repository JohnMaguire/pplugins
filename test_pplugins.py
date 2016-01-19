import pytest

import pplugins


def test_pluginmanager_abstract():
    with pytest.raises(TypeError):
        pplugins.PluginManager()


def test_pluginrunner_abstract():
    with pytest.raises(TypeError):
        pplugins.PluginRunner()
