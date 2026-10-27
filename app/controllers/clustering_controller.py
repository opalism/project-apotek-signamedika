import json
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.models import Obat, HasilCluster, HasilEOQ, RiwayatProses
from app.services.kmeans_service import proses_clustering_dan_eoq, hitung_elbow, dapatkan_detail_perhitungan_kmeans

clustering_bp = Blueprint('clustering', __name__)


@clustering_bp.route('/proses', methods=['GET', 'POST'])
@login_required
def proses():
    total_obat = Obat.query.count()
    riwayat = (RiwayatProses.query
               .order_by(RiwayatProses.tanggal_proses.desc())
               .limit(5).all())

    _, _, elbow_data = hitung_elbow()

    if request.method == 'POST':
        try:
            k = int(request.form.get('jumlah_cluster', 3))
        except ValueError:
            k = 3

        success, message, result = proses_clustering_dan_eoq(k, user_id=getattr(current_user, 'id', None))
        if success:
            flash(
                f'Clustering berhasil! DBI: {result["dbi"]} | '
                f'Silhouette: {result["silhouette"]}',
                'success'
            )
            return redirect(url_for('clustering.hasil'))
        flash(message, 'danger')

    return render_template('clustering/proses.html',
                           total_obat=total_obat,
                           riwayat=riwayat,
                           elbow_data=json.dumps(elbow_data))


@clustering_bp.route('/hasil')
@login_required
def hasil():
    hasil_list = (db.session.query(
        Obat.id, Obat.nama_obat, Obat.kategori,
        Obat.jumlah_terjual_per_bulan, Obat.harga_jual,
        HasilCluster.cluster_label,
        HasilEOQ.eoq, HasilEOQ.reorder_point
    )
    .join(HasilCluster, Obat.id == HasilCluster.obat_id)
    .outerjoin(HasilEOQ, Obat.id == HasilEOQ.obat_id)
    .order_by(HasilCluster.cluster_label, Obat.nama_obat)
    .all())

    if not hasil_list:
        flash('Belum ada hasil clustering. Jalankan proses terlebih dahulu.', 'warning')
        return redirect(url_for('clustering.proses'))

    COLORS = {
        'Fast Moving': '#16a34a',
        'Medium Moving': '#d97706',
        'Slow Moving':  '#dc2626',
    }
    scatter_data = [
        {
            'x': float(r.jumlah_terjual_per_bulan or 0),
            'y': float(r.harga_jual or 0),
            'label': r.nama_obat,
            'cluster': r.cluster_label,
            'color': COLORS.get(r.cluster_label, '#6b7280'),
        }
        for r in hasil_list
    ]

    summary = {}
    for r in hasil_list:
        summary[r.cluster_label] = summary.get(r.cluster_label, 0) + 1

    riwayat_terbaru = (RiwayatProses.query
                       .order_by(RiwayatProses.tanggal_proses.desc())
                       .first())

    k_cluster = riwayat_terbaru.jumlah_cluster if riwayat_terbaru else 3
    detail_perhitungan = dapatkan_detail_perhitungan_kmeans(k_cluster)

    return render_template('clustering/hasil.html',
                           hasil_list=hasil_list,
                           scatter_data=json.dumps(scatter_data),
                           summary=summary,
                           riwayat=riwayat_terbaru,
                           detail_perhitungan=detail_perhitungan)

