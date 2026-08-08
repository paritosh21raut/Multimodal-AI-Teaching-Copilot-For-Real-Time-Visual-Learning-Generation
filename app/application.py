from app.audio.audio_pipeline import AudioPipeline
from app.knowledge.content_generator import content_generator
from app.lecture.lecture_pipeline import lecture_pipeline
from app.slides.slide_manager import slide_manager
from app.topics.topic_intelligence import topic_intelligence
from app.utils.logger import app_logger
from app.ppt.ppt_manager import ppt_manager

class Application:

    def __init__(self):

        app_logger.info("Initializing Application")

        self.pipeline = AudioPipeline()

        lecture_pipeline.register_topic_detector(
            topic_intelligence
        )

        lecture_pipeline.register_content_generator(
            content_generator
        )

        lecture_pipeline.register_slide_manager(
            slide_manager
        )

        # NEW
        ppt_manager.create_new_presentation("Live Lecture")
        ppt_manager.add_title_slide(
            title="Live Lecture",
            subtitle="AI Teaching Copilot"
        )

        app_logger.success("Lecture Pipeline Ready")

    def start(self):

        app_logger.success("Application Started")

        self.pipeline.start()