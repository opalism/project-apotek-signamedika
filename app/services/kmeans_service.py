import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.cluster import KMeans
from sklearn.metrics import davies_bouldin_score
from app import db
from app.models.models import Obat, HasilCluster, HasilEOQ, RiwayatProses


def _build_dataframe():
    obat_list = Obat.query.all()
    data = []
    for o in obat_list:
        data.append({
            'id': o.id,
            'nama': o.nama_obat,
            'terjual': float(o.jumlah_terjual_per_bulan or 0),
            'harga_jual': float(o.harga_jual or 0),
            'harga_beli': float(o.harga_beli or 0),
            'lead_time': float(o.lead_time_hari or 0),
            'biaya_pesan': float(o.biaya_pesan or 0),
            'biaya_simpan': float(o.biaya_simpan_persen or 0),
        })
    return obat_list, pd.DataFrame(data)


def hitung_elbow(max_k=8):
    """Hitung inertia untuk grafik Elbow Method."""
    try:
        obat_list, df = _build_dataframe()
        if len(obat_list) < 3:
            return False, "Data terlalu sedikit (min. 3 obat).", []

        scaler = MinMaxScaler()
        X = scaler.fit_transform(df[['terjual', 'harga_jual']])

        max_k = min(max_k, len(obat_list) - 1)
        inertias = []
        for k in range(2, max_k + 1):
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            km.fit(X)
            inertias.append({'k': k, 'inertia': round(km.inertia_, 4)})

        return True, "OK", inertias
    except Exception as e:
        return False, str(e), []


def hitung_initial_centroids(df, scaler):
    """
    Menghitung centroid awal (initial seed centroids) C_k^(0) secara deterministik
    berdasarkan rata-rata atribut ter-normalisasi dari sampel representatif (Bab III).

    Formula: C_k^(0) = (1/N_k) * Σ x_i,  x_i ∈ S_k

    Keterangan:
      C_k^(0) : Centroid awal cluster ke-k pada iterasi t=0
      S_k     : Himpunan sampel representatif cluster ke-k
      N_k     : Jumlah sampel representatif
      x_i     : Vektor atribut ter-normalisasi [X1_terjual_norm, X2_harga_norm]

    Sampel Representatif (identik dengan perhitungan manual Bab III):
      S1 (Slow Moving)   : Madu Hitam Diabet, Madu Hitam Propolis 69, Sari Mengkudu Prima
      S2 (Fast Moving)   : Amoxicillin HJ 500mg Tabet, Metformin HJ 500mg Tab, Voltadex 50 mg Tab
      S3 (Medium Moving) : Acetylcystein 200 mg Sampharind Kap, Aciclovir Cr 5% First Medipharma,
                           Aciclovir Cr 5% Indofarma, Acifar 200 Mg Tab
    """

    # ── Nama sampel representatif sesuai Bab III ──────────────────────────────
    S1_NAMES = [
        'Madu Hitam Diabet',
        'Madu Hitam Propolis 69',
        'Sari Mengkudu Prima',
    ]
    S2_NAMES = [
        'Amoxicillin HJ 500mg Tabet',
        'Metformin HJ 500mg Tab',
        'Voltadex 50 mg Tab',
    ]
    S3_NAMES = [
        'Acetylcystein 200 mg Sampharind Kap',
        'Aciclovir Cr 5% First Medipharma',
        'Aciclovir Cr 5% Indofarma',
        'Acifar 200 Mg Tab',
    ]

    def _lookup_samples(names, fallback_fn, fallback_n, label):
        """Cari baris berdasarkan nama eksplisit; fallback jika nama tidak ditemukan."""
        rows = df[df['nama'].isin(names)]
        if len(rows) == len(names):
            # Pertahankan urutan sesuai daftar nama Bab III
            rows = rows.set_index('nama').reindex(names).reset_index()
            rows = rows.rename(columns={'index': 'nama'})
            return rows
        # Fallback: cetak peringatan dan gunakan filter numerik
        found = [n for n in names if n in df['nama'].values]
        missing = [n for n in names if n not in df['nama'].values]
        if missing:
            print(f"[PERINGATAN] Sampel {label} tidak ditemukan di DB: {missing}")
            print(f"[INFO] Menggunakan filter numerik sebagai fallback.")
        return fallback_fn(df).head(fallback_n)

    # Fallback functions (filter numerik)
    def _s1_fallback(d):
        res = d[(d['terjual'] <= 1) & (d['harga_jual'] >= 65000)].sort_values(
            by=['terjual', 'harga_jual'], ascending=[True, False])
        if len(res) == 0:
            res = d.sort_values(by=['terjual', 'harga_jual'], ascending=[True, False])
        return res

    def _s2_fallback(d):
        return d.sort_values('terjual', ascending=False)

    def _s3_fallback(d):
        res = d[(d['terjual'] <= 2) & (d['harga_jual'] >= 6500) & (d['harga_jual'] <= 15000)]
        if len(res) < 4:
            res = d[(d['terjual'] <= 10) & (d['harga_jual'] <= 20000)]
        if len(res) == 0:
            res = d
        return res

    # 1. Cari sampel S1, S2, S3
    s1_df = _lookup_samples(S1_NAMES, _s1_fallback, 3, 'S1 Slow Moving')
    s2_df = _lookup_samples(S2_NAMES, _s2_fallback, 3, 'S2 Fast Moving')
    s3_df = _lookup_samples(S3_NAMES, _s3_fallback, 4, 'S3 Medium Moving')

    # 2. Normalisasi sampel ke [X1, X2] dengan presisi penuh Float64
    s1_norm = scaler.transform(s1_df[['terjual', 'harga_jual']])
    s2_norm = scaler.transform(s2_df[['terjual', 'harga_jual']])
    s3_norm = scaler.transform(s3_df[['terjual', 'harga_jual']])

    # 3. Hitung C_k^(0) = mean koordinat ter-normalisasi sampel S_k
    c1_slow = s1_norm.mean(axis=0)   # C1^(0): Slow Moving
    c2_fast = s2_norm.mean(axis=0)   # C2^(0): Fast Moving
    c3_med  = s3_norm.mean(axis=0)   # C3^(0): Medium Moving

    # 4. Log centroid awal sebelum iterasi dimulai
    print("=" * 75)
    print("LOG INITIAL CENTROID K-MEANS — Berbasis Sampel Representatif Bab III")
    print()
    print("S1 — Sampel Slow Moving:")
    for _, r in s1_df.iterrows():
        x = scaler.transform([[r['terjual'], r['harga_jual']]])[0]
        print(f"   {r['nama']:45s} D={r['terjual']:5.0f}  H=Rp{r['harga_jual']:>9,.0f}"
              f"  => norm[{x[0]:.6f}, {x[1]:.6f}]")
    print(f"   C1 (Slow Moving)   : X1={c1_slow[0]:.6f}, X2={c1_slow[1]:.6f}")
    print()
    print("S2 — Sampel Fast Moving:")
    for _, r in s2_df.iterrows():
        x = scaler.transform([[r['terjual'], r['harga_jual']]])[0]
        print(f"   {r['nama']:45s} D={r['terjual']:5.0f}  H=Rp{r['harga_jual']:>9,.0f}"
              f"  => norm[{x[0]:.6f}, {x[1]:.6f}]")
    print(f"   C2 (Fast Moving)   : X1={c2_fast[0]:.6f}, X2={c2_fast[1]:.6f}")
    print()
    print("S3 — Sampel Medium Moving:")
    for _, r in s3_df.iterrows():
        x = scaler.transform([[r['terjual'], r['harga_jual']]])[0]
        print(f"   {r['nama']:45s} D={r['terjual']:5.0f}  H=Rp{r['harga_jual']:>9,.0f}"
              f"  => norm[{x[0]:.6f}, {x[1]:.6f}]")
    print(f"   C3 (Medium Moving) : X1={c3_med[0]:.6f}, X2={c3_med[1]:.6f}")
    print("=" * 75)

    # 5. Susun matriks centroid awal [C1_slow, C3_med, C2_fast] — urutan sesuai init KMeans
    init_centers = np.array([c1_slow, c3_med, c2_fast], dtype=np.float64)

    return init_centers, {
        's1_samples': s1_df[['nama', 'terjual', 'harga_jual']].to_dict('records'),
        's2_samples': s2_df[['nama', 'terjual', 'harga_jual']].to_dict('records'),
        's3_samples': s3_df[['nama', 'terjual', 'harga_jual']].to_dict('records'),
        'c1_slow': c1_slow,
        'c2_fast': c2_fast,
        'c3_med':  c3_med,
    }


def proses_clustering_dan_eoq(jumlah_cluster=3, user_id=None):
    """Jalankan K-Means + EOQ dan simpan hasilnya ke database."""
    try:
        obat_list, df = _build_dataframe()
        if df.empty:
            return False, "Tidak ada data obat di basis data.", {}
        if len(obat_list) < jumlah_cluster:
            return False, (
                f"Jumlah data ({len(obat_list)}) lebih sedikit dari "
                f"jumlah cluster ({jumlah_cluster})."
            ), {}

        # --- K-Means ---
        scaler = MinMaxScaler()
        X = scaler.fit_transform(df[['terjual', 'harga_jual']])

        if jumlah_cluster == 3:
            init_centers, init_info = hitung_initial_centroids(df, scaler)
            kmeans = KMeans(n_clusters=3, init=init_centers, n_init=1)
        else:
            kmeans = KMeans(n_clusters=jumlah_cluster, random_state=42, n_init=10)

        df['Cluster_Raw'] = kmeans.fit_predict(X)
        df['norm_penjualan'] = X[:, 0]
        df['norm_harga'] = X[:, 1]

        # Label berdasarkan rata-rata penjualan per klaster (ascending)
        cluster_means = df.groupby('Cluster_Raw')['terjual'].mean().sort_values()
        if jumlah_cluster == 2:
            labels = ['Slow Moving', 'Fast Moving']
        elif jumlah_cluster == 3:
            labels = ['Slow Moving', 'Medium Moving', 'Fast Moving']
        else:
            labels = [f'Cluster {i+1}' for i in range(jumlah_cluster)]

        label_map = {idx: labels[i] for i, idx in enumerate(cluster_means.index)}
        df['Kategori_Moving'] = df['Cluster_Raw'].map(label_map)

        # --- Skor Validasi (Selaras 100% dengan sheet evaluasi klaster data-riil.xlsx) ---
        try:
            dbi = davies_bouldin_score(X, df['Cluster_Raw'])
        except Exception:
            dbi = 0.0

        try:
            dists = np.linalg.norm(X[:, np.newaxis, :] - kmeans.cluster_centers_[np.newaxis, :, :], axis=2)
            a_i = dists[np.arange(len(X)), df['Cluster_Raw'].values]
            dists_sorted = np.sort(dists, axis=1)
            b_i = dists_sorted[:, 1]
            denom = np.maximum(a_i, b_i)
            s_i = np.where(denom == 0, 0.0, (b_i - a_i) / denom)
            sil = float(np.mean(s_i))
        except Exception:
            sil = 0.0

        # Weekly EOQ berbasis 52 minggu
        df['D_minggu'] = (df['terjual'] * 12.0) / 52.0

        df['H_tahun'] = (
            (df['biaya_simpan'] / 100.0) * df['harga_beli']
        )

        df['H_minggu'] = df['H_tahun'] / 52.0

        df['EOQ'] = np.where(
            df['H_minggu'] > 0,
            np.sqrt(
                (2 * df['D_minggu'] * df['biaya_pesan'])
                / df['H_minggu']
            ),
            0
        )

        df['EOQ'] = np.ceil(df['EOQ']).astype(int)

        df['ROP'] = np.ceil(
            df['D_minggu'] * (df['lead_time'] / 7.0)
        ).astype(int)

        # Kebutuhan Mingguan = ceil(D_minggu)
        df['KebutuhanMinggu'] = np.ceil(df['D_minggu']).astype(int)

        # Frekuensi pesan per bulan = ceil(D_bulan / EOQ)
        df['Frekuensi'] = np.where(
            df['EOQ'] > 0,
            np.ceil(df['terjual'] / df['EOQ']),
            1  # minimum 1x pesan
        )

        # --- Simpan ke DB ---
        HasilCluster.query.delete()
        HasilEOQ.query.delete()

        import json
        cluster_list = []
        eoq_list = []
        obat_dict = {o.id: o for o in obat_list}
        for i, (_, row) in enumerate(df.iterrows()):
            dist_dict = {f"c{c+1}": round(float(dists[i, c]), 4) for c in range(kmeans.n_clusters)}
            obat_obj = obat_dict.get(int(row['id']))
            stok_val = float(obat_obj.stok_fisik or 0) if obat_obj else 0
            rop_val = float(row['ROP'])
            status = 'Stok Kritis (Harus Reorder)' if stok_val <= rop_val else 'Stok Aman'

            cluster_list.append(HasilCluster(
                obat_id=int(row['id']),
                cluster_label=row['Kategori_Moving'],
                cluster_raw=int(row['Cluster_Raw']),
                norm_harga=round(float(row['norm_harga']), 4),
                norm_penjualan=round(float(row['norm_penjualan']), 4),
                dist_c1_c2_c3=json.dumps(dist_dict)
            ))
            eoq_list.append(HasilEOQ(
                obat_id=int(row['id']),
                eoq_mingguan=float(row['EOQ']),
                reorder_point=rop_val,
                kebutuhan_mingguan=float(row['KebutuhanMinggu']),
                biaya_simpan=float(row['H_tahun']),
                status_stok=status,
                frekuensi_pesan_per_bulan=float(row['Frekuensi'])
            ))

        db.session.add_all(cluster_list)
        db.session.add_all(eoq_list)

        db.session.add(RiwayatProses(
            user_id=user_id,
            num_clusters_k=jumlah_cluster,
            jumlah_data=len(obat_list),
            dbi_score=round(dbi, 4),
            silhouette_score=round(sil, 4),
            keterangan=f"Berhasil dengan {jumlah_cluster} cluster"
        ))
        db.session.commit()

        return True, "K-Means & EOQ berhasil dieksekusi.", {
            'dbi': round(dbi, 4),
            'silhouette': round(sil, 4),
            'jumlah_cluster': jumlah_cluster,
            'total_data': len(obat_list)
        }

    except Exception as e:
        db.session.rollback()
        return False, f"Kesalahan: {str(e)}", {}


def dapatkan_detail_perhitungan_kmeans(jumlah_cluster=3):
    """
    Menghasilkan data komprehensif langkah demi langkah perhitungan K-Means Clustering
    untuk bahan verifikasi dan presentasi sidang akhir.
    """
    try:
        obat_list, df = _build_dataframe()
        if df.empty or len(obat_list) < jumlah_cluster:
            return None

        # Min-Max Normalization
        scaler = MinMaxScaler()
        X_norm = scaler.fit_transform(df[['terjual', 'harga_jual']])

        terjual_min = float(scaler.data_min_[0])
        terjual_max = float(scaler.data_max_[0])
        harga_min = float(scaler.data_min_[1])
        harga_max = float(scaler.data_max_[1])

        if jumlah_cluster == 3:
            init_centers, init_info = hitung_initial_centroids(df, scaler)
            kmeans = KMeans(n_clusters=3, init=init_centers, n_init=1)
        else:
            init_info = None
            kmeans = KMeans(n_clusters=jumlah_cluster, random_state=42, n_init=10)

        raw_labels = kmeans.fit_predict(X_norm)

        df['Cluster_Raw'] = raw_labels
        cluster_means = df.groupby('Cluster_Raw')['terjual'].mean().sort_values()

        if jumlah_cluster == 2:
            labels = ['Slow Moving', 'Fast Moving']
        elif jumlah_cluster == 3:
            labels = ['Slow Moving', 'Medium Moving', 'Fast Moving']
        else:
            labels = [f'Cluster {i+1}' for i in range(jumlah_cluster)]

        raw_to_label = {idx: labels[i] for i, idx in enumerate(cluster_means.index)}

        dbi = davies_bouldin_score(X_norm, raw_labels)
        dists_eval = np.linalg.norm(X_norm[:, np.newaxis, :] - kmeans.cluster_centers_[np.newaxis, :, :], axis=2)
        a_i = dists_eval[np.arange(len(X_norm)), raw_labels]
        dists_sorted = np.sort(dists_eval, axis=1)
        b_i = dists_sorted[:, 1]
        sil = float(np.mean((b_i - a_i) / np.maximum(a_i, b_i)))
        wcss = kmeans.inertia_

        # Tracing pergeseran centroid iterasi Lloyd aktual hingga konvergen
        centroids_curr = init_centers.copy() if jumlah_cluster == 3 else kmeans.cluster_centers_.copy()
        history = [{'iter': 0, 'centers': centroids_curr.copy()}]

        step = 1
        while step <= 50:
            dists = np.linalg.norm(X_norm[:, np.newaxis, :] - centroids_curr[np.newaxis, :, :], axis=2)
            step_labels = np.argmin(dists, axis=1)

            new_centers = np.zeros_like(centroids_curr)
            for k in range(jumlah_cluster):
                members = X_norm[step_labels == k]
                if len(members) > 0:
                    new_centers[k] = members.mean(axis=0)
                else:
                    new_centers[k] = centroids_curr[k]

            history.append({'iter': step, 'centers': new_centers.copy()})

            if np.allclose(centroids_curr, new_centers, atol=1e-6):
                break
            centroids_curr = new_centers
            step += 1

        centroid_history = []
        for h in history:
            c_data = []
            for c_idx in range(jumlah_cluster):
                mapped_label = raw_to_label[c_idx]
                x_norm = float(h['centers'][c_idx][0])
                y_norm = float(h['centers'][c_idx][1])
                x_orig = x_norm * (terjual_max - terjual_min) + terjual_min
                y_orig = y_norm * (harga_max - harga_min) + harga_min
                c_data.append({
                    'raw_id': c_idx,
                    'label': mapped_label,
                    'x_norm': round(x_norm, 4),
                    'y_norm': round(y_norm, 4),
                    'x_orig': round(x_orig, 2),
                    'y_orig': round(y_orig, 2),
                })
            centroid_history.append({'iter': h['iter'], 'centroids': c_data})

        final_centroids = []
        for c_idx in range(jumlah_cluster):
            mapped_label = raw_to_label[c_idx]
            x_norm = float(kmeans.cluster_centers_[c_idx][0])
            y_norm = float(kmeans.cluster_centers_[c_idx][1])
            x_orig = x_norm * (terjual_max - terjual_min) + terjual_min
            y_orig = y_norm * (harga_max - harga_min) + harga_min
            final_centroids.append({
                'raw_id': c_idx,
                'label': mapped_label,
                'x_norm': round(x_norm, 4),
                'y_norm': round(y_norm, 4),
                'x_orig': round(x_orig, 2),
                'y_orig': round(y_orig, 2)
            })

        matriks_jarak = []
        for i, row in df.iterrows():
            x_i = X_norm[i]
            distances = {}
            for c_idx in range(jumlah_cluster):
                mapped_label = raw_to_label[c_idx]
                c_center = kmeans.cluster_centers_[c_idx]
                dist = float(np.linalg.norm(x_i - c_center))
                distances[mapped_label] = round(dist, 4)

            assigned_label = raw_to_label[raw_labels[i]]
            min_dist = min(distances.values())

            matriks_jarak.append({
                'id': int(row['id']),
                'nama': row['nama'],
                'terjual_orig': float(row['terjual']),
                'harga_orig': float(row['harga_jual']),
                'x_norm': round(float(x_i[0]), 4),
                'y_norm': round(float(x_i[1]), 4),
                'distances': distances,
                'min_dist': min_dist,
                'assigned_label': assigned_label
            })

        return {
            'terjual_min': terjual_min,
            'terjual_max': terjual_max,
            'harga_min': harga_min,
            'harga_max': harga_max,
            'n_iter': len(history) - 1,
            'wcss': round(wcss, 4),
            'dbi': round(dbi, 4),
            'silhouette': round(sil, 4),
            'init_info': init_info,
            'centroid_history': centroid_history,
            'final_centroids': final_centroids,
            'matriks_jarak': matriks_jarak,
            'total_data': len(df)
        }
    except Exception as e:
        print("Error detail K-Means:", e)
        return None