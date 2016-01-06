import time
import logging
import importlib

from pplugins import plugins

class MyPluginRunner(plugins.PluginRunner):
    def _load_plugin(self):
        return importlib.import_module("%s_plugin" % self.plugin)


class MyPluginManager(plugins.PluginManager):
    plugin_runner = MyPluginRunner

    def _stop_plugin(self, name):
        # Attempt to send clean shutdown signal to plugin
        self.plugins[name]['events'].put(None)

        self.logger.info(
                "Waiting up to 10 seconds for plugin %s to shutdown" % name)

        self.plugins[name]['process'].join(10)


if __name__ == '__main__':
    # Get some output
    logging.basicConfig(level=logging.INFO)

    manager = MyPluginManager()

    # Example starting a plugin, wait 2 secs, stop it
    manager.start_plugin('example')
    time.sleep(2)
    manager.stop_plugin('example')
