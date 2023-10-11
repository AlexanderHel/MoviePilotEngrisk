from queue import Queue, Empty

from app.log import logger
from app.utils.singleton import Singleton
from app.schemas.types import EventType


class EventManager(metaclass=Singleton):
    """
    Event manager
    """

    #  Event queue
    _eventQueue: Queue = None
    #  Event response function dictionary
    _handlers: dict = {}

    def __init__(self):
        #  Event queue
        self._eventQueue = Queue()
        #  Event response function dictionary
        self._handlers = {}

    def get_event(self):
        """
        Getting events
        """
        try:
            event = self._eventQueue.get(block=True, timeout=1)
            handlerList = self._handlers.get(event.event_type)
            return event, handlerList or []
        except Empty:
            return None, []

    def add_event_listener(self, etype: EventType, handler: type):
        """
        Register event handling
        """
        try:
            handlerList = self._handlers[etype.value]
        except KeyError:
            handlerList = []
            self._handlers[etype.value] = handlerList
        if handler not in handlerList:
            handlerList.append(handler)
            logger.debug(f"Event Registed：{etype.value} - {handler}")

    def remove_event_listener(self, etype: EventType, handler: type):
        """
        Remove the listener's handler function
        """
        try:
            handlerList = self._handlers[etype.value]
            if handler in handlerList[:]:
                handlerList.remove(handler)
            if not handlerList:
                del self._handlers[etype.value]
        except KeyError:
            pass

    def send_event(self, etype: EventType, data: dict = None):
        """
        Send event
        """
        if etype not in EventType:
            return
        event = Event(etype.value)
        event.event_data = data or {}
        logger.debug(f"Send event：{etype.value} - {event.event_data}")
        self._eventQueue.put(event)

    def register(self, etype: [EventType, list]):
        """
        Event registration
        :param etype:  Event type
        """

        def decorator(f):
            if isinstance(etype, list):
                for et in etype:
                    self.add_event_listener(et, f)
            elif type(etype) == type(EventType):
                for et in etype.__members__.values():
                    self.add_event_listener(et, f)
            else:
                self.add_event_listener(etype, f)
            return f

        return decorator


class Event(object):
    """
    Event object
    """

    def __init__(self, event_type=None):
        #  Event type
        self.event_type = event_type
        #  Dictionaries are used to hold specific event data
        self.event_data = {}


#  Instance reference， For registering events
eventmanager = EventManager()
