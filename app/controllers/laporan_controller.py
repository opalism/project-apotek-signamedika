from datetime import datetime
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, make_response)
from flask_login import login_required
from app import db
from app.models.models import Obat, HasilCluster, HasilEOQ, RiwayatProses
from app.services.pdf_service import generate_pdf

laporan_bp = Blueprint('laporan', __name__)


def _get_data():
    return (db.session.query(
        Obat.nama_obat, Obat.supplier, Obat.kategori, Obat.satuan,
        Obat.stok_rata_rata, Obat.jumlah_terjual_per_bulan,
        HasilCluster.cluster_label,
        HasilEOQ.eoq, HasilEOQ.reorder_point,
        HasilEOQ.kebutuhan_mingguan,
        HasilEOQ.frekuensi_pesan_per_bulan
    )
    .join(HasilCluster, Obat.id == HasilCluster.obat_id)
    .join(HasilEOQ, Obat.id == HasilEOQ.obat_id)
    .order_by(HasilCluster.cluster_label, Obat.nama_obat)
    .all())


@laporan_bp.route('/preview')
@login_required
def preview():
    hasil = _get_data()
    if not hasil:
        flash('Belum ada data laporan. Jalankan proses clustering terlebih dahulu.', 'warning')
        return redirect(url_for('clustering.proses'))

    riwayat = (RiwayatProses.query
               .order_by(RiwayatProses.tanggal_proses.desc()).first())
    tanggal = datetime.now().strftime('%d %B %Y')
    
    # Calculate summary stats for preview
    summary = {
        'total': len(hasil),
        'fast': sum(1 for r in hasil if 'Fast' in r.cluster_label),
        'medium': sum(1 for r in hasil if 'Medium' in r.cluster_label),
        'slow': sum(1 for r in hasil if 'Slow' in r.cluster_label),
        'kritis': sum(1 for r in hasil if (r.stok_rata_rata or 0) <= float(r.reorder_point or 0))
    }
    
    return render_template('laporan/preview.html',
                           hasil=hasil, riwayat=riwayat, tanggal=tanggal, summary=summary)


@laporan_bp.route('/download-pdf')
@login_required
def download_pdf():
    hasil = _get_data()
    riwayat = (RiwayatProses.query
               .order_by(RiwayatProses.tanggal_proses.desc()).first())
    tanggal = datetime.now().strftime('%d %B %Y')

    pdf_bytes, error = generate_pdf('laporan/pdf_template.html',
                                    hasil=hasil,
                                    riwayat=riwayat,
                                    tanggal=tanggal)
    if error:
        flash(f'Gagal membuat PDF: {error}', 'danger')
        return redirect(url_for('laporan.preview'))

    fname = f"laporan_apotek_{datetime.now().strftime('%Y%m%d')}.pdf"
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={fname}'
    return response
