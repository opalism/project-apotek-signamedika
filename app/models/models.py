from app import db
from datetime import datetime
from flask_login import UserMixin
from sqlalchemy.orm import synonym


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='admin')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    riwayat_proses = db.relationship('RiwayatProses', backref='user', lazy=True)

    # Synonym for backwards compatibility
    password = synonym('password_hash')

    def __init__(self, username: str = '', password: str = '', password_hash: str = '', role: str = 'admin', **kwargs):
        super().__init__(**kwargs)
        if username:
            self.username = username
        if password_hash or password:
            self.password_hash = password_hash or password
        if role:
            self.role = role


class Obat(db.Model):
    __tablename__ = 'obat'
    id = db.Column(db.Integer, primary_key=True)
    kode_obat = db.Column(db.String(50), nullable=True)
    nama_obat = db.Column(db.String(100), nullable=False)
    supplier = db.Column(db.String(100))
    kategori = db.Column(db.String(50))
    satuan = db.Column(db.String(20))
    total_penjualan = db.Column(db.Integer)
    harga_beli = db.Column(db.Numeric(12, 2))
    harga_jual = db.Column(db.Numeric(12, 2))
    stok_fisik = db.Column(db.Integer)
    lead_time_hari = db.Column(db.Integer)
    biaya_pesan = db.Column(db.Numeric(12, 2))
    biaya_simpan_persen = db.Column(db.Numeric(5, 2))

    # Relationships (1:1 with HasilCluster and HasilEOQ per ERD)
    hasil_cluster = db.relationship('HasilCluster', backref='obat', uselist=False, cascade='all, delete-orphan')
    hasil_eoq = db.relationship('HasilEOQ', backref='obat', uselist=False, cascade='all, delete-orphan')

    # Synonyms for backwards compatibility
    jumlah_terjual_per_bulan = synonym('total_penjualan')
    stok_rata_rata = synonym('stok_fisik')

    @property
    def clusters(self):
        return [self.hasil_cluster] if self.hasil_cluster else []

    @property
    def eoqs(self):
        return [self.hasil_eoq] if self.hasil_eoq else []

    def __init__(self, nama_obat: str = '', supplier: str = '', kategori: str = '',
                 satuan: str = '', jumlah_terjual_per_bulan: int = None, total_penjualan: int = None,
                 harga_beli: float = 0, harga_jual: float = 0,
                 stok_rata_rata: int = None, stok_fisik: int = None, lead_time_hari: int = 0,
                 biaya_pesan: float = 0, biaya_simpan_persen: float = 0, kode_obat: str = None, **kwargs):
        super().__init__(**kwargs)
        if kode_obat is not None:
            self.kode_obat = kode_obat
        self.nama_obat = nama_obat
        self.supplier = supplier
        self.kategori = kategori
        self.satuan = satuan
        tot_penj = total_penjualan if total_penjualan is not None else (jumlah_terjual_per_bulan or 0)
        self.total_penjualan = tot_penj
        self.harga_beli = harga_beli
        self.harga_jual = harga_jual
        stok = stok_fisik if stok_fisik is not None else (stok_rata_rata or 0)
        self.stok_fisik = stok
        self.lead_time_hari = lead_time_hari
        self.biaya_pesan = biaya_pesan
        self.biaya_simpan_persen = biaya_simpan_persen


class HasilCluster(db.Model):
    __tablename__ = 'hasil_cluster'
    id = db.Column(db.Integer, primary_key=True)
    obat_id = db.Column(db.Integer, db.ForeignKey('obat.id'), nullable=False)
    cluster_label = db.Column(db.String(30))
    norm_harga = db.Column(db.Numeric(10, 4))
    norm_penjualan = db.Column(db.Numeric(10, 4))
    dist_c1_c2_c3 = db.Column(db.Text)
    cluster_raw = db.Column(db.Integer)
    tanggal_proses = db.Column(db.DateTime, default=datetime.utcnow)


class HasilEOQ(db.Model):
    __tablename__ = 'hasil_eoq'
    id = db.Column(db.Integer, primary_key=True)
    obat_id = db.Column(db.Integer, db.ForeignKey('obat.id'), nullable=False)
    kebutuhan_mingguan = db.Column(db.Numeric(10, 2))
    biaya_simpan = db.Column(db.Numeric(12, 2))
    eoq_mingguan = db.Column(db.Numeric(12, 2))
    reorder_point = db.Column(db.Numeric(12, 2))
    status_stok = db.Column(db.String(50))
    frekuensi_pesan_per_bulan = db.Column(db.Numeric(10, 2))
    tanggal_hitung = db.Column(db.DateTime, default=datetime.utcnow)

    # Synonym for backwards compatibility
    eoq = synonym('eoq_mingguan')


class RiwayatProses(db.Model):
    __tablename__ = 'riwayat_proses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    num_clusters_k = db.Column(db.Integer)
    dbi_score = db.Column(db.Numeric(10, 4))
    silhouette_score = db.Column(db.Numeric(10, 4))
    executed_at = db.Column(db.DateTime, default=datetime.utcnow)
    jumlah_data = db.Column(db.Integer)
    keterangan = db.Column(db.Text)

    # Synonyms for backwards compatibility
    jumlah_cluster = synonym('num_clusters_k')
    tanggal_proses = synonym('executed_at')