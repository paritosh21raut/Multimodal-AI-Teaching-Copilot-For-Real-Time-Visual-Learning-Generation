from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
import json
import time


# ============================================================
# STATE FILE
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

STATE_FILE = PROJECT_ROOT / "outputs" / "dashboard_state.json"


# ============================================================
# SNAPSHOT MODEL
# ============================================================

@dataclass
class DashboardSnapshot:

    running: bool = False

    microphone_status: str = "Ready"

    pipeline_stage: str = "Idle"

    transcript: str = ""

    transcript_history: list[str] = field(
        default_factory=list
    )

    topic: str = ""

    topic_confidence: float | None = None

    title: str = ""

    bullets: list[str] = field(
        default_factory=list
    )

    image: str = ""

    slide_number: int = 0

    slide_count: int = 0

    ppt_path: str = ""

    generation_status: str = "Waiting"

    error: str = ""

    last_update: float = 0.0


# ============================================================
# DASHBOARD STATE
# ============================================================

class DashboardState:

    def __init__(self):

        # RLock allows safe nested locking
        self.lock = RLock()

        STATE_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # ----------------------------------------------------
        # IMPORTANT
        # Do NOT overwrite an existing state file.
        # ----------------------------------------------------

        if STATE_FILE.exists():

            loaded = self._load_from_file()

            if loaded is not None:
                self._state = loaded
            else:
                self._state = DashboardSnapshot()

                self._save()

        else:

            self._state = DashboardSnapshot()

            self._save()

    # ========================================================
    # LOAD STATE FROM JSON
    # ========================================================

    def _load_from_file(self) -> DashboardSnapshot | None:

        try:

            if not STATE_FILE.exists():
                return None

            raw = STATE_FILE.read_text(
                encoding="utf-8"
            )

            if not raw.strip():
                return None

            data = json.loads(raw)

            return DashboardSnapshot(

                running=data.get(
                    "running",
                    False,
                ),

                microphone_status=data.get(
                    "microphone_status",
                    "Ready",
                ),

                pipeline_stage=data.get(
                    "pipeline_stage",
                    "Idle",
                ),

                transcript=data.get(
                    "transcript",
                    "",
                ),

                transcript_history=data.get(
                    "transcript_history",
                    [],
                ),

                topic=data.get(
                    "topic",
                    "",
                ),

                topic_confidence=data.get(
                    "topic_confidence",
                    None,
                ),

                title=data.get(
                    "title",
                    "",
                ),

                bullets=data.get(
                    "bullets",
                    [],
                ),

                image=data.get(
                    "image",
                    "",
                ),

                slide_number=data.get(
                    "slide_number",
                    0,
                ),

                slide_count=data.get(
                    "slide_count",
                    0,
                ),

                ppt_path=data.get(
                    "ppt_path",
                    "",
                ),

                generation_status=data.get(
                    "generation_status",
                    "Waiting",
                ),

                error=data.get(
                    "error",
                    "",
                ),

                last_update=data.get(
                    "last_update",
                    0.0,
                ),
            )

        except Exception as error:

            print(
                "[DashboardState] "
                f"Could not load state: {error}"
            )

            return None

    # ========================================================
    # SAVE STATE
    # ========================================================

    def _save(self):

        with self.lock:

            data = {

                "running": self._state.running,

                "microphone_status":
                    self._state.microphone_status,

                "pipeline_stage":
                    self._state.pipeline_stage,

                "transcript":
                    self._state.transcript,

                "transcript_history":
                    self._state.transcript_history,

                "topic":
                    self._state.topic,

                "topic_confidence":
                    self._state.topic_confidence,

                "title":
                    self._state.title,

                "bullets":
                    self._state.bullets,

                "image":
                    self._state.image,

                "slide_number":
                    self._state.slide_number,

                "slide_count":
                    self._state.slide_count,

                "ppt_path":
                    self._state.ppt_path,

                "generation_status":
                    self._state.generation_status,

                "error":
                    self._state.error,

                "last_update":
                    self._state.last_update,
            }

            temp_file = STATE_FILE.with_suffix(
                ".tmp"
            )

            temp_file.write_text(
                json.dumps(
                    data,
                    indent=2,
                ),
                encoding="utf-8",
            )

            temp_file.replace(
                STATE_FILE
            )

    # ========================================================
    # SNAPSHOT
    # ========================================================

    def snapshot(self) -> DashboardSnapshot:

        with self.lock:

            # =================================================
            # VERY IMPORTANT
            #
            # Streamlit and main.py are different processes.
            #
            # Therefore ALWAYS reload the JSON file before
            # returning the dashboard state.
            # =================================================

            file_state = self._load_from_file()

            if file_state is not None:

                self._state = file_state

            return DashboardSnapshot(

                running=self._state.running,

                microphone_status=
                    self._state.microphone_status,

                pipeline_stage=
                    self._state.pipeline_stage,

                transcript=
                    self._state.transcript,

                transcript_history=list(
                    self._state.transcript_history
                ),

                topic=
                    self._state.topic,

                topic_confidence=
                    self._state.topic_confidence,

                title=
                    self._state.title,

                bullets=list(
                    self._state.bullets
                ),

                image=
                    self._state.image,

                slide_number=
                    self._state.slide_number,

                slide_count=
                    self._state.slide_count,

                ppt_path=
                    self._state.ppt_path,

                generation_status=
                    self._state.generation_status,

                error=
                    self._state.error,

                last_update=
                    self._state.last_update,
            )

    # ========================================================
    # TRANSCRIPT
    # ========================================================

    def update_transcript(
        self,
        transcript: str,
    ):

        with self.lock:

            self._state.transcript = transcript

            if transcript:

                self._state.transcript_history.append(
                    transcript
                )

                self._state.transcript_history = (
                    self._state.transcript_history[-10:]
                )

            self._state.last_update = time.time()

            self._save()

    # ========================================================
    # TOPIC
    # ========================================================

    def update_topic(
        self,
        topic: str,
        confidence: float | None = None,
    ):

        with self.lock:

            self._state.topic = topic

            self._state.topic_confidence = confidence

            self._state.last_update = time.time()

            self._save()

    # ========================================================
    # SLIDE
    # ========================================================

    def update_slide(
        self,
        title: str,
        bullets: list[str],
        slide_number: int,
    ):

        with self.lock:

            self._state.title = title

            self._state.bullets = list(
                bullets
            )

            self._state.slide_number = (
                slide_number
            )

            self._state.last_update = time.time()

            self._save()

    # ========================================================
    # IMAGE
    # ========================================================

    def update_image(
        self,
        image: str,
    ):

        with self.lock:

            self._state.image = image

            self._state.last_update = time.time()

            self._save()

    # ========================================================
    # PPT
    # ========================================================

    def update_ppt(
        self,
        ppt_path: str,
        slide_count: int,
    ):

        with self.lock:

            self._state.ppt_path = ppt_path

            self._state.slide_count = (
                slide_count
            )

            self._state.last_update = time.time()

            self._save()

    # ========================================================
    # PIPELINE
    # ========================================================

    def set_pipeline(
        self,
        stage: str,
        status: str | None = None,
    ):

        with self.lock:

            self._state.pipeline_stage = stage

            if status is not None:

                self._state.generation_status = (
                    status
                )

            self._state.last_update = time.time()

            self._save()

    # ========================================================
    # RUNNING
    # ========================================================

    def set_running(
        self,
        running: bool,
    ):

        with self.lock:

            self._state.running = running

            self._state.last_update = time.time()

            self._save()

    # ========================================================
    # MICROPHONE
    # ========================================================

    def set_microphone(
        self,
        status: str,
    ):

        with self.lock:

            self._state.microphone_status = status

            self._state.last_update = time.time()

            self._save()

    # ========================================================
    # ERROR
    # ========================================================

    def set_error(
        self,
        error: str,
    ):

        with self.lock:

            self._state.error = error

            self._state.last_update = time.time()

            self._save()


# ============================================================
# GLOBAL INSTANCE
# ============================================================

dashboard_state = DashboardState()