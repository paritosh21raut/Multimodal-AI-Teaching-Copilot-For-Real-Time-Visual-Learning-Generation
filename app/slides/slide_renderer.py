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

        slide.shapes.title.text = title

        title_para = slide.shapes.title.text_frame.paragraphs[0]

        title_para.font.size = Pt(self.TITLE_FONT_SIZE)

        title_para.font.bold = True

        title_para.font.color.rgb = self.TITLE_COLOR

        body = None

        for shape in slide.placeholders:

            if shape.placeholder_format.type == PP_PLACEHOLDER.BODY:
                body = shape.text_frame
                break

        if body is None:
            return

        body.clear()

        for index, bullet in enumerate(bullets):

            if index == 0:
                paragraph = body.paragraphs[0]
            else:
                paragraph = body.add_paragraph()

            paragraph.text = bullet

            paragraph.level = 0

            paragraph.font.size = Pt(self.BODY_FONT_SIZE)

            paragraph.font.color.rgb = self.BODY_COLOR

            paragraph.space_after = Pt(8)


slide_renderer = SlideRenderer()