from queue import Queue


class SpeechQueue:
    """
    Queue containing completed speech segments.
    """

    def __init__(self):

        self.queue = Queue()

    def put(self, segment):

        self.queue.put(segment)

    def get(self):

        return self.queue.get()

    def empty(self):

        return self.queue.empty()

    def size(self):

        return self.queue.qsize()