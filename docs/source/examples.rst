*************
Example Usage
*************

pplugins is a framework for creating plugin management systems based on the standard multiprocessing module.

In order to use it effectively, you will need to extend and implement a few methods.

Extending the Framework
=======================
.. code-block:: python
    :linenos:

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

Creating Plugins
================
.. code-block:: python
    :linenos:

    from six import queue
    import time
    import logging

    from pplugins import Plugin

    class ExamplePlugin(Plugin):
        """Don't do anything special"""

        def __init__(self, *args, **kwargs):
            self.logger = logging.getLogger(__name__)

            super(ExamplePlugin, self).__init__(*args, **kwargs)

        def run(self):
            self.logger.info("Child, started!")

            while True:
                try:
                    event = self.interface.events.get(block=False)
                except Queue.Empty:
                    self.logger.info("Child, no message. Waiting .5 seconds")
                    time.sleep(.5)
                    continue

                if event is None:
                    self.logger.info("Child, exiting.")
                    break
