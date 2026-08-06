from threading import Lock


class TranscriptManager:

    def __init__(self):

        self.transcripts = []

        self.lock = Lock()

    def add(self, text):

        if not text:
            return

        with self.lock:

            self.transcripts.append(text)

    def get_all(self):

        with self.lock:

            return "\n".join(self.transcripts)

    def clear(self):

        with self.lock:

            self.transcripts.clear()