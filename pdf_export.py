"""Create offline PDFs in memory using an embedded Unicode font."""
import unicodedata
from pathlib import Path

FONT_PATH = Path(__file__).resolve().parent / 'assets/fonts/DejaVuSans.ttf'


def translation_pdf(text, kind='translation'):
    from fpdf import FPDF
    from fontTools.ttLib import TTFont
    text = text.replace('\r\n', '\n').replace('\r', '\n').replace('\t', '    ')
    with TTFont(FONT_PATH) as font:
        supported = font.getBestCmap()
        if any(ord(char) not in supported for char in text if char != '\n'):
            raise ValueError('The PDF font does not support some characters in this translation. Use Save note (.txt) to preserve the full text.')
    pdf = FPDF()
    pdf.set_title('GLTS transcript' if kind == 'transcript' else 'GLTS translation')
    pdf.set_author('Global Language Translation Service')
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_font('GLTS', fname=str(FONT_PATH))
    pdf.set_font('GLTS', size=12)
    pdf.set_text_shaping(True)
    pdf.add_page()
    for paragraph in text.split('\n'):
        direction = next((unicodedata.bidirectional(char) for char in paragraph if unicodedata.bidirectional(char) in ('L', 'R', 'AL')), 'L')
        pdf.multi_cell(w=0, h=7, text=paragraph or ' ', align='R' if direction in ('R', 'AL') else 'L', new_x='LMARGIN', new_y='NEXT')
    return bytes(pdf.output())
