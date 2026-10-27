"""
conftest.py — Fixture terpusat untuk test suite
================================================
Menyediakan fixture `app_riil` yang menggunakan data-riil.xlsx (988 baris)
sebagai pengganti data dummy. Digunakan oleh test_clustering.py dan test_eoq.py.
"""
import os
import sys
import pytest
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db as _db
from app.models.models import User, Obat
from werkzeug.security import generate_password_hash

# Path ke file data riil
DATA_RIIL_PATH = os.path.join(os.path.dirname(__file__), '..', 'data-riil.xlsx')


def _load_data_riil():
    """Membaca data-riil.xlsx dan mengembalikan list dict siap pakai."""
    df = pd.read_excel(DATA_RIIL_PATH)
    obat_list = []
    for _, row in df.iterrows():
        obat_list.append(dict(
            nama_obat=str(row['Nama Obat']),
            supplier=str(row['Supplier']),
            kategori=str(row['Kategori']),
            satuan=str(row['Satuan']),
            total_penjualan=int(row['Jumlah Terjual per Bulan']),
            harga_beli=float(row['Harga Beli (Rp)']),
            harga_jual=float(row['Harga Jual (Rp)']),
            stok_fisik=int(row['Stok Rata-rata']),
            lead_time_hari=int(row['Lead Time (Hari)']),
            biaya_pesan=float(row['Biaya Pesan (Rp)']),
            biaya_simpan_persen=float(row['Biaya Simpan (% per tahun)']),
        ))
    return obat_list


@pytest.fixture(scope='session')
def app_riil():
    """
    Fixture session-scoped: satu instance SQLite in-memory yang sudah
    diisi dengan 988 baris data riil dan sudah menjalankan clustering K=3.
    """
    from app.services.kmeans_service import proses_clustering_dan_eoq

    if not os.path.exists(DATA_RIIL_PATH):
        pytest.skip(
            "data-riil.xlsx tidak ditemukan. File ini tidak disertakan di repositori "
            "karena berisi data asli apotek. Letakkan di root proyek untuk menjalankan "
            "test clustering dan EOQ."
        )

    app = create_app({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'UPLOAD_FOLDER': '/tmp/test_uploads',
    })

    with app.app_context():
        _db.create_all()

        # Buat user admin
        user = User(
            username='admin_riil',
            password=generate_password_hash('test123'),
            role='admin'
        )
        _db.session.add(user)

        # Seed 988 data riil
        obat_list = _load_data_riil()
        for d in obat_list:
            _db.session.add(Obat(**d))
        _db.session.commit()

        # Jalankan clustering + EOQ K=3
        success, msg, _ = proses_clustering_dan_eoq(jumlah_cluster=3)
        assert success, f"Proses clustering gagal pada fixture: {msg}"

        yield app
        _db.drop_all()
