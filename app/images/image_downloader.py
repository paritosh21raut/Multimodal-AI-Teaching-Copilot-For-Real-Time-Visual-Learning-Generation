from __future__ import annotations

from pathlib import Path
import requests

from app.config import PIXABAY_API_KEY

SAVE_DIR = Path("assets/images")
SAVE_DIR.mkdir(parents=True, exist_ok=True)


def download_image(query: str):

    url = (
        "https://pixabay.com/api/"
        f"?key={PIXABAY_API_KEY}"
        f"&q={query.replace(' ', '+')}"
        "&image_type=photo"
        "&per_page=3"
    )

    response = requests.get(url)

    print("=" * 60)
    print("Pixabay Status:", response.status_code)
    print(response.text[:500])
    print("=" * 60)

    data = response.json()

    if not data["hits"]:
        return None

    image_url = data["hits"][0]["largeImageURL"]

    image = requests.get(image_url)

    filename = SAVE_DIR / (
        query.replace(" ", "_") + ".jpg"
    )

    with open(filename, "wb") as f:
        f.write(image.content)

    return str(filename)