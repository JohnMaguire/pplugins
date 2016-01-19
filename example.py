import time
import logging
import importlib

import pplugins


class MyPluginRunner(pplugins.PluginRunner):
    """Example plugin runner imports a module named <name>_plugin"""

    def _load_plugin(self):
        return importlib.import_module("%s_plugin" % self.plugin)


class MyPluginManager(pplugins.PluginManager):
    """Example plugin manager sets custom plugin runner and shutdown signal"""

    plugin_runner = MyPluginRunner

    def _stop_plugin(self, name):
        # Attempt to send clean shutdown signal to plugin
        self.plugins[name]['events'].put(None)

        self.logger.info(
            "Waiting up to 10 seconds for plugin %s to shutdown", name)

        self.plugins[name]['process'].join(10)


if __name__ == '__main__':
    # Get some output
    logging.basicConfig(level=logging.DEBUG)

    with MyPluginManager() as manager:
        # Example starting a plugin, wait 2 secs, stop it
        manager.start_plugin('example')
        time.sleep(15)
        manager.stop_plugin('example')
