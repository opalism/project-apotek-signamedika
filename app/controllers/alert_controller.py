from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from app import db
from app.models.models import Obat, HasilEOQ, HasilCluster

alert_bp = Blueprint('alert', __name__)


# ---------------------------------------------------------------------------
# API: data stok kritis untuk notification bell (dipanggil via fetch/JS)
# ---------------------------------------------------------------------------
@alert_bp.route('/alert/notif-data')
@login_required
def notif_data():
    rows = _query_stok_kritis()
    items = [{
        'nama_obat': r.nama_obat,
        'satuan':    r.satuan or '',
        'stok':      r.stok_rata_rata or 0,
        'rop':       int(r.reorder_point),
        'cluster':   r.cluster_label,
    } for r in rows]
    return jsonify({'items': items, 'total': len(items)})


# ---------------------------------------------------------------------------
# Halaman Stok Kritis
# ---------------------------------------------------------------------------
@alert_bp.route('/alert/stok-kritis')
@login_required
def stok_kritis():
    rows = _query_stok_kritis()
    return render_template('alert/stok_kritis.html', rows=rows)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _query_stok_kritis():
    """Ambil semua obat dengan stok_rata_rata <= reorder_point."""
    return (
        db.session.query(
            Obat.nama_obat,
            Obat.satuan,
            Obat.stok_rata_rata,
            Obat.jumlah_terjual_per_bulan,
            HasilCluster.cluster_label,
            HasilEOQ.reorder_point,
            HasilEOQ.eoq,
            HasilEOQ.kebutuhan_mingguan,
        )
        .join(HasilEOQ,     Obat.id == HasilEOQ.obat_id)
        .join(HasilCluster, Obat.id == HasilCluster.obat_id)
        .filter(Obat.stok_rata_rata <= HasilEOQ.reorder_point)
        .order_by(HasilCluster.cluster_label, Obat.nama_obat)
        .all()
    )
