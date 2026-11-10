# 📋 Customer Information Questionnaire (CIQ) Specification

**Document Version:** 2.3.0  
**Target User:** Product Manager, Business Unit (BU), & Core Engineering IOH  

Dokumen ini mendefinisikan standar kolom input file CIQ (Excel `.xlsx` / CSV `.csv`) yang didukung oleh **RELPOOL Batch Processing Engine**.

Current validation requires `product_type`, `apn_name`, `app_name`, `rg_val` and `sid_val` columns with nonempty values. New Product and Reguler Update also require explicit domains. Other missing fields use documented application defaults; complete templates are recommended. Duplicate/ambiguous aliases are rejected; substring guessing is disabled. Limits: 5 MB upload, 1000 rows, 100 domains per application. Legacy `.xls` is not accepted.

CSV cells containing commas must be quoted: `"*.tiktok.com, *.v2.tiktokcdn.com"`. Select the exact charging value `Special Rate (differentiate RG)` when applicable. QCI, speed and capping selections are recorded as comments; the engine does not implement those policies.

---

## 1. Daftar Kolom & Pemetaan Alias

Engine RELPOOL dilengkapi fitur **Auto-Aliasing** sehingga penamaan header tabel tidak harus kaku:

| Kolom Standar | Tipe Data | Wajib? | Contoh Nilai | Alias yang Dikenali |
|---|---|---|---|---|
| `product_type` | String | Ya | `New Product`, `Revamp`, `Reguler Update` | `Tipe Produk`, `req_type`, `jenis_produk` |
| `user_profile` | String | Ya | `New`, `Existing` | `profile`, `profile_type`, `tipe_profile` |
| `apn_name` | String | Ya | `internet_im3`, `b2b_corporate` | `APN`, `nama_apn`, `target_apn` |
| `charging_type` | String | Ya | `Zero Rating`, `Special Rate` | `tipe_charging`, `billing_type` |
| `rg_val` | Numerik | Ya | `11010`, `20000`, `30000` | `Rating Group`, `rg_id`, `rg` |
| `sid_val` | Numerik | Ya | `11001000`, `20001000` | `Service ID`, `sid_id`, `sid` |
| `capping_option` | String | Tidak | `20 MB/day`, `No Capping` | `capping`, `kuota_capping`, `capping_limit` |
| `header_enrichment` | String | Tidak | `Yes`, `No` | `he`, `he_required` |
| `speed_limit` | String | Ya | `Full Speed`, `Throttle 256kbps` | `kecepatan`, `bandwidth`, `qos_speed` |
| `qci_val` | String | Ya | `9 (Default Internet)`, `1 (Voice/Low Latency)` | `QCI`, `qci_profile` |
| `app_category` | String | Tidak | `Well Known Apps`, `Local Apps` | `kategori_aplikasi`, `category` |
| `app_name` | String | Ya | `TikTok`, `Gojek Driver`, `Mobile Legends` | `nama_aplikasi`, `target_app` |
| `app_domain` | String (Multi) | Ya | `*.tiktok.com, *.v2.tiktokcdn.com` | `domain`, `url`, `target_domain` |

---

## 2. Aturan Format Domain & URL

* **Protokol:** Jangan sertakan `http://` atau `https://`. Jika tim komersial menyertakannya, engine otomatis membuangnya.
* **Trailing Slash:** Karakter `/` di ujung URL otomatis dihilangkan.
* **Multi-Domain:** Pisahkan beberapa domain menggunakan koma (`,`) atau baris baru (`\n`). Setiap domain akan otomatis dibuatkan baris konfigurasi `host` dan `filter` terpisah di Huawei Service-V.
