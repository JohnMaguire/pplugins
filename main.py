import time
import logging

from pplugins import plugins

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    manager = plugins.PluginManager()

    manager.start_plugin('test')
    time.sleep(2)
    manager.stop_plugin('test')
