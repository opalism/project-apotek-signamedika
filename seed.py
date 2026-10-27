"""
seed.py — Reset database, import 988 data riil obat, dan jalankan clustering + EOQ.
Jalankan: python seed.py
"""
import os
import pandas as pd
from app import create_app, db
from app.models.models import User, Obat
from app.services.kmeans_service import proses_clustering_dan_eoq
from werkzeug.security import generate_password_hash

app = create_app()

DATA_RIIL_PATH = os.path.join(os.path.dirname(__file__), 'data-riil.xlsx')

with app.app_context():
    print("[1/4] Mengosongkan dan membuat ulang tabel database sesuai skema ERD...")
    db.drop_all()
    db.create_all()

    print("[2/4] Membuat user admin...")
    admin = User(
        username='admin',
        password=generate_password_hash('admin123'),
        role='admin'
    )
    db.session.add(admin)
    db.session.commit()
    print("      [OK] Username: admin | Password: admin123")

    print("[3/4] Mengimpor 988 data obat dari data-riil.xlsx...")
    if os.path.exists(DATA_RIIL_PATH):
        df = pd.read_excel(DATA_RIIL_PATH)
        count = 0
        for _, row in df.iterrows():
            o = Obat(
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
            )
            db.session.add(o)
            count += 1
        db.session.commit()
        print(f"      [OK] Berhasil mengimpor {count} data obat ke database MySQL.")

        print("[4/4] Menjalankan proses awal Clustering & EOQ (K=3)...")
        success, msg, result = proses_clustering_dan_eoq(jumlah_cluster=3, user_id=admin.id)
        if success:
            print("      [OK] Clustering K=3 dan perhitungan EOQ berhasil diselesaikan!")
        else:
            print(f"      [PERINGATAN] Gagal menjalankan clustering: {msg}")
    else:
        print(f"      [BISA DIABAIKAN] File {DATA_RIIL_PATH} tidak ditemukan.")

    print("\n[SUKSES] Database MySQL siap digunakan dengan data riil!")
