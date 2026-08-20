import threading
import time

from app.audio.voice_detector import VoiceDetector
from app.audio.audio_recorder import AudioRecorder
from app.speech.speech_segment_builder import SpeechSegmentBuilder
from app.speech.whisper_worker import WhisperWorker
from app.utils.logger import app_logger
from app.lecture.lecture_pipeline import lecture_pipeline
from app.dashboard.dashboard_state import dashboard_state
import traceback

class AudioWorker(threading.Thread):

    def __init__(self, audio_queue):

        super().__init__(daemon=True)

        self.audio_queue = audio_queue

        self.detector = VoiceDetector()

        self.builder = SpeechSegmentBuilder()

        self.recorder = AudioRecorder()

        self.whisper = WhisperWorker()

        self.recording = False

        self.silence_counter = 0

        self.running = True

    def run(self):

        app_logger.success("Audio Worker Started")

        while self.running:

            if self.audio_queue.empty():
                time.sleep(0.01)
                continue

            chunk = self.audio_queue.get()

            # Check if speech exists
            if self.detector.is_speech(chunk):

                # Speech started
                if not self.recording:

                    self.recording = True

                    self.builder.clear()

                    self.silence_counter = 0

                    app_logger.success("Speech Started")

                # Store speech chunk
                self.builder.add_chunk(chunk)

                self.silence_counter = 0

            else:

                # Ignore silence if we are not recording
                if not self.recording:
                    continue

                # Keep a little silence at the end
                self.builder.add_chunk(chunk)

                self.silence_counter += 1

                # Around 2 seconds of silence
                if self.silence_counter >= 80:

                    app_logger.success("Speech Finished")

                    audio = self.builder.get_audio()

                    if audio is not None:

                        filename = self.recorder.save(audio)

                        app_logger.success(f"Audio Saved : {filename}")

                        try:

                            app_logger.info("Starting Whisper...")

                            transcript = self.whisper.transcribe(filename)

                            app_logger.success("Transcription Completed")

                            dashboard_state.update_transcript(transcript)

                            print("\n" + "=" * 60)
                            print("TRANSCRIPT")
                            print("=" * 60)
                            print(transcript)
                            print("=" * 60 + "\n")

                            lecture_pipeline.process_transcript(transcript)

                        except Exception as e:
                            traceback.print_exc()
                            app_logger.error(e)

                    self.builder.clear()

                    self.recording = False

                    self.silence_counter = 0

    def stop(self):

        self.running = False