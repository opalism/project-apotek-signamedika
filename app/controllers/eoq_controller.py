from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models.models import Obat, HasilCluster, HasilEOQ

eoq_bp = Blueprint('eoq', __name__)


@eoq_bp.route('/rekomendasi')
@login_required
def rekomendasi():
    hasil = (db.session.query(
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

    if not hasil:
        flash('Belum ada data EOQ. Jalankan proses clustering terlebih dahulu.', 'warning')
        return redirect(url_for('clustering.proses'))

    return render_template('eoq/rekomendasi.html', hasil=hasil)
