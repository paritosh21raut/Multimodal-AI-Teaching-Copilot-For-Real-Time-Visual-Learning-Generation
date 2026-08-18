from __future__ import annotations

from pptx.enum.text import PP_ALIGN
from pptx.util import Pt, Inches
from pptx.dml.color import RGBColor


class SlideRenderer:
    """
    Responsible only for formatting slides.
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
        image_path=None,
    ):
        # =====================================================
        # TITLE
        # =====================================================

        title_shape = slide.shapes.title

        title_shape.left = Inches(0.6)
        title_shape.top = Inches(0.25)
        title_shape.width = Inches(8.8)
        title_shape.height = Inches(0.7)

        title_shape.text = title

        title_para = title_shape.text_frame.paragraphs[0]
        title_para.font.size = Pt(self.TITLE_FONT_SIZE)
        title_para.font.bold = True
        title_para.font.color.rgb = self.TITLE_COLOR

        # =====================================================
        # BODY PLACEHOLDER
        # =====================================================

        body_shape = None

        for shape in slide.placeholders:
            if shape == title_shape:
                continue

            if hasattr(shape, "text_frame"):
                body_shape = shape
                break

        if body_shape is None:
            raise RuntimeError("No body placeholder found")

        # LEFT SIDE = BULLETS
        body_shape.left = Inches(0.7)
        body_shape.top = Inches(1.35)
        body_shape.width = Inches(5.0)
        body_shape.height = Inches(5.4)

        body = body_shape.text_frame
        body.clear()

        # =====================================================
        # BULLETS
        # =====================================================

        for i, bullet in enumerate(bullets):

            if i == 0:
                paragraph = body.paragraphs[0]
            else:
                paragraph = body.add_paragraph()

            paragraph.text = bullet
            paragraph.level = 0

            paragraph.font.size = Pt(self.BODY_FONT_SIZE)
            paragraph.font.color.rgb = self.BODY_COLOR

            paragraph.space_after = Pt(10)

        print("[PPT] Added", len(bullets), "bullets")

        # =====================================================
        # IMAGE
        # =====================================================

        if image_path:

            try:
                slide.shapes.add_picture(
                    image_path,
                    left=Inches(6.0),
                    top=Inches(1.35),
                    width=Inches(3.3),
                    height=Inches(5.0),
                )

                print("[PPT] Image inserted")

            except Exception as error:
                print(
                    "[PPT] Image insertion failed:",
                    error,
                )


slide_renderer = SlideRenderer()