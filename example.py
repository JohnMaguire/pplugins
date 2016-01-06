import time
import logging

from pplugins import plugins

if __name__ == '__main__':
    # Get some output
    logging.basicConfig(level=logging.INFO)

    manager = plugins.PluginManager()

    # Example starting a plugin, wait 2 secs, stop it
    manager.start_plugin('example')
    time.sleep(2)
    manager.stop_plugin('example')
