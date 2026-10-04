# Multimodal AI Teaching Copilot for Real-Time Visual Learning Generation

Listens to a live lecture and builds a designed, continuity-aware educational display on the classroom
screen in real time. Visual simulation and story modes will follow.

- Status and progress: [`docs/STATE.md`](docs/STATE.md)
- Roadmap: [`docs/ROADMAP.md`](docs/ROADMAP.md)
- Architecture: [`docs/architecture/overview.md`](docs/architecture/overview.md)

## Quick start (Windows, Python 3.10)
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest
.venv/Scripts/python -m copilot --simulate tests/fixtures/lectures/photosynthesis.txt
```
