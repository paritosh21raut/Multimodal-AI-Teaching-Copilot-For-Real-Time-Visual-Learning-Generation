from __future__ import annotations

from app.images.image_downloader import download_image


class ImageManager:

    def get_image(self, query: str):

        return download_image(query)


image_manager = ImageManager()