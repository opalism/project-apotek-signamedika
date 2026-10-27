from io import BytesIO
from flask import render_template
from xhtml2pdf import pisa


def generate_pdf(template_name, **context):
    """Render template Jinja2 ke PDF dengan xhtml2pdf."""
    html = render_template(template_name, **context)
    buf = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode('UTF-8')), buf,
                            encoding='UTF-8')
    if pdf.err:
        return None, f"Gagal membuat PDF (error code: {pdf.err})"
    return buf.getvalue(), None
