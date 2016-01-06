import time
import logging

from pplugins import plugins

def _find_plugins():
    """Any callable returning a dictionary in this format will do"""
    return {
        'example': 'example_plugin'
    }

if __name__ == '__main__':
    # Get some output
    logging.basicConfig(level=logging.INFO)

    manager = plugins.PluginManager(finder=_find_plugins)

    # Example starting a plugin, wait 2 secs, stop it
    manager.start_plugin('example')
    time.sleep(2)
    manager.stop_plugin('example')
