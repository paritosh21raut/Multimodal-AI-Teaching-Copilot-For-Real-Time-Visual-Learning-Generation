from queue import Queue


class AudioQueue:
    """
    Thread-safe queue for passing audio
    between modules.
    """

    def __init__(self):

        self.queue = Queue()

    def put(self, chunk):

        self.queue.put(chunk)

    def get(self):

        return self.queue.get()

    def empty(self):

        return self.queue.empty()

    def size(self):

        return self.queue.qsize()