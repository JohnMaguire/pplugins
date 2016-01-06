import logging
import inspect
import importlib
import multiprocessing
from abc import abstractmethod

from pplugins.exceptions import (PluginError, PluginNotFoundError)


class PluginInterface(object):
    def __init__(self, event_queue, message_queue):
        self.event_queue = event_queue
        self.message_queue = message_queue

    def add_message(self, result):
        self.message_queue.put(result)

    def get_event(self, block=True, timeout=None):
        return self.event_queue.get(block, timeout)


class PluginRunner(multiprocessing.Process):
    interface = PluginInterface

    def __init__(self, plugin, event_queue, result_queue):
        super(PluginRunner, self).__init__()

        # Terminate the plugin if the plugin manager terminates
        self.daemon = True

        # FIXME: Use something process-safe
        self.logger = logging.getLogger(__name__)

        # Import the specified plugin module and create the interface back to
        # the main process
        self.plugin = plugin
        self.module = self._load_plugin()
        self.interface = self.interface(event_queue, result_queue)

    def _load_plugin(self):
        """Returns the module the Plugin subclass lives in.

        This method may be overriden by subclasses to adjust how a plugin's
        module is found. By default, we assume it lives in a module named
        <name>_plugin.
        """
        return importlib.import_module("%s_plugin" % self.plugin)

    def _is_plugin(self, obj):
        """Returns whether a given object is a class extending Plugin"""
        return inspect.isclass(obj) and Plugin in obj.__bases__

    def _find_plugin(self):
        """Returns the first Plugin subclass in the plugin module.

        Raises:
            PluginNotFoundError -- If no subclass of Plugin is found.
        """
        cls = None
        for name, obj in inspect.getmembers(self.module, self._is_plugin):
            cls = obj
            break

        if cls is None:
            raise PluginNotFoundError("Unable to find a Plugin class (a class "
                                      "subclassing pplugins.plugins.Plugin)",
                                      self.name)

        return cls

    def run(self):
        """Instantiates the first Plugin subclass in the plugin's module"""
        try:
            cls = self._find_plugin()
        except LookupError:
            self.logger.exception("Unable to find a valid plugin class in %s" %
                                  self.module_name)
            # FIXME: Pass error result back to Cardinal
            return

        try:
            cls(self.interface)
        except Exception:
            self.logger.exception("Error starting plugin")
            # FIXME: Pass error result back to Cardinal
            return


class PluginManager(object):
    """Finds, launches, and stops plugins"""

    plugin_runner = PluginRunner

    def __init__(self):
        # FIXME: Use something process-safe
        self.logger = logging.getLogger(__name__)

        self.plugins = {}

    def start_plugin(self, name):
        """Attempt to start a new process-based plugin.

        Keyword arguments:
            name -- Plugin name to start.
        """
        self.reap_plugins()

        # Don't run two instances of the same plugin
        if name in self.plugins:
            raise PluginError("Plugin is already running", name)

        self.logger.info("Starting plugin %s" % name)

        data = {
            'name': name,

            # Create an input and output queue
            'events': multiprocessing.Queue(),
            'messages': multiprocessing.Queue(),
        }

        try:
            data['process'] = self.plugin_runner(
                name, data['events'], data['messages'])
        except Exception:
            self.logger.exception("Unable to create plugin process")
            raise

        data['process'].start()

        self.logger.info("Started plugin %s" % name)
        self.plugins[name] = data

    def stop_plugin(self, name):
        """Stops a plugin process. Tries cleanly, forcefully, then gives up.

        Keyword arguments:
            name -- Plugin name to stop.
        """
        self.reap_plugins()

        self.logger.info("Stopping plugin %s" % name)

        if name not in self.plugins:
            self.logger.info("Plugin %s isn't running" % name)
            return

        # Try cleanly shutting it down
        self._stop_plugin(name)

        # Make sure it died or send SIGTERM
        if self.plugins[name]['process'].is_alive():
            self.logger.info("Forcefully killing plugin %s (SIGTERM)" % name)
            self.plugins[name]['process'].terminate()

            self.logger.info(
                    "Waiting up to 10 seconds for plugin %s to die" % name)

        # Make sure plugin is definitely dead now, or just ignore it
        self.plugins[name]['process'].join(10)
        if self.plugins[name]['process'].is_alive():
            self.logger.error(
                    "Unable to kill plugin %s -- ignoring it" % name)
        else:
            self.logger.info("Successfully shut down plugin %s" % name)

        del self.plugins[name]

    def _stop_plugin(self, name):
        """Attempts to cleanly shut down a plugin.

        This method may be overridden by subclasses to send a different signal
        or adjust the timeout to a desirable duration.
        """
        # Attempt to send clean shutdown signal to plugin
        self.logger.info(
                "Waiting up to 10 seconds for plugin %s to shutdown" % name)

        self.plugins[name]['events'].put(None)
        self.plugins[name]['process'].join(10)

    def process_messages(self):
        """Handles any messages from children"""
        self.reap_plugins()

        for plugin in self.plugins:
            while not plugin['messages'].empty():
                self._process_message(plugin['name'], plugin['messages'].get())

    def _process_message(self, plugin, message):
        """This method should be overridden by subclasses.

        Processes a message from a plugin.

        Keyword argument:
            plugin -- The name of the plugin that sent the message
            message -- Could be any pickle-able object sent from the plugin
        """
        raise NotImplementedError("Subclasses must implement _process_message()")

    def reap_plugins(self):
        """Reaps any children processes that terminated"""
        # Create a new list for plugins that are still alive
        self.plugins = {
            name: plugin for name, plugin in self._living_plugins()
        }

    def _living_plugins(self):
        """Checks all plugins to see if they're alive, yields living plugins"""
        for name, plugin in self.plugins.items():
            # Don't add dead processes to our new plugin list
            if not plugin['process'].is_alive():
                self.logger.warning("Plugin %s has terminated itself" % name)
                continue

            yield (name, plugin)


class Plugin(object):
    def __init__(self, interface):
        self.interface = interface

        # Plugins should implement the run() method
        self.run()

    @abstractmethod
    def run(self):
        """This method should be overridden by the Plugin."""
        pass
