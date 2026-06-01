# Webcam Tower Bloxx

Project ini memakai Python, OpenCV, dan NumPy untuk membuat mini game bergaya
Tower Bloxx. Pemain memakai objek/sarung tangan warna biru sebagai titik pinch
untuk mengambil blok bangunan, membawa blok ke zona release di bagian atas
layar, lalu menjatuhkannya ke atas tower. Tujuannya adalah membuat tower
setinggi mungkin.

## Input dan Deteksi

- Kamera dibaca memakai `cv2.VideoCapture(0)`.
- Frame diproses dalam ruang warna HSV.
- Objek biru dideteksi dari rentang `H`, `S`, dan `V` pada HSV.
- Deteksi dilakukan pada seluruh frame kamera.
- Mask juga diperketat dengan dominasi channel biru pada BGR agar warna lain
  tidak mudah ikut terdeteksi.
- Mask biner dibuat manual memakai operasi array NumPy.
- Noise dibersihkan dengan operasi morfologi manual:
  - Opening: erosi lalu dilasi.
  - Closing: dilasi lalu erosi.
- Contour terbesar yang memenuhi batas area dianggap sebagai objek biru.
- Titik pusat objek biru dihitung memakai distance transform pada contour
  terpilih.
- Titik pusat distabilkan dengan smoothing adaptif agar tidak terlalu bergetar.

## Gameplay

- Sentuhkan titik biru ke blok yang berada di sisi bawah layar untuk melakukan
  pinch/grab.
- Saat blok sudah terpegang, gerakkan objek biru ke zona hijau di bagian atas.
- Blok hanya bisa release di zona atas. Ketika titik biru masuk zona tersebut,
  blok otomatis jatuh.
- Blok berhasil menumpuk jika overlap horizontal dengan tower cukup besar.
- Skor `Height` bertambah setiap blok berhasil ditumpuk.
- Jika blok meleset terlalu jauh, game over.

## Kontrol

- `q`: keluar dari game.
- `r`: restart setelah game over.

## Menjalankan

```bash
python Skyscraper.py
```

Tekan `q` untuk keluar dari jendela kamera.

## Struktur File

- `Skyscraper.py`: file utama berisi logic Tower Bloxx, scoring, rendering
  game, webcam loop, kontrol keyboard, dan import tracking.
- `tracking.py`: modul tracking warna biru berisi mask NumPy, morfologi manual,
  contour selection, dan smoothing titik tracking.

## Catatan Kalibrasi

Jika objek biru belum terdeteksi stabil, ubah nilai berikut di
`tracking.py`:

- `BLUE_HUE_MIN` dan `BLUE_HUE_MAX`: rentang warna biru pada HSV OpenCV.
- `BLUE_SATURATION_MIN`: semakin kecil nilainya, biru pucat lebih mudah
  terdeteksi.
- `BLUE_VALUE_MIN`: semakin kecil nilainya, biru pada kondisi gelap lebih mudah
  terdeteksi.
- `BLUE_OVER_GREEN_MIN` dan `BLUE_OVER_RED_MIN`: semakin besar nilainya,
  deteksi makin ketat ke warna biru.
- `MIN_BLUE_AREA`: semakin besar nilainya, semakin ketat filter ukuran objek.
- `MAX_BLUE_AREA_RATIO`: membatasi contour terlalu besar agar background biru
  tidak dipilih sebagai objek.
- `OPEN_KERNEL_SIZE`: membersihkan noise kecil.
- `CLOSE_KERNEL_SIZE`: menutup lubang kecil. Jika terlalu besar, noise bisa
  melebar, jadi nilai saat ini dibuat kecil.
- `CENTER_SMOOTHING_ALPHA`: semakin kecil nilainya, titik pusat makin stabil
  tetapi gerakannya lebih lambat mengikuti tangan.
- `FAST_CENTER_SMOOTHING_ALPHA`: dipakai saat gerakan besar agar titik pusat
  mengejar tangan lebih cepat.
- `CENTER_DEADZONE_PIXELS`: perubahan kecil di bawah nilai ini diabaikan agar
  titik pusat tidak bergetar.
- `FAST_MOVEMENT_PIXELS`: batas jarak gerakan yang dianggap cepat.
- `RADIUS_SMOOTHING_ALPHA`: menghaluskan perubahan ukuran lingkaran deteksi.

Konstanta gameplay:

- `RELEASE_ZONE_RATIO`: tinggi zona release di bagian atas layar.
- `PINCH_MARGIN_PIXELS`: toleransi jarak agar titik biru dapat mengambil blok.
- `MIN_LANDING_OVERLAP_RATIO`: minimal overlap agar blok dianggap berhasil
  menumpuk.
- `DROP_GRAVITY` dan `DROP_MAX_SPEED`: kecepatan jatuh blok.
