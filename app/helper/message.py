import queue

from app.utils.singleton import Singleton


class MessageHelper(metaclass=Singleton):
    """
    Message queue manager
    """
    def __init__(self):
        self.queue = queue.Queue()

    def put(self, message: str):
        self.queue.put(message)

    def get(self):
        if not self.queue.empty():
            return self.queue.get(block=False)
        return None
