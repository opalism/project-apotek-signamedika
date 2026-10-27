import pandas as pd
from app import db
from app.models.models import Obat


def import_data_excel(file_path):
    try:
        # Membaca data menggunakan pandas (coba sheet 'Data Obat', jika tidak ada gunakan sheet pertama)
        try:
            df = pd.read_excel(file_path, sheet_name='Data Obat')
        except (ValueError, KeyError):
            df = pd.read_excel(file_path, sheet_name=0)

        # Pastikan kolom numerik tidak NaN — ganti dengan 0
        numeric_cols = {
            'Jumlah Terjual per Bulan': 0,
            'Harga Beli (Rp)': 0,
            'Harga Jual (Rp)': 0,
            'Stok Rata-rata': 0,
            'Lead Time (Hari)': 0,
            'Biaya Pesan (Rp)': 0,
            'Biaya Simpan (% per tahun)': 0,
        }
        df = df.fillna(numeric_cols)

        # Muat semua objek obat yang ada ke dalam memory (Dictionary) untuk fitur UPSERT instan O(1)
        # { 'nama_obat': ObjectObat }
        existing_obat = {o.nama_obat.lower(): o for o in Obat.query.all()}

        imported = 0
        obat_baru_list = []
        updated = 0

        # Iterasi setiap baris dan siapkan list objek
        for _, row in df.iterrows():
            nama = str(row.get('Nama Obat', '')).strip()
            if not nama or nama.lower() == 'nan':
                continue
            
            # Normalisasi persentase biaya simpan yg terbaca sbg desimal dari format persen Excel (0.11 -> 11)
            raw_biaya_simpan = float(row.get('Biaya Simpan (% per tahun)', 0) or 0)
            if 0 < raw_biaya_simpan <= 1.0:
                raw_biaya_simpan = raw_biaya_simpan * 100.0

            # Cek duplikat secara instan lewat Memory
            if nama.lower() in existing_obat:
                # FITUR UPSERT: Lakukan UPDATE data pada obat yang sudah ada
                obat_obj = existing_obat[nama.lower()]
                if obat_obj is not None:
                    obat_obj.supplier = str(row.get('Supplier', '') or '').strip()
                    obat_obj.kategori = str(row.get('Kategori', '') or '').strip()
                    obat_obj.satuan = str(row.get('Satuan', '') or '').strip()
                    obat_obj.jumlah_terjual_per_bulan = int(row.get('Jumlah Terjual per Bulan', 0) or 0)
                    obat_obj.harga_beli = float(row.get('Harga Beli (Rp)', 0) or 0)
                    obat_obj.harga_jual = float(row.get('Harga Jual (Rp)', 0) or 0)
                    obat_obj.stok_rata_rata = int(row.get('Stok Rata-rata', 0) or 0)
                    obat_obj.lead_time_hari = int(row.get('Lead Time (Hari)', 0) or 0)
                    obat_obj.biaya_pesan = float(row.get('Biaya Pesan (Rp)', 0) or 0)
                    obat_obj.biaya_simpan_persen = raw_biaya_simpan
                    updated += 1
                continue

            baru = Obat(
                nama_obat=nama,
                supplier=str(row.get('Supplier', '') or '').strip(),
                kategori=str(row.get('Kategori', '') or '').strip(),
                satuan=str(row.get('Satuan', '') or '').strip(),
                jumlah_terjual_per_bulan=int(row.get('Jumlah Terjual per Bulan', 0) or 0),
                harga_beli=float(row.get('Harga Beli (Rp)', 0) or 0),
                harga_jual=float(row.get('Harga Jual (Rp)', 0) or 0),
                stok_rata_rata=int(row.get('Stok Rata-rata', 0) or 0),
                lead_time_hari=int(row.get('Lead Time (Hari)', 0) or 0),
                biaya_pesan=float(row.get('Biaya Pesan (Rp)', 0) or 0),
                biaya_simpan_persen=raw_biaya_simpan,
            )
            existing_obat[nama.lower()] = baru
            obat_baru_list.append(baru)
            imported += 1

        # Bulk save: Injeksi data ke database sekaligus (ratusan kali lebih cepat dibanding .add() iteratif)
        if obat_baru_list:
            db.session.bulk_save_objects(obat_baru_list)

        # Simpan perubahan secara permanen ke MySQL (meng-insert obat baru dan menyimpan re-assign update memori ORM tadi)
        db.session.commit()
        return True, f"Berhasil menarik data: {imported} obat baru ditambahkan, dan {updated} obat diperbarui stok & penjualannya."

    except KeyError as e:
        db.session.rollback()
        return False, f"Kolom tidak ditemukan di file Excel: {e}"
    except Exception as e:
        # Batalkan seluruh transaksi jika terjadi kesalahan (Prinsip Atomicity)
        db.session.rollback()
        return False, f"Terjadi kesalahan: {str(e)}"

def import_opname_excel(file_path):
    try:
        df = pd.read_excel(file_path)
        
        updated = 0
        not_found = 0
        
        # Load dictionary existing drugs
        existing_obat = {o.nama_obat.lower(): o for o in Obat.query.all()}
        
        for _, row in df.iterrows():
            nama = str(row.get('Nama Obat', '')).strip()
            if not nama:
                continue
                
            if nama.lower() in existing_obat:
                obat_obj = existing_obat[nama.lower()]
                obat_obj.stok_rata_rata = int(row.get('Stok Tersisa Apotek', 0) or 0)
                obat_obj.jumlah_terjual_per_bulan = int(row.get('Terjual Bulan Ini', 0) or 0)
                updated += 1
            else:
                not_found += 1
                
        db.session.commit()
        msg = f"Berhasil sinkronisasi Stok Opname: {updated} obat diperbarui"
        if not_found > 0:
            msg += f" ({not_found} nama obat baru/tidak dikenal diabaikan)."
            
        return True, msg
        
    except KeyError as e:
        db.session.rollback()
        return False, f"Kolom Stok Opname tidak valid: {e}"
    except Exception as e:
        db.session.rollback()
        return False, f"Terjadi kesalahan saat Stok Opname: {str(e)}"