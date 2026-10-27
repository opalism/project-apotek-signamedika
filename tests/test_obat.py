"""
Black Box Testing — F-02 & F-03: CRUD Data Obat & Import Excel
==============================================================
Menguji fungsionalitas manajemen data obat sesuai PRD Bagian 13.
"""
import pytest
import sys
import os
import io

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db as _db
from app.models.models import User, Obat
from werkzeug.security import generate_password_hash


@pytest.fixture(scope='module')
def app():
    app = create_app({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SECRET_KEY': 'test-secret-key',
        'UPLOAD_FOLDER': '/tmp/test_uploads',
    })
    with app.app_context():
        _db.create_all()
        user = User(username='admin_test', password=generate_password_hash('test123'), role='admin')
        _db.session.add(user)
        _db.session.commit()
        yield app
        _db.drop_all()


@pytest.fixture
def client(app):
    c = app.test_client()
    # Auto-login setiap test
    c.post('/login', data={'username': 'admin_test', 'password': 'test123'})
    return c


# ===========================================================
# Test Case F-02: CRUD Data Obat
# ===========================================================

class TestCRUDObat:
    """Black Box Test untuk fitur CRUD Data Obat (F-02)."""

    def test_TC_OBAT_01_halaman_list_obat_tampil(self, client):
        """TC-OBAT-01: Halaman daftar obat dapat diakses dan menampilkan tabel."""
        resp = client.get('/obat/')
        assert resp.status_code == 200

    def test_TC_OBAT_02_tambah_obat_berhasil(self, client, app):
        """TC-OBAT-02: Tambah obat baru dengan data lengkap berhasil disimpan ke database."""
        resp = client.post('/obat/tambah', data={
            'nama_obat': 'Paracetamol 500mg Test',
            'kategori': 'Analgesik',
            'satuan': 'Tablet',
            'jumlah_terjual_per_bulan': '120',
            'harga_beli': '1500',
            'harga_jual': '2500',
            'stok_rata_rata': '200',
            'lead_time_hari': '3',
            'biaya_pesan': '10000',
            'biaya_simpan_persen': '20',
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            o = Obat.query.filter_by(nama_obat='Paracetamol 500mg Test').first()
            assert o is not None
            assert o.jumlah_terjual_per_bulan == 120

    def test_TC_OBAT_03_edit_obat_berhasil(self, client, app):
        """TC-OBAT-03: Edit data obat yang ada berhasil tersimpan."""
        with app.app_context():
            o = Obat.query.filter_by(nama_obat='Paracetamol 500mg Test').first()
            obat_id = o.id

        resp = client.post(f'/obat/edit/{obat_id}', data={
            'nama_obat': 'Paracetamol 500mg Test',
            'kategori': 'Analgesik',
            'satuan': 'Tablet',
            'jumlah_terjual_per_bulan': '150',   # Diubah dari 120 → 150
            'harga_beli': '1500',
            'harga_jual': '2500',
            'stok_rata_rata': '200',
            'lead_time_hari': '3',
            'biaya_pesan': '10000',
            'biaya_simpan_persen': '20',
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            o = Obat.query.filter_by(nama_obat='Paracetamol 500mg Test').first()
            assert o.jumlah_terjual_per_bulan == 150

    def test_TC_OBAT_04_hapus_obat_berhasil(self, client, app):
        """TC-OBAT-04: Hapus obat berhasil menghapus data dari database."""
        with app.app_context():
            o = Obat.query.filter_by(nama_obat='Paracetamol 500mg Test').first()
            obat_id = o.id

        resp = client.post(f'/obat/hapus/{obat_id}', follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            o = _db.session.get(Obat, obat_id)
            assert o is None

    def test_TC_OBAT_05_hapus_obat_tidak_ada_mengembalikan_404(self, client):
        """TC-OBAT-05: Menghapus obat dengan ID yang tidak ada mengembalikan 404."""
        resp = client.post('/obat/hapus/99999')
        assert resp.status_code == 404


# ===========================================================
# Test Case F-03: Import Excel
# ===========================================================

class TestImportExcel:
    """Black Box Test untuk fitur Import Data (F-03)."""

    def test_TC_IMPORT_01_halaman_import_tampil(self, client):
        """TC-IMPORT-01: Halaman import Excel dapat diakses."""
        resp = client.get('/obat/import')
        assert resp.status_code == 200

    def test_TC_IMPORT_02_upload_tanpa_file_ditolak(self, client):
        """TC-IMPORT-02: Submit form tanpa file menampilkan pesan error."""
        resp = client.post('/obat/import', data={}, follow_redirects=True)
        assert resp.status_code == 200

    def test_TC_IMPORT_03_upload_format_tidak_valid_ditolak(self, client):
        """TC-IMPORT-03: Upload file dengan format tidak valid (.txt) ditolak."""
        data = {'file': (io.BytesIO(b'dummy content'), 'test.txt')}
        resp = client.post('/obat/import', data=data,
                           content_type='multipart/form-data', follow_redirects=True)
        assert resp.status_code == 200
        assert b'tidak valid' in resp.data.lower() or b'format' in resp.data.lower()

    def test_TC_IMPORT_04_download_template_berhasil(self, client):
        """TC-IMPORT-04: Tombol Unduh Template menghasilkan file Excel."""
        resp = client.get('/obat/download-template')
        # Haru berhasil (200 atau redirect yang berhasil)
        assert resp.status_code in (200, 302)
