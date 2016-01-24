import logging
import inspect
import threading
import multiprocessing
from abc import ABCMeta, abstractmethod

from six import add_metaclass


class PluginError(Exception):
    """Custom Exception class to store plugin name with exception"""
    def __init__(self, message, plugin):
        super(PluginError, self).__init__(message, plugin)

        self.plugin = plugin

    def __str__(self):
        return "%s (plugin: %s)" % (self.args[0], self.plugin)


class PluginInterface(object):
    """Facilitates communication between the plugin and the parent process"""
    def __init__(self, event_queue, message_queue):
        self.events = event_queue
        self.messages = message_queue


@add_metaclass(ABCMeta)
class Plugin(object):
    """Abstract class for plugins to implement"""

    def __init__(self, interface):
        self.interface = interface

        # Plugins should implement the run() method
        self.run()

    @abstractmethod
    def run(self):
        """This method must be overridden by the plugin."""


@add_metaclass(ABCMeta)
class PluginRunner(multiprocessing.Process):
    """Finds and runs a plugin. Entry point to the child process."""

    interface = PluginInterface
    """Interface class to instantiate and pass to the plugin"""

    plugin_class = Plugin
    """Plugin class which must be subclassed by plugins"""

    def __init__(self, plugin, event_queue, message_queue):
        super(PluginRunner, self).__init__()

        self.plugin = plugin
        self.event_queue = event_queue
        self.message_queue = message_queue

        # Terminate the plugin if the plugin manager terminates
        self.daemon = True

    def run(self):
        """Instantiates the first Plugin subclass in the plugin's module"""
        interface = self.interface(self.event_queue, self.message_queue)

        cls = self._find_plugin()

        try:
            cls(interface)
        except:
            logging.getLogger(__name__).exception(
                "Error running plugin %s", self.plugin)

    def _find_plugin(self):
        """Returns the first Plugin subclass in the plugin module.

        Raises:
            PluginError -- If no subclass of Plugin is found.
        """
        module = self._load_plugin()

        cls = None
        for _, obj in inspect.getmembers(module, self._is_plugin):
            cls = obj
            break

        if cls is None:
            raise PluginError("Unable to find a Plugin class (a class "
                              "subclassing %s)" % self.plugin_class,
                              self.plugin)

        return cls

    def _is_plugin(self, obj):
        """Returns whether a given object is a class extending Plugin"""
        return inspect.isclass(obj) and self.plugin_class in obj.__bases__

    @abstractmethod
    def _load_plugin(self):
        """This method must be overridden to return a Python module.

        A Plugin class should exist in the module returned by this method.
        """


@add_metaclass(ABCMeta)
class PluginManager(object):
    """Finds, launches, and stops plugins"""

    plugin_runner = PluginRunner

    def __init__(self):
        self.plugins = {}
        self.logger = logging.getLogger(__name__)
        self.reap_lock = threading.RLock()

    def __enter__(self):
        # Reap plugin processes every 5 seconds
        self._start_reaping_thread()

        return self

    def __exit__(self, type, value, traceback):
        self._stop_reaping_thread()

    def start_plugin(self, name):
        """Attempt to start a new process-based plugin.

        Keyword arguments:
            name -- Plugin name to start.
        """
        self.reap_plugins()

        # Don't run two instances of the same plugin
        if name in self.plugins:
            raise PluginError("Plugin is already running", name)

        self.logger.info("Starting plugin %s", name)

        data = {
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

        self.logger.info("Started plugin %s", name)
        self.plugins[name] = data

    def stop_plugin(self, name):
        """Stops a plugin process. Tries cleanly, forcefully, then gives up.

        Keyword arguments:
            name -- Plugin name to stop.
        """
        self.reap_plugins()

        self.logger.info("Stopping plugin %s", name)

        if name not in self.plugins:
            self.logger.info("Plugin %s isn't running", name)
            return

        # Try cleanly shutting it down
        self._stop_plugin(name)

        # Make sure it died or send SIGTERM
        if self.plugins[name]['process'].is_alive():
            self.logger.info("Forcefully killing plugin %s (SIGTERM)", name)
            self.plugins[name]['process'].terminate()

        del self.plugins[name]

    def process_messages(self):
        """Handles any messages from children"""
        self.reap_plugins()

        for name, plugin in self.plugins.items():
            while not plugin['messages'].empty():
                self._process_message(name, plugin['messages'].get())

    def reap_plugins(self):
        """Reaps any children processes that terminated"""
        with self.reap_lock:
            self.logger.debug("Reaping plugin processes")

            # Create a new list for plugins that are still alive
            self.plugins = {
                name: plugin for name, plugin in self._living_plugins()
            }

    def _living_plugins(self):
        """Checks all plugins to see if they're alive, yields living plugins"""
        for name, plugin in self.plugins.items():
            # Don't add dead processes to our new plugin list
            if not plugin['process'].is_alive():
                self.logger.warning("Plugin %s terminated unexpectedly", name)
                continue

            yield (name, plugin)

    def _start_reaping_thread(self):
        self.reap_timer = threading.Timer(5, self.reap_plugins)
        self.reap_timer.start()

    def _stop_reaping_thread(self):
        self.reap_timer.cancel()
        self.reap_timer.join()

    @abstractmethod
    def _stop_plugin(self, name):
        """This method must be overridden to send a clean shutdown signal."""

    def _process_message(self, plugin, message):
        """This method should be overridden by subclasses.

        Processes a message from a plugin.

        Keyword argument:
            plugin -- The name of the plugin that sent the message
            message -- Could be any pickle-able object sent from the plugin
        """
        raise NotImplementedError(
            "Subclasses should implement _process_message()")
