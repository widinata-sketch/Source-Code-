"""Uji alur lewat halaman web: semua halaman terbuka, transaksi tersimpan, laporan & CSV benar."""
import pytest


def isi_data(client):
    client.post("/modal", data={"jenis": "setoran", "tanggal": "2026-10-01", "jumlah": "5.000.000", "akun_id": "1"})
    client.post("/barang/baru", data={"kode": "BRG-001", "nama": "Beras 5 kg", "satuan": "karung",
                                      "harga_jual": "76000", "stok_minimum": "10"})
    client.post("/barang/baru", data={"kode": "BRG-002", "nama": "Minyak 2 L", "satuan": "pouch",
                                      "harga_jual": "37500", "stok_minimum": "12", "stok_awal": "4",
                                      "modal_awal": "33000", "tanggal_awal": "2026-10-01"})
    client.post("/pembelian/baru", data={"tanggal": "2026-10-02", "akun_id": "1", "pemasok": "CV A",
                                         "barang_id": ["1", "1"], "qty": ["10", "10"], "harga": ["10000", "12000"]})
    client.post("/penjualan/baru", data={"tanggal": "2026-10-05", "metode_bayar": "tunai", "akun_tunai": "1",
                                         "barang_id": ["1"], "qty": ["5"], "harga": ["15000"]})
    client.post("/penjualan/baru", data={"tanggal": "2026-10-06", "metode_bayar": "qris", "akun_nontunai": "3",
                                         "biaya_admin": "100", "barang_id": ["1", "2"], "qty": ["2", "1"],
                                         "harga": ["15000", "37500"]})
    client.post("/biaya", data={"tanggal": "2026-10-10", "kategori": "Sewa tempat", "jumlah": "50000",
                                "akun_id": "1"})


HALAMAN = [
    "/", "/?bulan=2026-10", "/barang", "/barang?f=isi", "/barang?nonaktif=1", "/barang/baru", "/barang/1",
    "/barang/1/edit", "/stok", "/stok?jenis=stok_awal", "/pembelian?bulan=2026-10", "/pembelian/baru",
    "/pembelian/1", "/pembelian/1/edit", "/penjualan?bulan=2026-10", "/penjualan/baru", "/penjualan/1",
    "/penjualan/2/edit", "/biaya?bulan=2026-10", "/biaya/1/edit", "/modal", "/pindah-dana",
    "/laporan/laba-rugi?bulan=2026-10", "/laporan/laba-rugi?mode=tahunan&tahun=2026",
    "/laporan/arus-kas?bulan=2026-10", "/laporan/arus-kas?mode=tahunan&tahun=2026",
    "/laporan/neraca?tanggal=2026-10-31", "/pengaturan", "/hutang", "/hutang?semua=1",
]


def test_dashboard_kosong_menampilkan_panduan(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Mulai pakai" in r.get_data(as_text=True)


@pytest.mark.parametrize("url", HALAMAN)
def test_semua_halaman_terbuka(client, url):
    isi_data(client)
    r = client.get(url)
    assert r.status_code == 200, url


def test_laporan_laba_rugi_berisi_angka_benar(client):
    isi_data(client)
    teks = client.get("/laporan/laba-rugi?bulan=2026-10").get_data(as_text=True)
    # penjualan 75.000 + 30.000 + 37.500; HPP 7 x 11.000 + 33.000
    assert "Rp 142.500" in teks
    assert "Rp 110.000" in teks
    assert "Biaya admin pembayaran" in teks


def test_neraca_seimbang_lewat_halaman(client):
    isi_data(client)
    teks = client.get("/laporan/neraca?tanggal=2026-10-31").get_data(as_text=True)
    assert "Seimbang" in teks


def test_csv_laporan(client):
    isi_data(client)
    for url in ["/laporan/laba-rugi?bulan=2026-10&format=csv", "/laporan/laba-rugi?mode=tahunan&tahun=2026&format=csv",
                "/laporan/arus-kas?bulan=2026-10&format=csv", "/laporan/neraca?tanggal=2026-10-31&format=csv"]:
        r = client.get(url)
        assert r.status_code == 200
        assert r.mimetype == "text/csv"
        assert ";" in r.get_data(as_text=True)


def test_penjualan_melebihi_stok_ditolak(client):
    isi_data(client)
    r = client.post("/penjualan/baru", data={"tanggal": "2026-10-07", "metode_bayar": "tunai", "akun_tunai": "1",
                                             "barang_id": ["2"], "qty": ["99"], "harga": ["37500"]})
    assert "tidak cukup" in r.get_data(as_text=True)
    assert "PJ-0003" not in client.get("/penjualan?bulan=2026-10").get_data(as_text=True)


def test_hapus_pembelian_yang_terjual_ditolak(client):
    isi_data(client)
    r = client.post("/pembelian/1/hapus", follow_redirects=True)
    assert "tidak bisa dihapus" in r.get_data(as_text=True)


def test_alur_pembelian_tempo(client):
    isi_data(client)
    r = client.post("/pembelian/baru", data={
        "tanggal": "2026-10-08", "pemasok": "UD Makmur", "no_faktur": "INV-77", "akun_id": "1",
        "cara_bayar": "tempo", "jatuh_tempo": "2026-10-22", "uang_muka": "50.000",
        "barang_id": ["2"], "qty": ["10"], "harga": ["33000"],
    }, follow_redirects=True)
    teks = r.get_data(as_text=True)
    assert "Hutang tercatat" in teks
    assert "Rp 280.000" in teks  # sisa hutang 330.000 - 50.000

    teks = client.get("/hutang").get_data(as_text=True)
    assert "INV-77" in teks and "UD Makmur" in teks

    r = client.post("/hutang/2/bayar", data={"tanggal": "2026-10-20", "jumlah": "100000", "akun_id": "2"},
                    follow_redirects=True)
    assert "Sisa hutang Rp 180.000" in r.get_data(as_text=True)

    teks = client.get("/laporan/neraca?tanggal=2026-10-31").get_data(as_text=True)
    assert "Hutang usaha" in teks and "Rp 180.000" in teks and "Seimbang" in teks

    r = client.post("/hutang/2/bayar", data={"tanggal": "2026-10-21", "jumlah": "999999", "akun_id": "1"},
                    follow_redirects=True)
    assert "melebihi sisa hutang" in r.get_data(as_text=True)

    client.post("/hutang/2/bayar", data={"tanggal": "2026-10-21", "jumlah": "180000", "akun_id": "1"})
    assert "Tidak ada hutang" in client.get("/hutang").get_data(as_text=True)
    assert client.get("/pembelian/2").status_code == 200


def test_pindah_dana_dan_backup(client):
    isi_data(client)
    r = client.post("/pindah-dana", data={"tanggal": "2026-10-20", "dari_akun_id": "1", "ke_akun_id": "2",
                                          "jumlah": "100000"}, follow_redirects=True)
    assert "Pindah dana Rp 100.000 dicatat" in r.get_data(as_text=True)
    r = client.get("/pengaturan/backup")
    assert r.status_code == 200
    assert r.data[:15] == b"SQLite format 3"
    r.close()


def test_barang_baru_dari_form_pembelian(client):
    isi_data(client)
    teks = client.get("/pembelian/baru").get_data(as_text=True)
    assert 'id="buka-barang-baru"' in teks and 'id="dlg-barang"' in teks
    assert 'value="BRG-003"' in teks  # kode berikutnya sudah terisi di pop-up

    r = client.post("/barang/cepat", data={"kode": "", "nama": "Dispenser Baru", "satuan": "unit",
                                           "harga_jual": "1.500.000", "stok_minimum": "2"})
    assert r.status_code == 200
    b = r.get_json()
    assert b["kode"] == "BRG-003" and b["nama"] == "Dispenser Baru" and b["satuan"] == "unit"
    assert b["harga_jual"] == 1500000 and b["kode_berikut"] == "BRG-004"

    # barang baru langsung bisa dipakai di pembelian, dan muncul di dropdown form
    client.post("/pembelian/baru", data={"tanggal": "2026-10-20", "akun_id": "1", "barang_id": [str(b["id"])],
                                         "qty": ["3"], "harga": ["1200000"]})
    teks = client.get("/barang").get_data(as_text=True)
    assert "Dispenser Baru" in teks and "Rp 3.600.000" in teks
    assert "BRG-003 · Dispenser Baru" in client.get("/pembelian/baru").get_data(as_text=True)


@pytest.mark.parametrize("data, pesan", [
    ({"nama": ""}, "wajib diisi"),
    ({"kode": "BRG-001", "nama": "Kembar"}, "sudah dipakai"),
    ({"nama": "Minus", "harga_jual": "-5"}, "tidak boleh negatif"),
])
def test_barang_baru_cepat_menolak_isian_salah(client, data, pesan):
    isi_data(client)
    r = client.post("/barang/cepat", data=data)
    assert r.status_code == 400
    assert pesan in r.get_json()["galat"]
    assert "Kembar" not in client.get("/barang").get_data(as_text=True)


def test_file_static_diberi_versi_supaya_tidak_tertahan_cache(client):
    teks = client.get("/pembelian/baru").get_data(as_text=True)
    assert "/static/transaksi.js?v=" in teks and "/static/style.css?v=" in teks
    assert client.get("/static/transaksi.js?v=123").status_code == 200
