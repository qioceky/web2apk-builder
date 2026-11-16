# Web2APK Builder

Repo pembangun untuk aplikasi **Web2APK**: workflow `build-apk` menerima
input website dari aplikasi (workflow_dispatch), menggenerate project
Android WebView dari `template/`, membangunnya, dan menerbitkan APK jadi
ke **Releases** repo ini.

## Rahasia yang wajib ada (Settings → Secrets → Actions)

- `GENAPP_KEYSTORE_BASE64` — keystore tetap (base64), dipakai menandatangani
  SEMUA APK hasil builder ini agar update bisa saling menimpa
- `GENAPP_KEYSTORE_PASSWORD`
- `GENAPP_KEY_ALIAS`
- `GENAPP_KEY_PASSWORD`

Tanpa secret ini build sengaja digagalkan — APK tidak boleh bertanda
tangan acak.

## Cara pakai manual

Tab **Actions → build-apk → Run workflow**, isi alamat website, nama
aplikasi, dan Package ID. APK terbit di tab **Releases**.
