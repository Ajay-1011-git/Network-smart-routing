class SmartRouteError(ValueError):
    """Actionable input or simulation failure."""


class ConfigurationError(SmartRouteError):
    pass


class PolicyError(SmartRouteError):
    pass


class EngineError(SmartRouteError):
    pass
