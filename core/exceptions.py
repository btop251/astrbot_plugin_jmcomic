class JmPluginError(Exception):
    pass


class JmImportError(JmPluginError):
    pass


class JmPermissionError(JmPluginError):
    pass


class JmTaskNotFoundError(JmPluginError):
    pass
