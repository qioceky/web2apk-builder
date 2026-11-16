#!/usr/bin/env python3
"""Web2APK Builder — generate project Android (WebView) dari input workflow_dispatch.

Input lewat environment variable (diisi workflow dari inputs):
  SITE_URL, APP_NAME, PACKAGE_ID, VERSION_NAME, THEME_COLOR, ICON_URL,
  OPT_JAVASCRIPT, OPT_ZOOM, OPT_FILE_UPLOAD, OPT_EXTERNAL_LINKS,
  OPT_SPLASH, OPT_HIDE_TOOLBAR, OPT_PULL_REFRESH, OPT_COOKIES  ("true"/"false")
Output: project lengkap di ./out
"""
import io
import os
import re
import shutil
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(ROOT, "template")
OUT = os.path.join(ROOT, "out")

TEXT_FILES = {
    "settings.gradle.tmpl": "settings.gradle",
    "build.gradle.tmpl": "build.gradle",
    "gradle.properties.tmpl": "gradle.properties",
    "gradle/libs.versions.toml.tmpl": "gradle/libs.versions.toml",
    "app/build.gradle.tmpl": "app/build.gradle",
    "app/src/main/AndroidManifest.xml.tmpl": "app/src/main/AndroidManifest.xml",
    "app/src/main/res/values/strings.xml.tmpl": "app/src/main/res/values/strings.xml",
    "app/src/main/res/values/themes.xml.tmpl": "app/src/main/res/values/themes.xml",
    "app/src/main/assets/config.json.tmpl": "app/src/main/assets/config.json",
}
RAW_FILES = {
    "gradlew": "gradlew",
    "gradle/wrapper/gradle-wrapper.jar": "gradle/wrapper/gradle-wrapper.jar",
    "gradle/wrapper/gradle-wrapper.properties": "gradle/wrapper/gradle-wrapper.properties",
}


def env(name, default=""):
    return os.environ.get(name, default).strip()


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "", name.lower())
    if not s or s[0].isdigit():
        s = "app" + s
    return s


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Linux; Android 14) Web2APK-Builder"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.geturl()


def find_icon_url(site_url, icon_input):
    if icon_input:
        return icon_input
    try:
        data, final = fetch(site_url)
        html = data.decode("utf-8", "ignore")[:300_000]
        best, best_size = "", -1
        for tag in re.findall(r"<link[^>]+>", html, re.I):
            rel = (re.search(r"rel=[\"'](.*?)[\"']", tag, re.I) or [None, ""])[1].lower()
            if "icon" not in rel:
                continue
            href = (re.search(r"href=[\"'](.*?)[\"']", tag, re.I) or [None, ""])[1]
            if not href:
                continue
            sizes = (re.search(r"sizes=[\"'](.*?)[\"']", tag, re.I) or [None, ""])[1]
            m = re.search(r"(\d+)x\d+", sizes)
            size = int(m.group(1)) if m else (180 if "apple" in rel else 32)
            if size > best_size:
                best, best_size = href, size
        if best:
            return urllib.request.urljoin(final, best)
        return urllib.request.urljoin(final, "/favicon.ico")
    except Exception as e:
        print(f"::warning::Gagal mencari ikon situs: {e}")
        return ""


def make_icons(cfg, icon_url):
    """Tulis ikon mipmap ke OUT dari ikon situs, atau ikon huruf bila gagal."""
    from PIL import Image, ImageDraw, ImageFont

    base = None
    if icon_url:
        try:
            data, _ = fetch(icon_url)
            base = Image.open(io.BytesIO(data)).convert("RGBA")
            print(f"Ikon situs dipakai: {icon_url} ({base.size[0]}x{base.size[1]})")
        except Exception as e:
            print(f"::warning::Ikon situs gagal dipakai ({e}) — pakai ikon huruf.")
            base = None
    if base is None:
        base = Image.new("RGBA", (192, 192), (0, 0, 0, 0))
        d = ImageDraw.Draw(base)
        color = cfg["theme_rgb"]
        d.rounded_rectangle([0, 0, 191, 191], radius=38, fill=color + (255,))
        letter = (cfg["app_name"].strip()[:1] or "W").upper()
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 110)
        except Exception:
            font = ImageFont.load_default()
        d.text((96, 100), letter, fill=(255, 255, 255, 255), font=font, anchor="mm")

    sizes = {"mipmap-mdpi": 48, "mipmap-hdpi": 72, "mipmap-xhdpi": 96,
             "mipmap-xxhdpi": 144, "mipmap-xxxhdpi": 192}
    for dirname, size in sizes.items():
        d = os.path.join(OUT, "app/src/main/res", dirname)
        os.makedirs(d, exist_ok=True)
        img = base.resize((size, size), Image.LANCZOS)
        img.save(os.path.join(d, "ic_launcher.png"))
        img.save(os.path.join(d, "ic_launcher_round.png"))
    fg = Image.new("RGBA", (432, 432), (0, 0, 0, 0))
    fg.paste(base.resize((264, 264), Image.LANCZOS), (84, 84))
    fg.save(os.path.join(OUT, "app/src/main/res/mipmap-xxxhdpi/ic_launcher_foreground.png"))
    anydpi = os.path.join(OUT, "app/src/main/res/mipmap-anydpi-v26")
    os.makedirs(anydpi, exist_ok=True)
    adaptive = ('<?xml version="1.0" encoding="utf-8"?>\n'
                '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
                '    <background android:drawable="@color/ic_bg"/>\n'
                '    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>\n'
                '</adaptive-icon>\n')
    open(os.path.join(anydpi, "ic_launcher.xml"), "w").write(adaptive)
    open(os.path.join(anydpi, "ic_launcher_round.xml"), "w").write(adaptive)
    hexcol = "#%02X%02X%02X" % cfg["theme_rgb"]
    vals = os.path.join(OUT, "app/src/main/res/values")
    os.makedirs(vals, exist_ok=True)
    open(os.path.join(vals, "colors.xml"), "w").write(
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        f'    <color name="ic_bg">{hexcol}</color>\n</resources>\n')


def main():
    site_url = env("SITE_URL")
    if site_url and not site_url.startswith(("http://", "https://")):
        site_url = "https://" + site_url
    app_name = env("APP_NAME")
    package_id = env("PACKAGE_ID")
    if not site_url or not app_name or not package_id:
        print("::error::SITE_URL, APP_NAME, PACKAGE_ID wajib diisi.")
        return 1
    if not re.match(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$", package_id):
        print(f"::error::PACKAGE_ID tidak valid: {package_id}")
        return 1
    theme = env("THEME_COLOR", "#FFD02E")
    m = re.match(r"#?([0-9a-fA-F]{6})$", theme)
    theme_rgb = tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4)) if m else (255, 208, 46)
    theme = "#%02X%02X%02X" % theme_rgb

    def b(name):
        return "true" if env(name, "true").lower() == "true" else "false"

    tokens = {
        "__APP_NAME__": app_name,
        "__APP_NAME_JSON__": app_name.replace("\\", "\\\\").replace('"', '\\"'),
        "__APP_NAME_XML__": (app_name.replace("&", "&amp;").replace("<", "&lt;")
                             .replace(">", "&gt;").replace('"', "&quot;").replace("'", "\\'")),
        "__PROJECT_NAME__": re.sub(r"[^A-Za-z0-9 ]", "", app_name).strip() or "WebApp",
        "__PROJECT_SLUG__": slug(app_name),
        "__PACKAGE__": package_id,
        "__URL__": site_url,
        "__VERSION_NAME__": env("VERSION_NAME", "1.0") or "1.0",
        "__VERSION_CODE__": "1",
        "__THEME_COLOR__": theme,
        "__OPT_JAVASCRIPT__": b("OPT_JAVASCRIPT"),
        "__OPT_ZOOM__": b("OPT_ZOOM"),
        "__OPT_FILE_UPLOAD__": b("OPT_FILE_UPLOAD"),
        "__OPT_EXTERNAL_LINKS__": b("OPT_EXTERNAL_LINKS"),
        "__OPT_SPLASH__": b("OPT_SPLASH"),
        "__OPT_HIDE_TOOLBAR__": b("OPT_HIDE_TOOLBAR"),
        "__OPT_PULL_REFRESH__": b("OPT_PULL_REFRESH"),
        "__OPT_COOKIES__": b("OPT_COOKIES"),
    }

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    for src, dest in TEXT_FILES.items():
        text = open(os.path.join(TEMPLATE, src), encoding="utf-8").read()
        for k, v in tokens.items():
            text = text.replace(k, v)
        leftover = re.findall(r"__[A-Z_]+__", text)
        if leftover:
            print(f"::error::Token belum terganti di {src}: {leftover}")
            return 1
        path = os.path.join(OUT, dest)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w", encoding="utf-8").write(text)

    main_src = open(os.path.join(TEMPLATE, "app/src/main/java/MainActivity.kt.tmpl"), encoding="utf-8").read()
    for k, v in tokens.items():
        main_src = main_src.replace(k, v)
    pkg_path = os.path.join(OUT, "app/src/main/java", *package_id.split("."))
    os.makedirs(pkg_path, exist_ok=True)
    open(os.path.join(pkg_path, "MainActivity.kt"), "w", encoding="utf-8").write(main_src)
    open(os.path.join(OUT, "app/proguard-rules.pro"), "w").write(
        "# Dibuat Web2APK Builder — WebView murni.\n")

    for src, dest in RAW_FILES.items():
        path = os.path.join(OUT, dest)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.copyfile(os.path.join(TEMPLATE, src), path)
    os.chmod(os.path.join(OUT, "gradlew"), 0o755)

    icon_url = find_icon_url(site_url, env("ICON_URL"))
    make_icons({"app_name": app_name, "theme_rgb": theme_rgb}, icon_url)
    print(f"Project tergenerate di {OUT}: {app_name} ({package_id}) -> {site_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
