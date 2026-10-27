"""
Black Box & Akurasi Testing — F-07: Perhitungan EOQ & Reorder Point
====================================================================
Menguji akurasi formula EOQ, ROP, dan Kebutuhan Mingguan sesuai PRD Bagian 11 & 13.
Menggunakan 988 data riil dari data-riil.xlsx.

Obat Referensi: Amoxicillin HJ 500mg Tabet
  D_bulan  = 147 unit/bulan
  S        = Rp 5.500 (biaya pesan)
  harga_beli = Rp 4.560
  biaya_simpan = 26% per tahun
  lead_time = 4 hari

Formula (PRD v1.4 — basis 52 minggu):
  D_minggu  = (D_bulan × 12) / 52 = (147×12)/52 = 33.9231
  H_tahun   = (26/100 × 4560)     = 1185.6  Rp/unit/tahun
  H_minggu  = H_tahun / 52        = 22.8    Rp/unit/minggu
  EOQ       = ceil(√((2 × D_minggu × S) / H_minggu))
            = ceil(√((2 × 33.9231 × 5500) / 22.8))
            = ceil(√(16342.8)) = ceil(127.84) = 128
  ROP       = ceil(D_minggu × (lead_time / 7))
            = ceil(33.9231 × (4/7)) = ceil(19.384) = 20
  Kebut     = ceil(D_minggu) = ceil(33.9231) = 34
  Frekuensi = ceil(D_bulan / EOQ) = ceil(147/128) = 2
"""
import pytest
import math
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db as _db
from app.models.models import Obat, HasilEOQ
from app.services.kmeans_service import proses_clustering_dan_eoq

# ===========================================================
# Konstanta referensi: Amoxicillin HJ 500mg Tabet (dari data-riil.xlsx)
# ===========================================================
REF_NAMA      = 'Amoxicillin HJ 500mg Tabet'
REF_D         = 147          # unit/bulan
REF_S         = 5500         # biaya pesan
REF_HB        = 4560.0       # harga beli
REF_BS        = 26           # biaya simpan % per tahun
REF_LT        = 4            # lead time hari

# Perhitungan manual yang diekspektasikan
_D_minggu     = (REF_D * 12) / 52.0
_H_tahun      = (REF_BS / 100) * REF_HB
_H_minggu     = _H_tahun / 52.0
EXPECTED_EOQ  = math.ceil(math.sqrt((2 * _D_minggu * REF_S) / _H_minggu))   # 128
EXPECTED_ROP  = math.ceil(_D_minggu * (REF_LT / 7.0))                         # 20
EXPECTED_KEBUT = math.ceil(_D_minggu)                                          # 34
EXPECTED_FREK = math.ceil(REF_D / EXPECTED_EOQ)                               # 2


# ===========================================================
# Fixtures
# ===========================================================

@pytest.fixture(scope='module')
def app(app_riil):
    """Gunakan fixture data riil dari conftest.py."""
    return app_riil


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post('/login', data={'username': 'admin_riil', 'password': 'test123'})
    return c


# ===========================================================
# Helper
# ===========================================================

def _get_eoq_ref(app):
    """Ambil data EOQ untuk obat referensi dari database."""
    with app.app_context():
        o = Obat.query.filter_by(nama_obat=REF_NAMA).first()
        assert o is not None, f"Obat '{REF_NAMA}' tidak ditemukan di DB"
        e = HasilEOQ.query.filter_by(obat_id=o.id).first()
        assert e is not None, f"HasilEOQ tidak ditemukan untuk obat '{REF_NAMA}'"
        return {
            'eoq':       float(e.eoq),
            'rop':       float(e.reorder_point),
            'kebutuhan': float(e.kebutuhan_mingguan),
            'frekuensi': float(e.frekuensi_pesan_per_bulan),
        }


# ===========================================================
# Test Case F-07: Akurasi Perhitungan EOQ
# ===========================================================

class TestAkurasiEOQ:
    """Uji Akurasi Perhitungan EOQ — spot check vs perhitungan manual Amoxicillin HJ 500mg."""

    def test_TC_EOQ_01_semua_obat_punya_data_eoq(self, app):
        """TC-EOQ-01: Setiap obat yang sudah dicluster memiliki data EOQ di database."""
        with app.app_context():
            jumlah_obat = Obat.query.count()
            jumlah_eoq  = HasilEOQ.query.count()
        assert jumlah_eoq == jumlah_obat, \
            f"Jumlah data EOQ ({jumlah_eoq}) tidak sama dengan jumlah obat ({jumlah_obat})"

    def test_TC_EOQ_02_nilai_eoq_positif(self, app):
        """TC-EOQ-02: Nilai EOQ harus positif untuk obat referensi."""
        data = _get_eoq_ref(app)
        assert data['eoq'] > 0, f"EOQ bernilai {data['eoq']}, seharusnya > 0"

    def test_TC_EOQ_03_akurasi_eoq_sesuai_formula_prd(self, app):
        """TC-EOQ-03: EOQ Amoxicillin HJ 500mg = 128 (toleransi ±1 unit)."""
        data = _get_eoq_ref(app)
        assert abs(data['eoq'] - EXPECTED_EOQ) <= 1, \
            f"EOQ aktual={data['eoq']}, expected={EXPECTED_EOQ}"

    def test_TC_EOQ_04_akurasi_rop_sesuai_formula_prd(self, app):
        """TC-EOQ-04: ROP Amoxicillin HJ 500mg = 20 (toleransi ±1 unit)."""
        data = _get_eoq_ref(app)
        assert abs(data['rop'] - EXPECTED_ROP) <= 1, \
            f"ROP aktual={data['rop']}, expected={EXPECTED_ROP}"

    def test_TC_EOQ_05_akurasi_kebutuhan_mingguan(self, app):
        """TC-EOQ-05: Kebutuhan Mingguan Amoxicillin HJ 500mg = 34."""
        data = _get_eoq_ref(app)
        assert data['kebutuhan'] == EXPECTED_KEBUT, \
            f"Kebutuhan aktual={data['kebutuhan']}, expected={EXPECTED_KEBUT}"

    def test_TC_EOQ_06_frekuensi_pesan_minimal_satu(self, app):
        """TC-EOQ-06: Frekuensi pesan per bulan harus minimal 1 untuk semua obat."""
        with app.app_context():
            semua_eoq = HasilEOQ.query.all()
        for e in semua_eoq:
            assert float(e.frekuensi_pesan_per_bulan) >= 1, \
                f"Frekuensi = {e.frekuensi_pesan_per_bulan} untuk obat_id={e.obat_id}"

    def test_TC_EOQ_07_eoq_nol_jika_biaya_simpan_nol(self, app):
        """TC-EOQ-07: Jika biaya_simpan_persen = 0, EOQ = 0 (tidak bisa dihitung)."""
        with app.app_context():
            o_temp = Obat(
                nama_obat='Obat_Tanpa_Simpan',
                total_penjualan=100,
                harga_jual=2000,
                harga_beli=1500,
                lead_time_hari=3,
                biaya_pesan=10000,
                biaya_simpan_persen=0,
                stok_fisik=50
            )
            _db.session.add(o_temp)
            _db.session.commit()
            proses_clustering_dan_eoq(jumlah_cluster=3)
            e = HasilEOQ.query.filter_by(obat_id=o_temp.id).first()
            eoq_val = float(e.eoq) if e else None
        assert eoq_val == 0.0, f"EOQ seharusnya 0, tapi bernilai {eoq_val}"

    def test_TC_EOQ_08_semua_rop_bernilai_non_negatif(self, app):
        """TC-EOQ-08: ROP semua obat harus >= 0."""
        with app.app_context():
            semua_eoq = HasilEOQ.query.all()
        for e in semua_eoq:
            assert float(e.reorder_point) >= 0, \
                f"ROP negatif ({e.reorder_point}) untuk obat_id={e.obat_id}"


# ===========================================================
# Test Case F-07: Tampilan Rekomendasi EOQ
# ===========================================================

class TestTampilanEOQ:
    """Black Box Test untuk halaman Rekomendasi EOQ (F-07)."""

    def test_TC_EOQ_09_halaman_rekomendasi_dapat_diakses(self, client):
        """TC-EOQ-09: Halaman Rekomendasi EOQ dapat diakses."""
        client.post('/login', data={'username': 'admin_riil', 'password': 'test123'})
        resp = client.get('/eoq/rekomendasi')
        assert resp.status_code == 200

    def test_TC_EOQ_10_data_eoq_tampil_di_halaman(self, client):
        """TC-EOQ-10: Data EOQ (kolom kebutuhan/ROP) muncul di halaman rekomendasi."""
        client.post('/login', data={'username': 'admin_riil', 'password': 'test123'})
        resp = client.get('/eoq/rekomendasi')
        assert resp.status_code == 200
        content = resp.data.lower()
        assert b'fast moving' in content or b'slow moving' in content or b'eoq' in content
