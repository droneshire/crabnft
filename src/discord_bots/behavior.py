# Base class for parsing and responding to messages
class OnMessage:
    HOTKEY = ""

    def response(cls, message) -> str:
        raise NotImplementedError()
