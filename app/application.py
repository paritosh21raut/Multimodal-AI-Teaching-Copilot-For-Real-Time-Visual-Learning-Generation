from app.audio.audio_pipeline import AudioPipeline
from app.utils.logger import app_logger


class Application:

    def __init__(self):

        app_logger.info("Initializing Application")

        self.pipeline = AudioPipeline()

    def start(self):

        app_logger.success("Application Started")

        self.pipeline.start()