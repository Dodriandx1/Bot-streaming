"""
Constructor del comando FFmpeg
─────────────────────────────────
Toma la configuración del usuario (calidad, codec, preset, etc.)
y devuelve el comando FFmpeg listo para ejecutar.
"""

import os


# ─── PRESETS DE CALIDAD ───
# CRF más bajo = mejor calidad, archivo más grande
QUALITY_PRESETS = {
    "original": {"crf": "18", "preset": "medium",  "label": "Original (CRF 18)"},
    "alta":     {"crf": "20", "preset": "medium",  "label": "Alta (CRF 20)"},
    "media":    {"crf": "23", "preset": "medium",  "label": "Media (CRF 23)"},
    "baja":     {"crf": "28", "preset": "fast",    "label": "Baja (CRF 28)"},
    "rapida":   {"crf": "26", "preset": "veryfast","label": "Rápida (CRF 26)"},
    "ultra":    {"crf": "30", "preset": "ultrafast","label": "Ultra Rápida (CRF 30)"},
}

# ─── CÓDECS DE VIDEO ───
VIDEO_CODECS = {
    "h264": {"codec": "libx264", "label": "H.264 (compatible)"},
    "h265": {"codec": "libx265", "label": "H.265 / HEVC (mejor compresión)"},
    "copy": {"codec": "copy",    "label": "Copiar (sin recodificar)"},
}

# ─── CÓDECS DE AUDIO ───
AUDIO_CODECS = {
    "aac": {"codec": "aac",  "bitrate": "192k", "label": "AAC 192k"},
    "mp3": {"codec": "libmp3lame", "bitrate": "192k", "label": "MP3 192k"},
    "opus":{"codec": "libopus", "bitrate": "128k", "label": "Opus 128k"},
    "copy":{"codec": "copy",  "bitrate": None,   "label": "Copiar (sin recodificar)"},
}


def build_ffmpeg_command(input_path: str, output_path: str, config: dict,
                          audio_map: str = "0:a?",
                          extra_vf: str | None = None) -> list:
    """
    Construye el comando FFmpeg basado en la configuración del usuario.

    Args:
        input_path:  Ruta del archivo de entrada
        output_path: Ruta del archivo de salida
        config:      Diccionario de configuración (ver get_default_config)
        audio_map:   Mapeo de audio (ej. "0:1" para el primer audio en español)
        extra_vf:    Filtro de video extra (ej. "subtitles=...")

    Returns:
        Lista con el comando FFmpeg listo para usar con asyncio.create_subprocess_exec
    """
    quality = config.get("quality", "original")
    vcodec_key = config.get("vcodec", "h264")
    acodec_key = config.get("acodec", "aac")

    q = QUALITY_PRESETS.get(quality, QUALITY_PRESETS["original"])
    vc = VIDEO_CODECS.get(vcodec_key, VIDEO_CODECS["h264"])
    ac = AUDIO_CODECS.get(acodec_key, AUDIO_CODECS["aac"])

    cmd = ["ffmpeg", "-y", "-i", input_path]

    # ─── MAPEO DE STREAMS ───
    if audio_map:
        cmd += ["-map", "0:v:0", "-map", audio_map]
    else:
        cmd += ["-map", "0"]

    # ─── SUBTÍTULOS EXTERNOS / MARCA DE AGUA ───
    # Si el usuario tiene un .ass de marca de agua activo, se añade
    wm_path = config.get("wm_ass_path")
    spam_wm = config.get("spam_wm", "No") == "Sí"
    use_wm = bool(spam_wm and wm_path and os.path.exists(wm_path))

    vf_parts = []
    if use_wm:
        # El filtro "ass" aplica el archivo .ass en cualquier parte del video
        abs_wm = os.path.abspath(wm_path).replace("\\", "/").replace(":", "\\:")
        vf_parts.append(f"ass='{abs_wm}'")
    if extra_vf:
        vf_parts.append(extra_vf)

    # ─── CÓDEC DE VIDEO ───
    if vc["codec"] == "copy" and not vf_parts:
        # Si el usuario pidió "copiar" y no hay filtros, no se recodifica
        cmd += ["-c:v", "copy"]
    else:
        cmd += ["-c:v", vc["codec"]]
        if vc["codec"] != "copy":
            # Ajustes de calidad solo si NO es copy
            if vcodec_key == "h265":
                cmd += ["-crf", q["crf"], "-preset", q["preset"]]
                # Compatibilidad H.265 con navegadores
                cmd += ["-tag:v", "hvc1"]
            else:
                cmd += ["-crf", q["crf"], "-preset", q["preset"]]
                # Compatibilidad con reproductores
                cmd += ["-pix_fmt", "yuv420p"]

        if vf_parts:
            cmd += ["-vf", ",".join(vf_parts)]

    # ─── CÓDEC DE AUDIO ───
    if ac["codec"] == "copy":
        cmd += ["-c:a", "copy"]
    else:
        cmd += ["-c:a", ac["codec"]]
        if ac["bitrate"]:
            cmd += ["-b:a", ac["bitrate"]]

    # ─── FLAGS FINALES ───
    if output_path.lower().endswith(".mp4"):
        cmd += ["-movflags", "+faststart"]

    cmd.append(output_path)
    return cmd
