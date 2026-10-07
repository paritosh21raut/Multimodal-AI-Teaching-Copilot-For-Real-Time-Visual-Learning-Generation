"""Materials and past lectures over HTTP (F-010): the teacher gets every file and the lecture list; a student on the
shared link gets only the PDFs the teacher shares — never a PPTX, an unshared PDF or a past lecture."""
import httpx
import pytest

from copilot.core.bus import EventBus
from copilot.display.hub import DisplayHub
from copilot.display.server import DisplayServer
from copilot.materials.archive import LectureArchive
from copilot.materials.store import MaterialStore
from tests.integration.test_display_hub import free_port
from tests.integration.test_share_access import KEY, TUNNEL
from tests.unit.test_materials import write_lecture


@pytest.fixture
async def stack(tmp_path):
    await write_lecture(tmp_path / "sessions", "L1")
    store = MaterialStore(tmp_path / "materials")
    shared = store.new("notes", "Week 1 notes", "Photosynthesis", ["L1"])
    store.file_for(shared).write_bytes(b"%PDF-1.4 shared")
    shared.status, shared.shared = "ready", True
    private = store.new("assignment", "", "Photosynthesis", ["L1"])
    store.file_for(private).write_bytes(b"%PDF-1.4 private")
    private.status = "ready"
    deck = store.new("pptx", "", "Photosynthesis", ["L1"])
    store.file_for(deck).write_bytes(b"PK pptx")
    deck.status = "ready"
    store.save()
    bus = EventBus()
    hub = DisplayHub(bus)
    hub.attach()
    archive = LectureArchive(tmp_path / "sessions", tmp_path / "archive.json", current_id="now")
    server = DisplayServer(hub, port=free_port(), control_key=KEY, archive=archive, materials=store)
    await server.start()
    yield server, shared, private, deck
    await server.stop()
    await bus.close()


async def test_students_download_only_shared_pdfs(stack):
    server, shared, private, deck = stack
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{server.port}", headers=TUNNEL) as student:
        r = await student.get(f"/api/materials/{shared.id}/file")
        assert r.status_code == 200 and r.content == b"%PDF-1.4 shared"
        assert "filename*=utf-8''Week%201%20notes.pdf" in r.headers["content-disposition"]  # the teacher's name
        assert (await student.get(f"/api/materials/{private.id}/file")).status_code == 403
        assert (await student.get(f"/api/materials/{deck.id}/file")).status_code == 403
        assert (await student.get("/api/lectures")).status_code == 403
        assert (await student.get("/api/lectures/L1")).status_code == 403
        assert (await student.get("/api/materials/nope/file")).status_code == 404


async def test_the_teacher_gets_everything(stack):
    server, shared, private, deck = stack
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{server.port}") as teacher:
        assert (await teacher.get(f"/api/materials/{private.id}/file")).status_code == 200
        r = await teacher.get(f"/api/materials/{deck.id}/file")
        assert r.status_code == 200 and "presentationml" in r.headers["content-type"]
        assert "attachment" in r.headers["content-disposition"]
        assert "inline" in (await teacher.get(f"/api/materials/{shared.id}/file?inline=1")).headers["content-disposition"]
        lectures = (await teacher.get("/api/lectures")).json()["lectures"]
        assert [(l["id"], l["title"], l["materials"]) for l in lectures] == [("L1", "Photosynthesis", 3)]
        one = (await teacher.get("/api/lectures/L1")).json()
        assert len(one["slides"]) == 5 and len(one["materials"]) == 3
        assert (await teacher.get("/api/lectures/..%2Fx")).status_code == 404
