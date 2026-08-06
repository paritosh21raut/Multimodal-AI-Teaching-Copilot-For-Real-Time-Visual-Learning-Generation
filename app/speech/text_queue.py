from queue import Queue


class TextQueue:
    """
    Queue for storing transcribed text.
    """

    def __init__(self):

        self.queue = Queue()

    def put(self, text):

        self.queue.put(text)

    def get(self):

        return self.queue.get()

    def empty(self):

        return self.queue.empty()

    def size(self):

        return self.queue.qsize()