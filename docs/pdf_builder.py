"""Small fpdf2-based helper for the five phase learning PDFs. Not part of the
shipped CLI -- a content-generation utility for docs/learning/*.pdf.
"""
from __future__ import annotations

from fpdf import FPDF
from fpdf.enums import XPos, YPos

INK = (17, 17, 17)
MUTED = (82, 81, 78)
BLUE = (42, 120, 214)
CALLOUT_BG = (238, 244, 251)
CALLOUT_BORDER = (42, 120, 214)
CODE_BG = (245, 245, 243)
TABLE_HEADER_BG = (42, 120, 214)

_DEJAVU_DIR = "/usr/share/fonts/truetype/dejavu"


class LearningPDF(FPDF):
    def __init__(self, phase_num: int, phase_title: str):
        super().__init__(format="Letter")
        # fpdf2's built-in core fonts (Helvetica, Courier) are Latin-1 only and
        # choke on em dashes and the Δ/± used in check names -- DejaVu Sans is
        # a real Unicode font, so register it instead of scrubbing every
        # non-ASCII character out of the content.
        self.add_font("DejaVu", "", f"{_DEJAVU_DIR}/DejaVuSans.ttf")
        self.add_font("DejaVu", "B", f"{_DEJAVU_DIR}/DejaVuSans-Bold.ttf")
        self.add_font("DejaVu", "I", f"{_DEJAVU_DIR}/DejaVuSans-Oblique.ttf")
        self.add_font("DejaVuMono", "", f"{_DEJAVU_DIR}/DejaVuSansMono.ttf")
        self.phase_num = phase_num
        self.phase_title = phase_title
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(20, 18, 20)
        self.add_page()

    def header(self):
        self.set_font("DejaVu", "B", 9)
        self.set_text_color(*MUTED)
        self.cell(0, 6, f"STATEMENT ANALYZER — PHASE {self.phase_num}", align="L")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def title_block(self, subtitle: str):
        self.set_font("DejaVu", "B", 22)
        self.set_text_color(*INK)
        self.multi_cell(0, 10, f"Phase {self.phase_num}: {self.phase_title}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("DejaVu", "", 12.5)
        self.set_text_color(*MUTED)
        self.multi_cell(0, 7, subtitle, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(3)
        self.set_draw_color(*BLUE)
        self.set_line_width(0.8)
        y = self.get_y()
        self.line(20, y, 191, y)
        self.ln(6)

    def h2(self, text: str):
        self.ln(2)
        self.set_font("DejaVu", "B", 14)
        self.set_text_color(*INK)
        self.multi_cell(0, 8, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def p(self, text: str):
        self.set_font("DejaVu", "", 10.5)
        self.set_text_color(*INK)
        self.multi_cell(0, 5.6, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)

    def bullets(self, items: list[str]):
        self.set_font("DejaVu", "", 10.5)
        self.set_text_color(*INK)
        left_margin = self.l_margin
        for item in items:
            self.set_x(left_margin + 4)
            self.multi_cell(171 - 4, 5.6, f"•  {item}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.ln(0.5)
        self.ln(1.5)

    def callout(self, label: str, text: str):
        self.ln(1)
        start_y = self.get_y()
        self.set_fill_color(*CALLOUT_BG)
        self.set_draw_color(*CALLOUT_BORDER)
        left = self.get_x()
        text_x = left + 5
        self.set_xy(text_x, start_y + 3)
        self.set_font("DejaVu", "B", 9.5)
        self.set_text_color(*BLUE)
        self.multi_cell(171 - 5, 5, label.upper(), new_x=XPos.LEFT, new_y=YPos.NEXT)
        self.set_font("DejaVu", "", 10.5)
        self.set_text_color(*INK)
        self.set_x(text_x)
        self.multi_cell(171 - 5, 5.6, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        end_y = self.get_y()
        self.rect(left, start_y, 171, end_y - start_y + 3, style="D")
        self.set_fill_color(*CALLOUT_BORDER)
        self.rect(left, start_y, 1.2, end_y - start_y + 3, style="F")
        self.set_y(end_y + 6)

    def code(self, lines: list[str]):
        self.set_font("DejaVuMono", "", 9.5)
        self.set_fill_color(*CODE_BG)
        start_y = self.get_y()
        for line in lines:
            self.set_x(20)
            self.cell(171, 5.5, line, fill=True)
            self.ln(5.5)
        self.ln(2)

    def table(self, headers: list[str], rows: list[list[str]], col_widths: list[float] | None = None):
        n = len(headers)
        widths = col_widths or [171 / n] * n
        self.set_font("DejaVu", "B", 9.5)
        self.set_fill_color(*TABLE_HEADER_BG)
        self.set_text_color(255, 255, 255)
        for w, h in zip(widths, headers):
            self.cell(w, 7, h, fill=True, border=0, align="L")
        self.ln(7)
        self.set_font("DejaVu", "", 9.5)
        self.set_text_color(*INK)
        for i, row in enumerate(rows):
            fill = i % 2 == 1
            self.set_fill_color(248, 248, 247)
            for w, cell in zip(widths, row):
                self.cell(w, 6.5, str(cell), fill=fill, border=0, align="L")
            self.ln(6.5)
        self.ln(3)

    def chart(self, path: str, caption: str):
        self.ln(1)
        w = 150
        x = (210 - w) / 2
        self.image(path, x=x, w=w)
        self.set_font("DejaVu", "I", 9)
        self.set_text_color(*MUTED)
        self.set_x(20)
        self.multi_cell(171, 5, caption, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)
