"""
Black Box Testing — F-01: Autentikasi (Login)
=============================================
Menguji fungsionalitas login admin sesuai PRD Bagian 13.
"""
import pytest
import sys
import os

# Pastikan root project bisa diimport
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db as _db
from app.models.models import User
from werkzeug.security import generate_password_hash


@pytest.fixture(scope='module')
def app():
    """Buat instance aplikasi Flask dalam mode testing."""
    app = create_app({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SECRET_KEY': 'test-secret-key',
    })
    with app.app_context():
        _db.create_all()
        # Seed user test
        if not User.query.filter_by(username='admin_test').first():
            user = User(
                username='admin_test',
                password=generate_password_hash('test123'),
                role='admin'
            )
            _db.session.add(user)
            _db.session.commit()
        yield app
        _db.drop_all()


@pytest.fixture
def client(app):
    with app.test_client() as client:
        client.get('/logout')
        yield client
        client.get('/logout')


# ===========================================================
# Test Case F-01: Login
# ===========================================================

class TestLogin:
    """Black Box Test untuk fitur Login (F-01)."""

    def test_TC_AUTH_01_halaman_login_tampil(self, client):
        """TC-AUTH-01: Halaman login dapat diakses dan menampilkan form."""
        resp = client.get('/login')
        assert resp.status_code == 200
        assert b'username' in resp.data.lower() or b'login' in resp.data.lower()

    def test_TC_AUTH_02_login_berhasil_dengan_kredensial_valid(self, client):
        """TC-AUTH-02: Login berhasil dengan username & password yang benar → redirect ke dashboard."""
        resp = client.post('/login', data={
            'username': 'admin_test',
            'password': 'test123'
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Setelah login, halaman dashboard seharusnya terbuka
        assert b'dashboard' in resp.data.lower() or b'obat' in resp.data.lower()

    def test_TC_AUTH_03_login_gagal_password_salah(self, client):
        """TC-AUTH-03: Login gagal dengan password yang salah → tetap di halaman login."""
        resp = client.post('/login', data={
            'username': 'admin_test',
            'password': 'passwordSalah'
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Harus ada pesan error atau tetap di halaman login
        assert b'login' in resp.data.lower() or b'salah' in resp.data.lower() or b'invalid' in resp.data.lower()

    def test_TC_AUTH_04_login_gagal_username_tidak_ada(self, client):
        """TC-AUTH-04: Login gagal dengan username yang tidak ada di database."""
        resp = client.post('/login', data={
            'username': 'user_tidak_ada',
            'password': 'test123'
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'login' in resp.data.lower()

    def test_TC_AUTH_05_akses_dashboard_tanpa_login_diblokir(self, client):
        """TC-AUTH-05: Akses halaman dashboard tanpa login harus diarahkan ke halaman login."""
        resp = client.get('/dashboard', follow_redirects=False)
        # Harus redirect ke login
        assert resp.status_code in (301, 302)

    def test_TC_AUTH_06_logout_berhasil(self, client):
        """TC-AUTH-06: Logout berhasil dan sesi dihapus."""
        # Login dulu
        client.post('/login', data={'username': 'admin_test', 'password': 'test123'})
        # Lalu logout
        resp = client.get('/logout', follow_redirects=True)
        assert resp.status_code == 200
        # Setelah logout, akses terproteksi harus diredirect
        resp2 = client.get('/dashboard', follow_redirects=False)
        assert resp2.status_code in (301, 302)
