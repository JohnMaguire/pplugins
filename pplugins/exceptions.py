class PluginError(Exception):
    def __init__(self, message, plugin):
        super(PluginError, self).__init__(message, plugin)

        self.plugin = plugin

    def __str__(self):
        return "%s (plugin: %s)" % (self.args[0], self.plugin)


class PluginNotFoundError(PluginError):
    pass
