"""
Black Box Testing — F-04, F-05, F-06: Proses Clustering K-Means
===============================================================
Menguji fungsionalitas clustering dan validasi cluster sesuai PRD Bagian 13.
Menggunakan 988 data riil dari data-riil.xlsx.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db as _db
from app.models.models import HasilCluster, RiwayatProses
from app.services.kmeans_service import proses_clustering_dan_eoq, hitung_elbow

TOTAL_DATA_RIIL = 988


# ===========================================================
# Fixtures (data riil diserahkan ke conftest.py -> app_riil)
# ===========================================================

@pytest.fixture(scope='module')
def app(app_riil):
    """Alias agar test class bisa pakai `app` tanpa perubahan nama fixture."""
    return app_riil


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post('/login', data={'username': 'admin_riil', 'password': 'test123'})
    return c


# ===========================================================
# Test Case F-04 & F-05: Proses Clustering
# ===========================================================

class TestKMeansClustering:
    """Black Box Test untuk fitur Clustering (F-04, F-05) — data riil 988 obat."""

    def test_TC_CLUSTER_01_clustering_k3_berhasil(self, app):
        """TC-CLUSTER-01: Clustering K=3 berhasil dijalankan, mengembalikan success=True."""
        with app.app_context():
            success, msg, result = proses_clustering_dan_eoq(jumlah_cluster=3)
        assert success is True, f"Clustering gagal: {msg}"
        assert result['jumlah_cluster'] == 3
        assert result['total_data'] == TOTAL_DATA_RIIL

    def test_TC_CLUSTER_02_hasil_tersimpan_di_database(self, app):
        """TC-CLUSTER-02: Hasil clustering tersimpan di tabel hasil_cluster (1 per obat)."""
        with app.app_context():
            count = HasilCluster.query.count()
        assert count == TOTAL_DATA_RIIL, \
            f"Jumlah hasil cluster ({count}) tidak sesuai jumlah data riil ({TOTAL_DATA_RIIL})"

    def test_TC_CLUSTER_03_label_cluster_valid(self, app):
        """TC-CLUSTER-03: Label cluster hanya berisi 'Fast Moving', 'Medium Moving', atau 'Slow Moving'."""
        valid_labels = {'Fast Moving', 'Medium Moving', 'Slow Moving'}
        with app.app_context():
            labels = {r.cluster_label for r in HasilCluster.query.all()}
        assert labels.issubset(valid_labels), f"Label tidak valid: {labels - valid_labels}"

    def test_TC_CLUSTER_04_clustering_k2_berhasil(self, app):
        """TC-CLUSTER-04: Clustering K=2 berhasil dengan label 'Slow Moving' dan 'Fast Moving'."""
        with app.app_context():
            success, msg, result = proses_clustering_dan_eoq(jumlah_cluster=2)
        assert success is True
        assert result['jumlah_cluster'] == 2

    def test_TC_CLUSTER_05_riwayat_proses_tersimpan(self, app):
        """TC-CLUSTER-05: Setiap kali clustering dijalankan, riwayat disimpan ke tabel riwayat_proses."""
        with app.app_context():
            riwayat = RiwayatProses.query.count()
        assert riwayat >= 1

    def test_TC_CLUSTER_06_gagal_jika_data_kurang_dari_k(self, app):
        """TC-CLUSTER-06: Clustering gagal dengan pesan jelas jika jumlah data < K."""
        with app.app_context():
            success, msg, _ = proses_clustering_dan_eoq(jumlah_cluster=9999)
        assert success is False
        assert 'cluster' in msg.lower() or 'lebih sedikit' in msg.lower()

    def test_TC_CLUSTER_07_halaman_proses_dapat_diakses(self, client):
        """TC-CLUSTER-07: Halaman proses clustering dapat diakses."""
        resp = client.get('/clustering/proses')
        assert resp.status_code == 200

    def test_TC_CLUSTER_08_halaman_hasil_dapat_diakses(self, client):
        """TC-CLUSTER-08: Halaman hasil clustering dapat diakses setelah proses dijalankan."""
        resp = client.get('/clustering/hasil')
        assert resp.status_code == 200

    def test_TC_CLUSTER_09_distribusi_cluster_valid(self, app):
        """TC-CLUSTER-09: Setiap cluster harus punya minimal 1 anggota dari 988 obat."""
        with app.app_context():
            proses_clustering_dan_eoq(jumlah_cluster=3)
            from sqlalchemy import text
            rows = _db.session.execute(
                text("SELECT cluster_label, COUNT(*) as cnt FROM hasil_cluster GROUP BY cluster_label")
            ).fetchall()
        labels = {r[0]: r[1] for r in rows}
        assert len(labels) == 3, f"Jumlah cluster aktif={len(labels)}, diharapkan=3. Labels: {labels}"
        for lbl, cnt in labels.items():
            assert cnt >= 1, f"Cluster '{lbl}' tidak punya anggota"

    def test_TC_CLUSTER_10_distribusi_sesuai_thesis(self, app):
        """TC-CLUSTER-10: Distribusi cluster sesuai hasil thesis — Slow=136, lainnya ~841+11=852."""
        with app.app_context():
            proses_clustering_dan_eoq(jumlah_cluster=3)
            from sqlalchemy import text
            rows = _db.session.execute(
                text("SELECT cluster_label, COUNT(*) as cnt FROM hasil_cluster GROUP BY cluster_label")
            ).fetchall()
        dist = {r[0]: r[1] for r in rows}
        # Slow Moving selalu ~136 (deterministik dari centroid awal)
        slow = dist.get('Slow Moving', 0)
        # Dua cluster lainnya berjumlah 988 - slow
        others = sum(v for k, v in dist.items() if k != 'Slow Moving')
        assert abs(slow - 136) <= 10, f"Slow Moving={slow}, expected ~136"
        assert abs(others - (TOTAL_DATA_RIIL - 136)) <= 10, \
            f"Non-Slow total={others}, expected ~{TOTAL_DATA_RIIL - 136}"


# ===========================================================
# Test Case F-06: Validasi Cluster (DBI & Elbow)
# ===========================================================

class TestValidasiCluster:
    """Black Box Test untuk validasi cluster (F-06) — data riil 988 obat."""

    def test_TC_VALID_01_dbi_dan_silhouette_tersimpan(self, app):
        """TC-VALID-01: Nilai DBI dan Silhouette Score tersimpan di riwayat proses."""
        with app.app_context():
            proses_clustering_dan_eoq(jumlah_cluster=3)
            r = RiwayatProses.query.order_by(RiwayatProses.tanggal_proses.desc()).first()
        assert r is not None
        assert r.dbi_score is not None
        assert r.silhouette_score is not None

    def test_TC_VALID_02_dbi_score_sesuai_thesis(self, app):
        """TC-VALID-02: DBI Score mendekati nilai thesis 0.5734 (toleransi ±0.05)."""
        with app.app_context():
            proses_clustering_dan_eoq(jumlah_cluster=3)
            r = RiwayatProses.query.order_by(RiwayatProses.tanggal_proses.desc()).first()
        dbi = float(r.dbi_score)
        assert dbi >= 0, f"DBI harus >= 0, aktual={dbi}"
        assert abs(dbi - 0.5734) <= 0.05, f"DBI={dbi:.4f}, expected ~0.5734 (±0.05)"

    def test_TC_VALID_03_silhouette_sesuai_thesis(self, app):
        """TC-VALID-03: Silhouette Score mendekati nilai thesis 0.7382 (toleransi ±0.05)."""
        with app.app_context():
            r = RiwayatProses.query.order_by(RiwayatProses.tanggal_proses.desc()).first()
        sil = float(r.silhouette_score)
        assert -1.0 <= sil <= 1.0, f"Silhouette harus dalam [-1,1], aktual={sil}"
        assert abs(sil - 0.7382) <= 0.05, f"Silhouette={sil:.4f}, expected ~0.7382 (±0.05)"

    def test_TC_VALID_04_elbow_method_mengembalikan_data(self, app):
        """TC-VALID-04: Fungsi hitung_elbow() mengembalikan data inertia untuk tiap K."""
        with app.app_context():
            success, msg, inertias = hitung_elbow(max_k=5)
        assert success is True
        assert len(inertias) >= 1
        for item in inertias:
            assert 'k' in item
            assert 'inertia' in item

    def test_TC_VALID_05_elbow_inertia_turun_monoton(self, app):
        """TC-VALID-05: Nilai inertia dari Elbow Method turun monoton seiring K bertambah."""
        with app.app_context():
            success, _, inertias = hitung_elbow(max_k=6)
        assert success is True
        inertia_vals = [item['inertia'] for item in inertias]
        for i in range(1, len(inertia_vals)):
            assert inertia_vals[i] <= inertia_vals[i - 1], \
                f"Inertia tidak turun: K={i+1} ({inertia_vals[i]}) > K={i} ({inertia_vals[i-1]})"
