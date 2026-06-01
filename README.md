# Webcam Tower Bloxx

## Daftar Isi

- [Overview](#overview)
- [Dependencies](#dependencies)
- [Cara Build dan Run Project](#cara-build-dan-run-project)
- [Kontrol](#kontrol)
- [Aturan Game](#aturan-game)
- [Input dan Deteksi](#input-dan-deteksi)
- [Progress](#progress)
- [Hasil Akhir](#hasil-akhir)
- [Struktur File](#struktur-file)
- [Catatan Kalibrasi](#catatan-kalibrasi)

## Overview

Project ini adalah mini game bergaya Tower Bloxx yang dikembangkan dengan
Python, OpenCV, dan NumPy. Pemain menggunakan sarung tangan atau objek berwarna
biru sebagai input gesture untuk mengambil blok bangunan, membawa blok ke zona
release di bagian atas layar, lalu membuka pinch untuk menjatuhkan blok ke atas
tower. Tujuan game adalah membuat tower setinggi mungkin.

Game ini tidak menggunakan game engine atau framework game. Seluruh tampilan,
input webcam, deteksi gesture, rendering sprite, scoring, HP, audio, dan
background dibuat langsung menggunakan OpenCV, NumPy, dan library standar
Python.

Fitur utama:

- Webcam real-time menggunakan `cv2.VideoCapture`.
- Deteksi objek biru menggunakan HSV color masking.
- Manipulasi mask biner menggunakan operasi array NumPy.
- Morfologi manual: opening dan closing.
- Gesture recognition untuk membedakan kondisi `pinch` dan `open`.
- Tower stacking dengan collision berbasis overlap horizontal.
- Score system dengan `Success`, `Perfect`, dan perfect streak bonus.
- HP system menggunakan sprite heart.
- BGM dan sound effect untuk drop biasa dan perfect landing.
- Background parallax bertahap dari city, cloud layer, sampai space.

## Dependencies

- Python 3.10 atau lebih baru
- OpenCV Python
- NumPy
- Webcam laptop atau kamera eksternal

Install dependency:

```bash
pip install opencv-python numpy
```

Audio memakai Windows MCI melalui library standar Python, jadi tidak perlu
install package audio tambahan.

## Cara Build dan Run Project

Project Python ini tidak perlu proses compile seperti C++/SFML. Ikuti langkah
berikut untuk menjalankan game:

1. Pastikan Python, OpenCV, dan NumPy sudah terpasang.
2. Clone atau download repository ini ke komputer.
3. Pastikan webcam laptop aktif dan tidak sedang dipakai aplikasi lain.
4. Jalankan game dari terminal:

   ```bash
   python Skyscraper.py
   ```

5. Jendela `Skyscraper` akan menampilkan game, sedangkan jendela `BLUE MASK`
   menampilkan hasil segmentasi warna biru.

## Kontrol

| Input | Fungsi |
|-------|--------|
| Sarung tangan/objek biru | Input utama tracking gesture |
| Pinch dua jari di atas blok | Mengambil blok bangunan |
| Tahan pinch | Menggerakkan blok mengikuti posisi jari |
| Buka pinch di `TOP RELEASE ZONE` | Melepas blok agar jatuh |
| **R** | Restart setelah game over |
| **Q** | Keluar dari game |

## Aturan Game

- Pemain mulai dengan 3 HP, ditampilkan sebagai heart di pojok kanan bawah.
- Jika blok jatuh atau meleset dari tower, pemain kehilangan 1 HP.
- Game over terjadi ketika HP habis.
- Blok berhasil ditumpuk jika overlap horizontal dengan tower cukup besar.
- Jika landing tidak sejajar tetapi overlap masih cukup, blok tetap ditumpuk
  utuh tanpa memotong bagian yang menggantung.
- Setiap blok yang berhasil ditumpuk dihitung sebagai 1 floor.
- `Success` memberi 25 poin.
- `Perfect` memberi 50 poin jika posisi blok sangat sejajar dengan blok
  sebelumnya.
- Perfect beruntun memberi bonus tambahan 25 poin per streak. Contoh: Perfect
  pertama 50 poin, Perfect kedua 75 poin, Perfect ketiga 100 poin.

## Input dan Deteksi

Pipeline deteksi gesture:

1. Kamera dibaca memakai `cv2.VideoCapture(0)`.
2. Frame diproses dalam ruang warna HSV.
3. Objek biru dideteksi dari rentang `H`, `S`, dan `V`.
4. Mask diperketat dengan dominasi channel biru pada BGR agar warna lain tidak
   mudah ikut terdeteksi.
5. Mask biner dibuat memakai operasi array NumPy.
6. Noise dibersihkan dengan opening dan closing manual.
7. Contour biru terbesar yang memenuhi batas area dianggap sebagai objek input.
8. Titik kontrol dihitung dari area celah/jepitan di antara jari.
9. Gesture `open` dideteksi saat sisi depan contour memiliki celah berbentuk C.
10. Gesture `pinch` dideteksi saat celah tersebut hilang atau terlalu kecil.

## Progress

| Tahap | Status | Keterangan |
|-------|--------|------------|
| M7 | Selesai | Webcam input, HSV masking, morfologi manual, dan tracking objek biru |
| M7 | Selesai | Gesture `pinch` dan `open` untuk mengambil/melepas blok |
| M7 | Selesai | Prototype Tower Bloxx dengan stacking dan scoring dasar |
| M15 | Selesai | Sprite gedung, heart HP, score system, perfect streak, dan game over |
| M15 | Selesai | Background parallax city-cloud-space dan kamera scroll halus |
| M15 | Selesai | BGM dan sound effect dari folder `assets/sound` |
| M15 | To be added | Dokumentasi screenshot dan video demonstrasi |

## Hasil Akhir

Hasil akhir project adalah mini game `Skyscraper` berbasis webcam. Pemain
menggunakan gesture pinch dari sarung tangan/objek biru untuk menyusun blok
bangunan setinggi mungkin.

Fitur yang sudah tersedia:

- Real-time camera input.
- Blue glove tracking.
- Gesture detection.
- Stackable building block.
- Second object berupa blok bangunan/sprite gedung.
- Score, floor counter, HP heart, dan game over.
- BGM, drop sound, dan perfect drop sound.
- Background bertahap dari kota ke awan lalu luar angkasa.
- Asset gedung dari folder `assets/buildings`.

Dokumentasi: To be added.

## Struktur File

```text
webcam-tower-bloxx/
|-- assets/
|   |-- buildings/
|   |   |-- blue_first_floor.jpg
|   |   |-- blue_upper_floor.jpg
|   |   |-- red_first_floor.jpg
|   |   |-- red_upper_floor.jpg
|   |   |-- green_first_floor.jpg
|   |   |-- green_upper_floor.jpg
|   |   |-- brown_first_floor.jpg
|   |   `-- brown_upper_floor.jpg
|   `-- sound/
|       |-- bgm.mp3
|       |-- drop.mp3
|       `-- drop-perfect.mp3
|-- docs/
|   `-- screenshots/
|-- heart.png
|-- audio_manager.py
|-- Skyscraper.py
|-- tracking.py
`-- README.md
```

Dokumentasi: To be added.

## Catatan Kalibrasi

Jika objek biru belum terdeteksi stabil, ubah nilai berikut di `tracking.py`:

- `BLUE_HUE_MIN` dan `BLUE_HUE_MAX`: rentang warna biru pada HSV OpenCV.
- `BLUE_SATURATION_MIN`: semakin kecil, biru pucat lebih mudah terdeteksi.
- `BLUE_VALUE_MIN`: semakin kecil, biru pada kondisi gelap lebih mudah
  terdeteksi.
- `BLUE_OVER_GREEN_MIN` dan `BLUE_OVER_RED_MIN`: semakin besar, deteksi makin
  ketat ke warna biru.
- `MIN_BLUE_AREA`: semakin besar, filter ukuran objek biru semakin ketat.
- `MAX_BLUE_AREA_RATIO`: membatasi contour terlalu besar agar background biru
  tidak dipilih sebagai input.
- `OPEN_KERNEL_SIZE`: membersihkan noise kecil.
- `CLOSE_KERNEL_SIZE`: menutup lubang kecil.
- `CENTER_SMOOTHING_ALPHA`: semakin kecil, titik pusat makin stabil tetapi
  gerakan lebih lambat mengikuti tangan.
- `FAST_CENTER_SMOOTHING_ALPHA`: dipakai saat gerakan besar agar tracking lebih
  responsif.
- `CENTER_DEADZONE_PIXELS`: perubahan kecil diabaikan agar titik tidak bergetar.
- `OPEN_GAP_SCAN_WIDTH_RATIO`: lebar area depan contour untuk mencari celah
  gesture open.
- `PINCH_FRONT_SCAN_WIDTH_RATIO`: fallback untuk mencari titik pinch saat game
  langsung dimulai dalam kondisi pinch.

Konstanta gameplay yang sering diubah ada di `Skyscraper.py`:

- `WINDOW_WIDTH` dan `WINDOW_HEIGHT`: ukuran render game.
- `BLOCK_WIDTH_RATIO`: ukuran lebar blok. Nilai saat ini dibuat sedikit lebih
  kecil agar game terlihat lebih zoom out.
- `BLOCK_SPAWN_X_RATIO` dan `BLOCK_SPAWN_TOP_OFFSET`: posisi awal blok baru.
- `RELEASE_ZONE_RATIO`: tinggi zona release di bagian atas layar.
- `PERFECT_ALIGNMENT_PIXELS`: toleransi alignment agar stack dianggap Perfect.
- `MIN_LANDING_OVERLAP_RATIO`: minimal overlap agar blok dianggap berhasil.
- `TOWER_SCROLL_MARGIN_RATIO`: posisi tower setelah kamera scroll.
- `CAMERA_SCROLL_STEP_RATIO`: kecepatan scroll kamera bertahap.
- `CLOUD_START_FLOOR` dan `CLOUD_FULL_FLOOR`: transisi city ke cloud.
- `SPACE_START_FLOOR` dan `SPACE_FULL_FLOOR`: transisi cloud ke space.
