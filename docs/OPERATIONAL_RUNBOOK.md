# 📖 NOC Operational Runbook — Core Service Provisioning

**Document Version:** 2.2.0  
**Scope:** GGSN PCEF & PCRF UPCC Production & Testbed Deployment  
**Role:** MCPE Core Engineer / NOC Operations  

> **v2.3 operational status:** Live execution is blocked in the UI. Simulation only lists commands and does not validate vendor syntax or network impact. The procedures below are historical reference, not authorization to bypass this block. Implement device pre-checks, object ownership checks, configuration snapshots, verified rollback and post-change service checks before restoring live execution. Downloaded rollbacks are drafts; delta updates intentionally contain no executable rollback without a snapshot. Follow the [reliability roadmap](RELIABILITY_AND_ML_ROADMAP.md).

---

## 1. Pre-Execution Checklist
Sebelum mendorong script MML ke router core Huawei:
1. Pastikan koneksi VPN Indosat aktif jika mengakses node live.
2. Lakukan pengecekan konfigurasi pada **🧪 Simulation Mode** di RELPOOL UI untuk memeriksa urutan eksekusi perintah MML.
3. Unduh dan simpan file **Safe Rollback Script (`.txt`)** ke storage lokal sebelum mengeksekusi script provisioning.
4. Catat nomor **Work Order (WO ID)** yang terbentuk di tabel *Audit Trail*.

---

## 2. Prosedur Eksekusi Provisioning
1. **Verifikasi Sintaks:**
   Periksa blok konfigurasi:
   * Objek `host` sequence 65535
   * Objek `filter` L34-protocol any
   * Objek `filter-group` binding
   * Parameter `cbb-id` online / offline
   * Binding `user-profile crbn_{apn}_sy` priority 27000
2. **Push Configuration:**
   * Klik tombol **"🚀 Push Config to Testbed Node"**.
   * Tunggu status bar selesai (`✅ EXECUTION COMPLETED`).
   * Tinjau setiap baris log eksekusi terminal.

---

## 3. Post-Execution Verification
Jalankan verifikasi langsung pada node via Service-V CLI:
```text
display service-v user-profile crbn_{apn}_sy
display service-v rule r_{app}_{rg}_{sid}
display service-v filter-group fg_gaspol_{app}
```
Pastikan seluruh filter status menunjukkan `ACTIVE` dan tidak ada alarm drop traffic.

---

## 4. Emergency Rollback Procedure
Jika terjadi kegagalan charging (*billing mismatch*) atau gangguan traffic pelanggan:
1. Buka Tab **🔄 Safe Rollback CLI** pada Work Order yang bersangkutan di RELPOOL UI.
2. Salin seluruh isi rollback script atau klik **📥 Download Rollback Script (.txt)**.
3. Eksekusi ke node untuk melepas rule-binding:
   ```text
   user-profile crbn_{apn}_sy
   undo rule-binding r_{app}_{rg}_{sid}
   q
   undo rule r_{app}_{rg}_{sid}
   undo category-group catg_{rg}_{sid}
   undo charge-property cp_{rg}_{sid}
   undo cbb-id cbbid_off_{rg}_{sid}
   undo cbb-id cbbid_on_{rg}
   undo filter-group fg_gaspol_{app}
   save
   Y
   ```
4. Laporkan insiden ke Incident Manager dan sertakan log Work Order dari tabel Audit Trail.
