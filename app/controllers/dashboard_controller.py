import json
from flask import Blueprint, render_template
from flask_login import login_required
from app import db
from app.models.models import Obat, HasilCluster, HasilEOQ

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
@login_required
def index():
    total_obat = Obat.query.count()
    sudah_clustering = HasilCluster.query.count() > 0

    # Hitung per cluster
    cluster_rows = (db.session.query(
        HasilCluster.cluster_label, db.func.count(HasilCluster.id)
    ).group_by(HasilCluster.cluster_label).all())
    cluster_dict = {label: cnt for label, cnt in cluster_rows}

    fast   = cluster_dict.get('Fast Moving', 0)
    medium = cluster_dict.get('Medium Moving', 0)
    slow   = cluster_dict.get('Slow Moving', 0)

    # Obat perlu restock (stok <= ROP)
    stok_kritis = (db.session.query(Obat)
                   .join(HasilEOQ, Obat.id == HasilEOQ.obat_id)
                   .filter(Obat.stok_rata_rata <= HasilEOQ.reorder_point)
                   .count()) if sudah_clustering else 0

    # Chart doughnut distribusi cluster
    chart_cluster = json.dumps({
        'labels': list(cluster_dict.keys()),
        'data': list(cluster_dict.values()),
    })

    # Chart bar top 10 terjual
    top_obat = (Obat.query
                .order_by(Obat.jumlah_terjual_per_bulan.desc())
                .limit(10).all())
    chart_top = json.dumps({
        'labels': [o.nama_obat for o in top_obat],
        'data': [o.jumlah_terjual_per_bulan or 0 for o in top_obat],
    })

    return render_template('dashboard/index.html',
                           total_obat=total_obat,
                           fast=fast, medium=medium, slow=slow,
                           stok_kritis=stok_kritis,
                           chart_cluster=chart_cluster,
                           chart_top=chart_top,
                           sudah_clustering=sudah_clustering)