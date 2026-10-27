from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app, abort)
from flask_login import login_required
from werkzeug.utils import secure_filename
from app import db
from app.models.models import Obat
from app.services.import_service import import_data_excel, import_opname_excel
from app.services.kmeans_service import proses_clustering_dan_eoq
import os
import pandas as pd
from io import BytesIO
from flask import send_file

obat_bp = Blueprint('obat', __name__)
ALLOWED_EXT = {'xlsx', 'xls', 'csv'}


def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


@obat_bp.route('/')
@login_required
def list():
    obat_list = Obat.query.order_by(Obat.nama_obat).all()
    return render_template('obat/list.html', obat_list=obat_list)


@obat_bp.route('/tambah', methods=['GET', 'POST'])
@login_required
def tambah():
    if request.method == 'POST':
        try:
            obat = Obat(
                nama_obat=request.form['nama_obat'].strip(),
                supplier=request.form.get('supplier', '').strip(),
                kategori=request.form.get('kategori', '').strip(),
                satuan=request.form.get('satuan', '').strip(),
                jumlah_terjual_per_bulan=int(request.form.get('jumlah_terjual_per_bulan') or 0),
                harga_beli=float(request.form.get('harga_beli') or 0),
                harga_jual=float(request.form.get('harga_jual') or 0),
                stok_rata_rata=int(request.form.get('stok_rata_rata') or 0),
                lead_time_hari=int(request.form.get('lead_time_hari') or 0),
                biaya_pesan=float(request.form.get('biaya_pesan') or 0),
                biaya_simpan_persen=float(request.form.get('biaya_simpan_persen') or 0),
            )
            db.session.add(obat)
            db.session.commit()
            flash('Data obat berhasil ditambahkan.', 'success')
            return redirect(url_for('obat.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Gagal menyimpan: {e}', 'danger')
    return render_template('obat/form.html', obat=None, action='tambah')


@obat_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    obat = db.session.get(Obat, id) or abort(404)
    if request.method == 'POST':
        try:
            obat.nama_obat = request.form['nama_obat'].strip()
            obat.supplier = request.form.get('supplier', '').strip()
            obat.kategori = request.form.get('kategori', '').strip()
            obat.satuan = request.form.get('satuan', '').strip()
            obat.jumlah_terjual_per_bulan = int(request.form.get('jumlah_terjual_per_bulan') or 0)
            obat.harga_beli = float(request.form.get('harga_beli') or 0)
            obat.harga_jual = float(request.form.get('harga_jual') or 0)
            obat.stok_rata_rata = int(request.form.get('stok_rata_rata') or 0)
            obat.lead_time_hari = int(request.form.get('lead_time_hari') or 0)
            obat.biaya_pesan = float(request.form.get('biaya_pesan') or 0)
            obat.biaya_simpan_persen = float(request.form.get('biaya_simpan_persen') or 0)
            db.session.commit()
            flash('Data obat berhasil diperbarui.', 'success')
            return redirect(url_for('obat.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Gagal memperbarui: {e}', 'danger')
    return render_template('obat/form.html', obat=obat, action='edit')


@obat_bp.route('/hapus/<int:id>', methods=['POST'])
@login_required
def hapus(id):
    obat = db.session.get(Obat, id) or abort(404)
    try:
        db.session.delete(obat)
        db.session.commit()
        flash(f'Obat "{obat.nama_obat}" berhasil dihapus.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Gagal menghapus: {e}', 'danger')
    return redirect(url_for('obat.list'))


@obat_bp.route('/import', methods=['GET', 'POST'])
@login_required
def import_excel():
    if request.method == 'POST':
        if 'file' not in request.files or request.files['file'].filename == '':
            flash('Pilih file terlebih dahulu.', 'danger')
            return redirect(request.url)

        file = request.files['file']
        if not _allowed(file.filename):
            flash('Format tidak valid. Gunakan .xlsx atau .csv.', 'danger')
            return redirect(request.url)

        folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, secure_filename(file.filename))
        file.save(path)

        success, message = import_data_excel(path)
        
        # Cek apakah user mencentang Auto-Cluster
        auto_cluster = request.form.get('auto_cluster')
        if success and auto_cluster == 'on':
            try:
                # Jalankan K-Means & EOQ otomatis dengan default K=3
                proses_clustering_dan_eoq(jumlah_cluster=3)
                message += " (Sistem juga telah berhasil melakukan Auto-Clustering K-Means K=3 & perhitungan ulang EOQ otomatis!)"
            except Exception as e:
                message += f" (Namun Auto-Clustering gagal dijalankan: {str(e)})"
                
        flash(message, 'success' if success else 'danger')
        if success:
            return redirect(url_for('obat.list'))

    return render_template('obat/import.html')


@obat_bp.route('/download-template')
@login_required
def download_template():
    from flask import send_from_directory
    root_dir = os.path.dirname(current_app.root_path)
    return send_from_directory(
        directory=root_dir,
        path='data-obat-contoh.xlsx',
        as_attachment=True,
    )

@obat_bp.route('/import-opname', methods=['GET', 'POST'])
@login_required
def import_opname():
    if request.method == 'POST':
        if 'file' not in request.files or request.files['file'].filename == '':
            flash('Pilih file terlebih dahulu.', 'danger')
            return redirect(request.url)

        file = request.files['file']
        if not _allowed(file.filename):
            flash('Format tidak valid. Gunakan .xlsx.', 'danger')
            return redirect(request.url)

        folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, secure_filename(file.filename))
        file.save(path)

        success, message = import_opname_excel(path)
        
        # Selalu Auto-Cluster jika stok opname
        if success:
            try:
                proses_clustering_dan_eoq(jumlah_cluster=3)
                message += " (Auto-Clustering K-Means dan sinkronisasi EOQ berhasil dijalankan!)"
            except Exception as e:
                message += f" (Gagal clustering: {str(e)})"
                
        flash(message, 'success' if success else 'danger')
        if success:
            return redirect(url_for('obat.list'))

    return render_template('obat/import_opname.html')


@obat_bp.route('/download-template-opname')
@login_required
def download_template_opname():
    # Buat template dinamis berisi seluruh nama obat dari database
    obats = Obat.query.order_by(Obat.nama_obat).all()
    
    data = []
    for o in obats:
        data.append({
            'Nama Obat': o.nama_obat,
            'Stok Tersisa Apotek': o.stok_rata_rata,
            'Terjual Bulan Ini': 0
        })
        
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Stok Opname')
        
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='Template_Opname_Apotek.xlsx'
    )