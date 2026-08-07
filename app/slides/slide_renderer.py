from __future__ import annotations

from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.enum.text import PP_ALIGN
from pptx.util import Pt
from pptx.dml.color import RGBColor


class SlideRenderer:
    """
    Responsible only for formatting slides.

    This class DOES NOT:
        - Create presentations
        - Save presentations
        - Detect topics

    It ONLY styles slides.
    """

    TITLE_FONT_SIZE = 28
    BODY_FONT_SIZE = 20

    TITLE_COLOR = RGBColor(33, 37, 41)
    BODY_COLOR = RGBColor(60, 60, 60)

    def render_title_slide(
        self,
        slide,
        title: str,
        subtitle: str,
    ):

        title_box = slide.shapes.title

        title_box.text = title

        paragraph = title_box.text_frame.paragraphs[0]

        paragraph.font.size = Pt(self.TITLE_FONT_SIZE)

        paragraph.font.bold = True

        paragraph.font.color.rgb = self.TITLE_COLOR

        paragraph.alignment = PP_ALIGN.CENTER

        if len(slide.placeholders) > 1:

            subtitle_box = slide.placeholders[1]

            subtitle_box.text = subtitle

            paragraph = subtitle_box.text_frame.paragraphs[0]

            paragraph.font.size = Pt(16)

            paragraph.font.color.rgb = RGBColor(120, 120, 120)

            paragraph.alignment = PP_ALIGN.CENTER

    def render_content_slide(
        self,
        slide,
        title: str,
        bullets,
    ):

        # -------------------------------
        # Title
        # -------------------------------

        title_shape = slide.shapes.title
        title_shape.text = title

        title_para = title_shape.text_frame.paragraphs[0]
        title_para.font.size = Pt(self.TITLE_FONT_SIZE)
        title_para.font.bold = True
        title_para.font.color.rgb = self.TITLE_COLOR

        # -------------------------------
        # Find body placeholder
        # -------------------------------

        body = None

        for shape in slide.placeholders:

            if not hasattr(shape, "text_frame"):
                continue

            print(
                "[PPT]",
                shape.placeholder_format.idx,
                shape.placeholder_format.type,
                shape.name,
            )

            body = shape.text_frame

            if shape != title_shape:
                break

        if body is None:
            raise RuntimeError("No body placeholder found")

        # -------------------------------
        # Clear existing text
        # -------------------------------

        body.clear()

        # -------------------------------
        # Add bullets
        # -------------------------------

        for i, bullet in enumerate(bullets):

            if i == 0:
                p = body.paragraphs[0]
            else:
                p = body.add_paragraph()

            p.text = bullet
            p.level = 0
            p.font.size = Pt(self.BODY_FONT_SIZE)
            p.font.color.rgb = self.BODY_COLOR
            p.space_after = Pt(8)

        print("[PPT] Added", len(bullets), "bullets")


slide_renderer = SlideRenderer()