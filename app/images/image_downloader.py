from __future__ import annotations

from pathlib import Path
import io
import re
import requests
from PIL import Image, UnidentifiedImageError

from app.config import PIXABAY_API_KEY


SAVE_DIR = Path("assets/images")
SAVE_DIR.mkdir(parents=True, exist_ok=True)

PIXABAY_URL = "https://pixabay.com/api/"

# Words that make Pixabay searches too generic/noisy.
STOP_WORDS = {
    "a",
    "an",
    "the",
    "of",
    "and",
    "or",
    "to",
    "for",
    "with",
    "from",
    "in",
    "on",
    "at",
    "by",
    "into",
    "showing",
    "displaying",
    "detailed",
    "detail",
    "clean",
    "futuristic",
    "realistic",
    "beautiful",
    "high",
    "quality",
    "image",
    "photo",
    "picture",
    "view",
    "illustration",
    "diagram",
    "architecture",
    "connected",
    "connection",
    "network",
    "labeled",
    "labelled",
    "including",
    "display",
    "generation",
    "creation",
    "process",
    "key",
    "main",
    "concept",
    "concepts",
}

# Words that are usually useful for educational images.
EDUCATIONAL_WORDS = {
    "biology",
    "biological",
    "plant",
    "photosynthesis",
    "chlorophyll",
    "glucose",
    "oxygen",
    "water",
    "carbon",
    "dioxide",
    "microcontroller",
    "microchip",
    "chip",
    "circuit",
    "electronics",
    "5g",
    "telecommunication",
    "telecommunications",
    "mobile",
    "network",
    "technology",
    "smart",
    "city",
    "iot",
    "bacteria",
    "bacterial",
    "microbiology",
    "microscopic",
    "cell",
    "cells",
    "mathematics",
    "math",
    "geometry",
    "circle",
    "circumference",
    "diameter",
    "radius",
    "pi",
    "physics",
    "science",
}


def _clean_query(query: str) -> str:
    """
    Convert Gemini's descriptive image query into a shorter
    Pixabay-friendly search query.

    Example:
        detailed biological diagram of plant photosynthesis
        displaying sunlight absorption water intake...
        
    becomes something closer to:
        biological plant photosynthesis sunlight water carbon dioxide glucose oxygen
    """

    query = str(query).strip().lower()

    # Keep 5G together.
    query = query.replace("5 g", "5g")

    # Remove punctuation.
    query = re.sub(r"[^a-z0-9\s\-]", " ", query)

    words = query.split()

    useful_words = []

    for word in words:
        if word in STOP_WORDS:
            continue

        if len(word) <= 1:
            continue

        useful_words.append(word)

    # Remove duplicate words while preserving order.
    unique_words = []

    for word in useful_words:
        if word not in unique_words:
            unique_words.append(word)

    # Prefer educational/technical terms.
    educational = [
        word for word in unique_words
        if word in EDUCATIONAL_WORDS
    ]

    other_words = [
        word for word in unique_words
        if word not in educational
    ]

    # Educational terms first.
    final_words = educational + other_words

    # Pixabay allows max 100 characters.
    cleaned = " ".join(final_words)[:100].strip()

    return cleaned


def _tokenize(text: str) -> set[str]:
    """
    Convert text into searchable tokens.
    """
    text = str(text).lower()
    text = text.replace("5 g", "5g")

    tokens = re.findall(r"[a-z0-9]+", text)

    return {
        token
        for token in tokens
        if len(token) > 1 and token not in STOP_WORDS
    }


def _score_result(hit: dict, query: str) -> float:
    """
    Score a Pixabay result according to how closely it matches
    the requested educational topic.
    """

    query_tokens = _tokenize(query)

    tags = _tokenize(hit.get("tags", ""))
    page_url = _tokenize(hit.get("pageURL", ""))

    # Pixabay doesn't always expose a title directly.
    # Tags are therefore the strongest relevance signal.
    matched_tags = query_tokens.intersection(tags)
    matched_url = query_tokens.intersection(page_url)

    score = 0.0

    # Strong reward for matching tags.
    score += len(matched_tags) * 10

    # Small reward for matching URL/topic information.
    score += len(matched_url) * 2

    # Educational/technical tags are preferred.
    educational_matches = matched_tags.intersection(EDUCATIONAL_WORDS)
    score += len(educational_matches) * 8

    # Prefer images with larger dimensions.
    width = hit.get("largeImageWidth", 0) or 0
    height = hit.get("largeImageHeight", 0) or 0

    if width >= 1000:
        score += 3

    if height >= 600:
        score += 2

    # Prefer landscape images because the current PPT layout
    # displays them beside the bullet points.
    if width > height:
        score += 5

    # Very small images are undesirable.
    if width < 500 or height < 300:
        score -= 10

    return score


def _is_valid_image(image_bytes: bytes) -> bool:
    """
    Make sure the downloaded response is actually a valid image.
    This prevents the PIL.UnidentifiedImageError currently
    breaking the Streamlit dashboard.
    """

    if not image_bytes:
        return False

    try:
        image = Image.open(io.BytesIO(image_bytes))

        # Force Pillow to actually decode the image.
        image.verify()

        return True

    except (UnidentifiedImageError, OSError, ValueError):
        return False


def _save_valid_image(image_bytes: bytes, filename: Path) -> bool:
    """
    Validate, reopen and normalize the image before saving.

    This guarantees that python-pptx receives a real image file
    instead of corrupted/HTML/invalid bytes.
    """

    try:
        image = Image.open(io.BytesIO(image_bytes))

        # Force complete decoding.
        image.load()

        # Normalize problematic formats/modes.
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")

        # JPEG does not support RGBA.
        if filename.suffix.lower() == ".jpg" and image.mode == "RGBA":
            background = Image.new("RGB", image.size, "white")
            background.paste(image, mask=image.getchannel("A"))
            image = background

        image.save(
            filename,
            format="JPEG",
            quality=95,
            optimize=True,
        )

        # Final validation of the file we actually wrote.
        with Image.open(filename) as check:
            check.verify()

        return True

    except (UnidentifiedImageError, OSError, ValueError):
        if filename.exists():
            try:
                filename.unlink()
            except OSError:
                pass

        return False


def _download_bytes(url: str) -> bytes | None:
    """
    Download an image safely.
    """

    try:
        response = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "Chrome/151.0 Safari/537.36"
                )
            },
        )

        response.raise_for_status()

        content = response.content

        if not content:
            return None

        # Validate before returning.
        if not _is_valid_image(content):
            return None

        return content

    except requests.RequestException as exc:
        print("[Image] Download failed:", exc)
        return None


def _search_pixabay(query: str, image_type: str) -> list[dict]:
    """
    Search Pixabay and return candidate images.

    We retrieve multiple results instead of blindly taking hit[0].
    """

    params = {
        "key": PIXABAY_API_KEY,
        "q": query,
        "image_type": image_type,
        "per_page": 20,
        "safesearch": "true",
        "orientation": "horizontal",
        "min_width": 500,
        "min_height": 300,
    }

    try:
        response = requests.get(
            PIXABAY_URL,
            params=params,
            timeout=20,
        )

        print("=" * 60)
        print("Pixabay Status:", response.status_code)
        print("Search Query:", query)
        print("Image Type:", image_type)
        print("=" * 60)

        response.raise_for_status()

        data = response.json()

        hits = data.get("hits", [])

        print("[Image] Pixabay candidates:", len(hits))

        return hits

    except (requests.RequestException, ValueError) as exc:
        print("[Image] Pixabay search failed:", exc)
        return []


def download_image(query: str):
    """
    Main image downloader.

    Existing architecture remains unchanged:

        query
          ↓
        Pixabay
          ↓
        choose best relevant result
          ↓
        validate downloaded bytes
          ↓
        convert to valid JPEG
          ↓
        return image path

    Returns:
        str  -> valid image path
        None -> no valid image found
    """

    original_query = str(query).strip()

    if not original_query:
        print("[Image] Empty query.")
        return None

    # ---------------------------------------------------------
    # 1. Simplify Gemini's long descriptive query.
    # ---------------------------------------------------------

    search_query = _clean_query(original_query)

    if not search_query:
        search_query = original_query[:100]

    print("=" * 60)
    print("IMAGE QUERY:")
    print(original_query)
    print("OPTIMIZED QUERY:")
    print(search_query)
    print("=" * 60)

    # ---------------------------------------------------------
    # 2. Search photos first.
    # ---------------------------------------------------------

    candidates = _search_pixabay(
        search_query,
        "photo",
    )

    # ---------------------------------------------------------
    # 3. If photo results are poor, also search illustrations.
    #
    # This is especially useful for:
    #   - biology diagrams
    #   - circuit diagrams
    #   - mathematical concepts
    #   - technical concepts
    # ---------------------------------------------------------

    illustration_candidates = _search_pixabay(
        search_query,
        "illustration",
    )

    all_candidates = candidates + illustration_candidates

    if not all_candidates:
        print("[Image] No Pixabay results found.")
        return None

    # ---------------------------------------------------------
    # 4. Score every candidate.
    # ---------------------------------------------------------

    scored_candidates = []

    for hit in all_candidates:
        score = _score_result(
            hit,
            search_query,
        )

        scored_candidates.append(
            (
                score,
                hit,
            )
        )

    # Highest score first.
    scored_candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    print("=" * 60)
    print("[Image] Ranked candidates:")

    for index, (score, hit) in enumerate(
        scored_candidates[:10],
        start=1,
    ):
        print(
            f"{index}. "
            f"score={score:.1f} | "
            f"tags={hit.get('tags', '')[:150]}"
        )

    print("=" * 60)

    # ---------------------------------------------------------
    # 5. Try the best candidates one by one.
    #
    # Important:
    # Even if Pixabay returns a result, the downloaded
    # largeImageURL can occasionally contain invalid data.
    #
    # We NEVER let that crash the pipeline.
    # ---------------------------------------------------------

    safe_query_name = re.sub(
        r"[^a-zA-Z0-9_\-]+",
        "_",
        search_query,
    ).strip("_")

    if not safe_query_name:
        safe_query_name = "generated_image"

    filename = SAVE_DIR / f"{safe_query_name}.jpg"

    for index, (score, hit) in enumerate(
        scored_candidates,
        start=1,
    ):

        image_url = (
            hit.get("largeImageURL")
            or hit.get("webformatURL")
            or hit.get("previewURL")
        )

        if not image_url:
            print(
                f"[Image] Candidate {index}: "
                "no usable image URL."
            )
            continue

        print(
            f"[Image] Trying candidate {index} "
            f"(score={score:.1f})"
        )

        image_bytes = _download_bytes(image_url)

        if image_bytes is None:
            print(
                f"[Image] Candidate {index} rejected: "
                "invalid image data."
            )
            continue

        # Save only after successful validation/conversion.
        if _save_valid_image(
            image_bytes,
            filename,
        ):
            print(
                f"[Image] Selected candidate {index}"
            )
            print(
                f"[Image] Saved -> {filename}"
            )
            print(
                f"[Image] Size -> "
                f"{Image.open(filename).size}"
            )
            print("=" * 60)

            return str(filename)

        print(
            f"[Image] Candidate {index} rejected "
            "during image conversion."
        )

    # ---------------------------------------------------------
    # 6. Nothing usable was found.
    # ---------------------------------------------------------

    print(
        "[Image] No valid image could be downloaded "
        "from the available Pixabay results."
    )
    print("=" * 60)

    return None