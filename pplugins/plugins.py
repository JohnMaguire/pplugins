import logging
import inspect
import importlib
import multiprocessing

from pplugins.exceptions import (PluginError, PluginNotFoundError)


class PluginInterface(object):
    def __init__(self, event_queue, result_queue):
        self.event_queue = event_queue
        self.result_queue = result_queue

    def add_result(self, result):
        self.result_queue.put(result)

    def get_event(self):
        return self.event_queue.get()


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
        return importlib.import_module("%s_plugin" % self.plugin)

    def _is_plugin(self, obj):
        """Returns whether a given object is a class extending Plugin"""
        return inspect.isclass(obj) and Plugin in obj.__bases__

    def _find_plugin(self):
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
        """Attempt to start a new plugin"""
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
        self.reap_plugins()

        if name not in self.plugins:
            # FIXME: Throw an exception so calling class can handle?
            self.logger.info("Plugin %s isn't running" % name)
            return

        # Time to wait for process to cleanup
        wait_time = 10

        # Attempt to send clean shutdown signal to plugin
        self.logger.info("Waiting up to %s seconds for plugin %s to shutdown" %
                         (wait_time, name))
        # FIXME: Make this a PluginEvent?
        self.plugins[name]['events'].put(None)
        self.plugins[name]['process'].join(wait_time)

        # Make sure it died or send SIGTERM
        if self.plugins[name]['process'].is_alive():
            self.logger.info("Forcefully killing plugin %s (SIGTERM)" % name)
            self.plugins[name]['process'].terminate()

            self.logger.info("Waiting up to %s seconds for plugin %s to die" %
                             (wait_time, name))

        # Make sure plugin is definitely dead now, or just ignore it
        self.plugins[name]['process'].join(wait_time)
        if self.plugins[name]['process'].is_alive():
            self.logger.error("Unable to kill plugin %s -- ignoring it" %
                              name)
        else:
            self.logger.info("Successfully shut down plugin %s" % name)

        del self.plugins[name]

    def process_messages(self):
        """Handles any messages from children"""
        self.reap_plugins()

        for plugin in self.plugins:
            while not plugin['messages'].empty():
                self.process_message(plugin['messages'].get())

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

        self.loop()

    def loop(self):
        """This should be overridden by the Plugin"""
        print("child, Looping")

        while True:
            event = self.interface.get_event()
            if event is None:
                print("child, Exiting")
                break
