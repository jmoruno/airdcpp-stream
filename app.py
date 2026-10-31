"""Addon de Stremio/Nuvio que reproduce desde AirDC++ mientras se descarga.

1. Busca a traves del bridge Torznab (titulos en espanol, mismo filtro que Radarr/Sonarr).
2. Muestra solo ficheros de video sueltos (no carpetas ni RAR).
3. Al reproducir, pide la descarga al bridge (categoria propia) y sirve el fichero
   temporal de AirDC++ (.dctmp) a medida que llegan los bytes, con soporte de Range.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = os.environ["TOKEN"]
PUBLIC_URL = os.environ["PUBLIC_URL"].rstrip("/")
PORT = int(os.environ.get("PORT", "7011"))

BRIDGES = {
    "movie": {
        "url": os.environ["BRIDGE_MOVIES_URL"].rstrip("/"),
        "save_path": os.environ.get("BRIDGE_MOVIES_SAVE_PATH", "/Downloads").rstrip("/"),
        "cat": "2000",
    },
    "series": {
        "url": os.environ["BRIDGE_SERIES_URL"].rstrip("/"),
        "save_path": os.environ.get("BRIDGE_SERIES_SAVE_PATH", "/DownloadsSeries").rstrip("/"),
        "cat": "5000",
    },
}
BRIDGE_API_KEY = os.environ["BRIDGE_API_KEY"]
BRIDGE_USER = os.environ["BRIDGE_USERNAME"]
BRIDGE_PASS = os.environ["BRIDGE_PASSWORD"]
CATEGORY = os.environ.get("BRIDGE_CATEGORY", "stremio")

AIRDCPP_URL = os.environ["AIRDCPP_URL"].rstrip("/")
AIRDCPP_AUTH = "Basic " + base64.b64encode(
    f"{os.environ['AIRDCPP_USER']}:{os.environ['AIRDCPP_PASS']}".encode()
).decode()

# Biblioteca: Radarr/Sonarr saben que ficheros tienes y donde (opcional)
RADARR = (os.environ.get("RADARR_URL", "").rstrip("/"), os.environ.get("RADARR_API_KEY", ""))
SONARR = (os.environ.get("SONARR_URL", "").rstrip("/"), os.environ.get("SONARR_API_KEY", ""))
# Rutas de Radarr/Sonarr -> rutas dentro de este contenedor: "/video=/biblioteca/peliculas;/tv=/biblioteca/series"
PATH_MAP = [tuple(x.split("=", 1)) for x in os.environ.get("PATH_MAP", "").split(";") if "=" in x]
# Al reproducir algo que Radarr/Sonarr no conocen, darlo de alta (sin buscar ni descargar)
REGISTER_IN_ARR = os.environ.get("REGISTER_IN_ARR", "true").lower() == "true"
RADARR_PROFILE = os.environ.get("RADARR_PROFILE", "")
SONARR_PROFILE = os.environ.get("SONARR_PROFILE", "")

# Idioma de los textos que se ven en Stremio/Nuvio: "es" (castellano) o "en" (ingles)
LANGUAGE = "en" if os.environ.get("LANGUAGE", "es").lower().startswith("en") else "es"
SPANISH_ONLY = (os.environ.get("SPANISH_ONLY") or ("true" if LANGUAGE == "es" else "false")).lower() == "true"
MAX_RESULTS = int(os.environ.get("MAX_RESULTS", "15"))
SEARCH_WAIT = float(os.environ.get("SEARCH_WAIT", "15"))
PREFETCH_EPISODES = int(os.environ.get("PREFETCH_EPISODES", "2"))
START_WAIT = float(os.environ.get("START_WAIT", "150"))
START_BUFFER = int(os.environ.get("START_BUFFER_MB", "4")) * 1024 * 1024
STALL_WAIT = float(os.environ.get("STALL_WAIT", "60"))
MAX_WAIT = float(os.environ.get("MAX_WAIT", "1800"))
# Cierra los ficheros que nadie lee desde hace este tiempo (libera el espacio si FileBot ya los movio)
IDLE_CLOSE = float(os.environ.get("IDLE_CLOSE_MINUTES", "120")) * 60
SAFETY_MARGIN = 1024 * 1024

VIDEO_EXT = (".mkv", ".mp4", ".avi", ".m4v", ".mov", ".ts", ".wmv")
SPANISH_RE = re.compile(
    r"\b(castellano|spanish|espa[ñn]ol|esp|spa|es|cast|dual|multi|temporada|capitulo|cap)\b", re.I
)
RES_RE = re.compile(r"\b(2160p|4k|uhd|1080p|720p|576p|480p)\b", re.I)
RES_RANK = {"2160p": 4, "4k": 4, "uhd": 4, "1080p": 3, "720p": 2, "576p": 1, "480p": 1}
TORZNAB = "{http://torznab.com/schemas/2015/feed}"

TEXTS = {
    "es": {
        "description": "Reproduce desde tus hubs de AirDC++ mientras se descarga.",
        "res_folder": "según la carpeta",
        "still_searching": "🔄 Sigue buscando en tus hubs… ({n} encontrado(s) hasta ahora)\nVuelve a abrir para ver más",
        "no_results_spanish": "Sin ficheros sueltos en español en tus hubs",
        "no_results": "Sin ficheros sueltos en tus hubs",
        "library": "📁 Biblioteca\n✅ Ya lo tienes",
        "instant": "▶️ Reproducción inmediata",
        "downloaded": "✅ Ya descargado: reproducción inmediata",
        "gone": "El fichero ya no está en la biblioteca",
        "bridge_failed": "el bridge no pudo iniciar la descarga (HTTP {code})",
        "not_created": "AirDC++ no ha creado la descarga",
    },
    "en": {
        "description": "Streams from your AirDC++ hubs while downloading.",
        "res_folder": "from folder name",
        "still_searching": "🔄 Still searching your hubs… ({n} found so far)\nOpen again to see more",
        "no_results_spanish": "No Spanish single files in your hubs",
        "no_results": "No single files in your hubs",
        "library": "📁 Library\n✅ Already in your library",
        "instant": "▶️ Instant playback",
        "downloaded": "✅ Already downloaded: instant playback",
        "gone": "The file is no longer in the library",
        "bridge_failed": "the bridge could not start the download (HTTP {code})",
        "not_created": "AirDC++ did not create the download",
    },
}[LANGUAGE]

MANIFEST = {
    "id": "local.airdcpp.stream",
    "version": "1.0.0",
    "name": "AirDC++",
    "description": TEXTS["description"],
    "resources": ["stream"],
    "types": ["movie", "series"],
    "idPrefixes": ["tt"],
    "catalogs": [],
}


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def http(method, url, headers=None, data=None, timeout=90):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# ------------------------------------------------------------------ busqueda

def human(size):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit not in ("B", "KB") else f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


CINEMETA_URL = os.environ.get("CINEMETA_URL", "https://v3-cinemeta.strem.io").rstrip("/")
_episode_lists = {}
_episode_lock = threading.Lock()


def absolute_episode(imdb_id, season, episode):
    """Numero absoluto del capitulo segun la lista de Cinemeta (T4 E14 de Dragon Ball GT = 61).

    El anime y muchas series antiguas se comparten asi ("Dragon Ball GT 61"), no como S04E14.
    """
    if not season or not episode:
        return None
    with _episode_lock:
        cached = _episode_lists.get(imdb_id)
    if not cached or time.time() - cached[0] > 86400:
        try:
            meta = json.loads(http("GET", f"{CINEMETA_URL}/meta/series/{imdb_id}.json", timeout=20))
            videos = (meta.get("meta") or {}).get("videos") or []
            pairs = sorted({(int(v["season"]), int(v["episode"])) for v in videos
                            if v.get("season") and v.get("episode") and int(v["season"]) > 0})
        except Exception as exc:  # noqa: BLE001
            log(f"No se pudo leer la lista de capitulos de {imdb_id}: {exc}")
            pairs = None
        # Si Cinemeta falla se reintenta a los 10 minutos en vez de esperar un dia
        cached = (time.time(), pairs or []) if pairs is not None else (time.time() - 86400 + 600, [])
        with _episode_lock:
            _episode_lists[imdb_id] = cached
    try:
        return cached[1].index((season, episode)) + 1
    except ValueError:
        return episode if season == 1 else None


def search_bridge(kind, imdb_id, season=None, episode=None, partial=False):
    bridge = BRIDGES[kind]
    params = {"apikey": BRIDGE_API_KEY, "cat": bridge["cat"], "imdbid": imdb_id}
    if kind == "movie":
        params["t"] = "movie"
    else:
        params.update(t="tvsearch", season=season, ep=episode)
        absolute = absolute_episode(imdb_id, season, episode)
        if absolute:
            params["absolute"] = absolute
    # Sin prisa: la busqueda sigue en segundo plano y el reproductor muestra "Buscando…" mientras
    if partial:
        # Solo lo encontrado hasta ahora por la busqueda en curso (no lanza otra)
        params["partial"] = "true"
    raw = http("GET", f"{bridge['url']}/torznab/api?{urllib.parse.urlencode(params)}", timeout=15 if partial else 600)
    results = []
    for item in ET.fromstring(raw).iter("item"):
        title = item.findtext("title") or ""
        size = int(item.findtext("size") or 0)
        attrs = {}
        languages = []
        for attr in item.iter(f"{TORZNAB}attr"):
            if attr.get("name") == "language":
                languages.append(attr.get("value"))
            else:
                attrs[attr.get("name")] = attr.get("value")
        release_id = attrs.get("infohash")
        if not release_id or size <= 0 or not title.lower().endswith(VIDEO_EXT):
            continue
        spanish = "Spanish" in languages or bool(SPANISH_RE.search(title))
        if SPANISH_ONLY and not spanish:
            continue
        res = RES_RE.search(title)
        results.append({
            "id": release_id, "title": title, "size": size, "spanish": spanish,
            # Si el nombre no la dice, el bridge la saca de la carpeta de AirDC++ donde esta el fichero
            "res": res.group(1).lower() if res else (attrs.get("resolution") or ""),
            "res_folder": not res and attrs.get("resolutionsource") == "carpeta",
            "peers": int(attrs.get("seeders") or 1),
            "languages": languages,
        })
    results.sort(key=lambda r: (not r["spanish"], -RES_RANK.get(r["res"], 0), -r["size"]))
    return results[:MAX_RESULTS]


def to_stream(kind, result, imdb_id):
    quoted = urllib.parse.quote(result["title"], safe="")
    url = f"{PUBLIC_URL}/{TOKEN}/play/{kind}/{result['id']}/{result['size']}/{imdb_id}/{quoted}"
    flag = " 🇪🇸" if result["spanish"] else ""
    info = f"💾 {human(result['size'])}   👥 {result['peers']}"
    if result["languages"]:
        info += "   🗣 " + ", ".join(result["languages"])
    if result.get("res_folder"):
        info += f"\n📁 {result['res']} {TEXTS['res_folder']}"
    return {
        "name": f"AirDC++\n{result['res'] or '?'}{flag}",
        "title": f"{result['title']}\n{info}",
        "description": f"{result['title']}\n{info}",
        "url": url,
        "behaviorHints": {
            "notWebReady": True,
            "filename": result["title"],
            "videoSize": result["size"],
            "bingeGroup": f"airdcpp-{result['res']}",
        },
    }


_search_cache = {}
_search_lock = threading.Lock()


def cached_search(kind, imdb_id, season=None, episode=None, wait=True):
    key = (kind, imdb_id, season, episode)
    with _search_lock:
        entry = _search_cache.get(key)
        if entry and entry["done"].is_set() and time.time() - entry["time"] > 600:
            entry = None
        if not entry:
            entry = {"done": threading.Event(), "time": time.time(), "streams": None, "error": None}
            _search_cache[key] = entry

            label = f"{imdb_id}" + (f" S{season:02d}E{episode:02d}" if season is not None else "")
            log(f"Buscando {label}{' (por adelantado)' if not wait else ''}…")

            def worker():
                started = time.monotonic()
                try:
                    entry["streams"] = [to_stream(kind, r, imdb_id) for r in search_bridge(kind, imdb_id, season, episode)]
                    log(f"Búsqueda {label} terminada en {time.monotonic() - started:.0f} s: "
                        f"{len(entry['streams'])} resultado(s)")
                except Exception as exc:  # noqa: BLE001
                    entry["error"] = str(exc)
                    log(f"ERROR busqueda {key}: {exc}")
                finally:
                    entry["time"] = time.time()
                    entry["done"].set()

            threading.Thread(target=worker, daemon=True).start()
    if not wait:
        return None, True
    if not entry["done"].wait(SEARCH_WAIT):
        # Se ensena lo encontrado hasta ahora y un aviso de que sigue buscando
        try:
            found = [to_stream(kind, r, imdb_id) for r in search_bridge(kind, imdb_id, season, episode, partial=True)]
        except Exception as exc:  # noqa: BLE001
            log(f"No se pudieron leer los resultados parciales: {exc}")
            found = []
        notice = {"name": "AirDC++",
                  "title": TEXTS["still_searching"].format(n=len(found)),
                  "externalUrl": PUBLIC_URL}
        return [notice] + found, True
    if entry["error"]:
        with _search_lock:
            _search_cache.pop(key, None)
        return [{"name": "AirDC++", "title": f"⚠️ {entry['error'][:120]}", "externalUrl": PUBLIC_URL}], True
    return entry["streams"], False


def prefetch_after(imdb_id, season, episode):
    """Busca los siguientes capitulos cuando termina el que se va a ver, uno detras de otro.

    AirDC++ deja 5 s entre busquedas y las encola: lanzarlas a la vez le quitaba turno
    al capitulo que se esta esperando y acababa en "timed out".
    """
    def run():
        for ahead in range(0, PREFETCH_EPISODES + 1):
            if ahead:
                cached_search("series", imdb_id, season, episode + ahead, wait=False)
            with _search_lock:
                entry = _search_cache.get(("series", imdb_id, season, episode + ahead))
            if entry:
                entry["done"].wait(900)

    if PREFETCH_EPISODES > 0:
        threading.Thread(target=run, daemon=True).start()


# ------------------------------------------------------------------ biblioteca

def arr_get(service, path, params=None):
    base, key = service
    url = f"{base}/api/v3/{path}" + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    return json.loads(http("GET", url, headers={"X-Api-Key": key}, timeout=20))


def arr_post(service, path, body):
    base, key = service
    return json.loads(http("POST", f"{base}/api/v3/{path}", data=json.dumps(body).encode(), timeout=30,
                           headers={"X-Api-Key": key, "Content-Type": "application/json"}) or b"null")


def arr_defaults(service, profile_name):
    profiles = arr_get(service, "qualityprofile")
    match = [p for p in profiles if p["name"].lower() == profile_name.lower()] if profile_name else []
    profile_id = (match or profiles)[0]["id"]
    return profile_id, arr_get(service, "rootfolder")[0]["path"]


_registered = set()


def register_in_arr(kind, imdb_id):
    """Da de alta la pelicula/serie en Radarr/Sonarr sin buscar nada, para que detecten
    el fichero cuando FileBot lo mueva a la biblioteca."""
    if not REGISTER_IN_ARR or (kind, imdb_id) in _registered:
        return
    _registered.add((kind, imdb_id))
    try:
        if kind == "movie" and RADARR[0]:
            lookup = arr_get(RADARR, "movie/lookup/imdb", {"imdbId": imdb_id})
            if arr_get(RADARR, "movie", {"tmdbId": lookup["tmdbId"]}):
                return
            profile_id, root = arr_defaults(RADARR, RADARR_PROFILE)
            lookup.update(qualityProfileId=profile_id, rootFolderPath=root, monitored=False,
                          minimumAvailability="released",
                          addOptions={"searchForMovie": False, "monitor": "none"})
            arr_post(RADARR, "movie", lookup)
            log(f"Registrada en Radarr (sin buscar): {lookup.get('title')} ({lookup.get('year')})")
        elif kind == "series" and SONARR[0]:
            lookup = [r for r in arr_get(SONARR, "series/lookup", {"term": f"imdb:{imdb_id}"}) if r.get("tvdbId")]
            if not lookup or arr_get(SONARR, "series", {"tvdbId": lookup[0]["tvdbId"]}):
                return
            profile_id, root = arr_defaults(SONARR, SONARR_PROFILE)
            series = lookup[0]
            series.update(qualityProfileId=profile_id, rootFolderPath=root, seasonFolder=True, monitored=False,
                          addOptions={"monitor": "none", "searchForMissingEpisodes": False})
            arr_post(SONARR, "series", series)
            log(f"Registrada en Sonarr (sin buscar): {series.get('title')}")
    except Exception as exc:  # noqa: BLE001
        _registered.discard((kind, imdb_id))
        log(f"No se pudo registrar {kind} {imdb_id} en Radarr/Sonarr: {exc}")


def safe_join(root, name):
    """Ruta de `name` dentro de `root`, o None si intenta salirse (../, rutas absolutas...)."""
    base = os.path.realpath(root)
    full = os.path.realpath(os.path.join(base, name))
    return full if full.startswith(base + os.sep) else None


def library_roots():
    return [os.path.realpath(dst) for _, dst in PATH_MAP]


def in_library(path):
    """Ruta real si esta dentro de alguna carpeta de la biblioteca (PATH_MAP), si no None."""
    real = os.path.realpath(path)
    for root in library_roots():
        if real.startswith(root + os.sep):
            return real
    return None


def local_path(path):
    for src, dst in PATH_MAP:
        src = src.rstrip("/")
        if path == src or path.startswith(src + "/"):
            path = dst.rstrip("/") + path[len(src):]
            break
    return path if os.path.isfile(path) else None


def library_file(kind, imdb_id, season=None, episode=None):
    """Devuelve (ruta_local, tamano) si Radarr/Sonarr ya tienen el fichero."""
    try:
        if kind == "movie" and RADARR[0]:
            tmdb_id = arr_get(RADARR, "movie/lookup/imdb", {"imdbId": imdb_id})["tmdbId"]
            for movie in arr_get(RADARR, "movie", {"tmdbId": tmdb_id}):
                movie_file = movie.get("movieFile") or {}
                path = movie_file.get("path") and local_path(movie_file["path"])
                if path:
                    return path, os.path.getsize(path)
        if kind == "series" and SONARR[0]:
            lookup = [r for r in arr_get(SONARR, "series/lookup", {"term": f"imdb:{imdb_id}"}) if r.get("tvdbId")]
            for series in arr_get(SONARR, "series", {"tvdbId": lookup[0]["tvdbId"]}) if lookup else []:
                for ep in arr_get(SONARR, "episode", {"seriesId": series["id"], "seasonNumber": season}):
                    if ep["episodeNumber"] == episode and ep.get("hasFile") and ep.get("episodeFileId"):
                        for ep_file in arr_get(SONARR, "episodefile", {"episodeFileIds": ep["episodeFileId"]}):
                            path = local_path(ep_file.get("path") or "")
                            if path:
                                return path, os.path.getsize(path)
    except Exception as exc:  # noqa: BLE001
        log(f"Biblioteca no disponible ({kind} {imdb_id}): {exc}")
    return None


def sign(value):
    return hmac.new(TOKEN.encode(), value.encode(), hashlib.sha256).hexdigest()[:32]


def library_stream(path, size):
    encoded = base64.urlsafe_b64encode(path.encode()).decode()
    name = os.path.basename(path)
    return {
        "name": TEXTS["library"],
        "title": f"{name}\n💾 {human(size)}   {TEXTS['instant']}",
        "description": f"{name}\n💾 {human(size)}   {TEXTS['instant']}",
        "url": f"{PUBLIC_URL}/{TOKEN}/local/{sign(encoded)}/{encoded}",
        "behaviorHints": {"notWebReady": True, "filename": name, "videoSize": size, "bingeGroup": "airdcpp-local"},
    }


def mark_downloaded(kind, streams):
    """Marca los resultados que ya estan descargados en la carpeta de AirDC++."""
    marked = []
    for stream in streams:
        filename = (stream.get("behaviorHints") or {}).get("filename")
        downloaded = filename and safe_join(BRIDGES[kind]["save_path"], filename)
        if downloaded and os.path.isfile(downloaded):
            stream = dict(stream, name=stream["name"] + " ✅",
                          title=TEXTS["downloaded"] + "\n" + stream["title"],
                          description=TEXTS["downloaded"] + "\n" + stream["title"])
        marked.append(stream)
    return marked


# ------------------------------------------------------------------ MKV

ID_SEGMENT, ID_SEEKHEAD, ID_SEEK, ID_SEEKID, ID_SEEKPOS, ID_CLUSTER = (
    0x18538067, 0x114D9B74, 0x4DBB, 0x53AB, 0x53AC, 0x1F43B675)


def _vint(data, pos, keep_marker):
    first = data[pos]
    length = next((i + 1 for i in range(8) if first & (0x80 >> i)), None)
    if length is None or pos + length > len(data):
        raise ValueError("vint")
    value = first if keep_marker else first & (0xFF >> length)
    for byte in data[pos + 1:pos + length]:
        value = (value << 8) | byte
    unknown = not keep_marker and value == (1 << (7 * length)) - 1
    return value, length, unknown


def _element(data, pos):
    eid, id_len, _ = _vint(data, pos, True)
    size, size_len, unknown = _vint(data, pos + id_len, False)
    return eid, pos + id_len + size_len, size, unknown


def mkv_patches(head, file_size):
    """Anula en el SeekHead las referencias a elementos situados tras los datos de video
    (Cues, Tags... al final del fichero) convirtiendolas en Void del mismo tamano.

    Asi el reproductor no pide el final del MKV para arrancar. Devuelve [(offset, bytes)].
    """
    try:
        if head[:4] != b"\x1a\x45\xdf\xa3":
            return []
        _, data_start, size, _ = _element(head, 0)
        pos = data_start + size
        eid, seg_start, _, _ = _element(head, pos)
        if eid != ID_SEGMENT:
            return []
        seeks, first_cluster, pos = [], None, seg_start
        while pos < len(head):
            eid, data_start, size, unknown = _element(head, pos)
            if eid == ID_CLUSTER:
                first_cluster = pos
                break
            if unknown:
                break
            if eid == ID_SEEKHEAD:
                inner = data_start
                while inner < min(data_start + size, len(head)):
                    sid, sdata, ssize, _ = _element(head, inner)
                    if sid == ID_SEEK:
                        target, field = None, sdata
                        while field < sdata + ssize:
                            fid, fdata, fsize, _ = _element(head, field)
                            if fid == ID_SEEKPOS:
                                target = seg_start + int.from_bytes(head[fdata:fdata + fsize], "big")
                            field = fdata + fsize
                        seeks.append((inner, sdata + ssize - inner, target))
                    inner = sdata + ssize
            pos = data_start + size
        limit = first_cluster if first_cluster is not None else file_size // 2
        patches = []
        for offset, length, target in seeks:
            if target is None or target <= limit:
                continue
            if 2 <= length <= 128:
                patches.append((offset, bytes([0xEC, 0x80 | (length - 2)])))
            elif length >= 10:
                patches.append((offset, b"\xec\x01" + (length - 9).to_bytes(7, "big")))
        return patches
    except (ValueError, IndexError):
        return []


def apply_patches(chunk, position, patches):
    for offset, data in patches:
        start, end = max(offset, position), min(offset + len(data), position + len(chunk))
        if start < end:
            chunk = chunk[:start - position] + data[start - offset:end - offset] + chunk[end - position:]
    return chunk


# ------------------------------------------------------------------ AirDC++

def adc(path):
    return json.loads(http("GET", f"{AIRDCPP_URL}/api/v1/{path}", headers={"Authorization": AIRDCPP_AUTH}, timeout=30))


_bridge_sids = {}


def bridge_sid(kind, renew=False):
    """Inicia sesion en la API qBittorrent del bridge y guarda la cookie SID."""
    if renew or kind not in _bridge_sids:
        body = urllib.parse.urlencode({"username": BRIDGE_USER, "password": BRIDGE_PASS}).encode()
        req = urllib.request.Request(f"{BRIDGES[kind]['url']}/api/v2/auth/login", data=body, method="POST",
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            cookie = resp.headers.get("Set-Cookie") or ""
        match = re.search(r"SID=([^;]+)", cookie)
        if not match:
            raise RuntimeError("login en el bridge rechazado")
        _bridge_sids[kind] = match.group(1)
    return _bridge_sids[kind]


def bridge_add(kind, release_id):
    bridge = BRIDGES[kind]
    body = urllib.parse.urlencode({"urls": f"magnet:?xt=urn:btih:{release_id}", "category": CATEGORY}).encode()
    try:
        for attempt in range(2):
            try:
                http("POST", f"{bridge['url']}/api/v2/torrents/add", data=body, timeout=120, headers={
                    "Cookie": f"SID={bridge_sid(kind, renew=attempt > 0)}",
                    "Content-Type": "application/x-www-form-urlencoded"})
                return
            except urllib.error.HTTPError as exc:
                if exc.code != 403 or attempt:
                    raise
    except urllib.error.HTTPError as exc:
        raise RuntimeError(TEXTS["bridge_failed"].format(code=exc.code)) from exc


class Session:
    """Estado de un fichero en reproduccion (compartido por todas las conexiones del reproductor)."""

    def __init__(self, kind, release_id, size, name):
        self.kind, self.release_id, self.size, self.name = kind, release_id, size, name
        self.target = safe_join(BRIDGES[kind]["save_path"], name)
        if self.target is None:
            raise ValueError("nombre de fichero no valido")
        self.lock = threading.Lock()
        self.started = False
        self.file_id = None
        self.fd = None
        self.available = 0
        self.complete = False
        self.last_poll = 0.0
        self.error = None
        self.patches = None
        self.active = 0
        self.last_used = time.monotonic()

    def find_file(self):
        for bundle in adc("queue/bundles/0/5000"):
            target = str(bundle.get("target") or "").rstrip("/")
            if target == self.target or bundle.get("name") == self.name:
                files = adc(f"queue/bundles/{bundle['id']}/files/0/50")
                for f in files:
                    if f.get("name") == self.name or str(f.get("target")) == self.target:
                        self.target = f.get("target") or self.target
                        return f
        return None

    def start(self):
        with self.lock:
            if self.started:
                return
            queued = self.find_file()
            if not queued and not os.path.exists(self.target):
                log(f"Iniciando descarga {self.name}")
                bridge_add(self.kind, self.release_id)
                deadline = time.monotonic() + 30
                while not queued and time.monotonic() < deadline:
                    time.sleep(1)
                    queued = self.find_file()
                if not queued:
                    raise RuntimeError(TEXTS["not_created"])
            if queued:
                self.file_id = queued["id"]
            else:
                self.complete = True
                self.available = self.size
            self.started = True

    def refresh(self):
        """Actualiza los bytes contiguos disponibles desde el inicio."""
        with self.lock:
            if self.complete or time.monotonic() - self.last_poll < 1.0:
                return
            self.last_poll = time.monotonic()
            try:
                info = adc(f"queue/files/{self.file_id}")
                if int(float(info.get("downloaded_bytes", 0))) >= self.size or (info.get("status") or {}).get("completed"):
                    self.complete = True
                    self.available = self.size
                    return
                seg = adc(f"queue/files/{self.file_id}/segments")
            except urllib.error.HTTPError as exc:
                if exc.code == 404 and os.path.exists(self.target):
                    self.complete = True
                    self.available = self.size
                return
            parts = sorted((s["start"], s["start"] + s["size"]) for s in seg.get("done", []) + seg.get("running_progress", []))
            prefix = 0
            for begin, end in parts:
                if begin > prefix:
                    break
                prefix = max(prefix, end)
            self.available = max(self.available, prefix - SAFETY_MARGIN)

    def open(self):
        with self.lock:
            if self.fd is None:
                for path in (self.target + ".dctmp", self.target):
                    if os.path.exists(path):
                        self.fd = os.open(path, os.O_RDONLY)
                        break
            return self.fd

    def header_patches(self):
        """Calcula (una vez) los parches del SeekHead mientras el fichero no este completo."""
        with self.lock:
            if self.patches is None and not self.name.lower().endswith(".mkv"):
                self.patches = []
            if self.patches is None and self.fd is not None and self.available > 0:
                head = os.pread(self.fd, min(1024 * 1024, self.available, self.size), 0)
                self.patches = mkv_patches(head, self.size)
                log(f"MKV {self.name}: {len(self.patches)} referencia(s) al final anuladas en la cabecera")
            return self.patches or []

    def wait_for(self, position, timeout):
        """Espera a tener datos en `position` mientras la descarga siga avanzando.

        Solo se rinde si no llega ningun byte nuevo en `timeout` segundos (o tras MAX_WAIT).
        """
        start = last_change = time.monotonic()
        last_available = self.available
        while time.monotonic() - start < MAX_WAIT:
            self.refresh()
            if (self.available > position or self.complete) and self.open() is not None:
                return True
            if self.available != last_available:
                last_available, last_change = self.available, time.monotonic()
            elif time.monotonic() - last_change > timeout:
                return False
            time.sleep(1)
        return False


_sessions = {}
_sessions_lock = threading.Lock()


def get_session(kind, release_id, size, name):
    with _sessions_lock:
        session = _sessions.get(release_id)
        if not session:
            session = _sessions[release_id] = Session(kind, release_id, size, name)
        session.last_used = time.monotonic()
        return session


def close_idle_sessions():
    """Cierra los ficheros sin lectores desde hace IDLE_CLOSE segundos."""
    while True:
        time.sleep(max(1.0, min(60.0, IDLE_CLOSE / 2)))
        now = time.monotonic()
        with _sessions_lock:
            for release_id, session in list(_sessions.items()):
                if session.active == 0 and now - session.last_used > IDLE_CLOSE:
                    with session.lock:
                        if session.fd is not None:
                            os.close(session.fd)
                            session.fd = None
                    del _sessions[release_id]
                    log(f"Cerrado {session.name} (sin uso desde hace {IDLE_CLOSE / 60:.0f} min)")


# ------------------------------------------------------------------ HTTP

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def head(self, code, ctype, length, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Content-Length", str(length))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def send_json(self, obj):
        data = json.dumps(obj, ensure_ascii=False).encode()
        try:
            self.head(200, "application/json; charset=utf-8", len(data), {"Cache-Control": "no-store"})
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            log("El cliente se cansó de esperar; los resultados quedan en caché para la próxima vez")

    def text(self, code, msg):
        data = msg.encode()
        self.head(code, "text/plain; charset=utf-8", len(data))
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.head(204, "text/plain", 0)

    def do_HEAD(self):
        self.route(head_only=True)

    def do_GET(self):
        self.route(head_only=False)

    def route(self, head_only):
        parts = [urllib.parse.unquote(p) for p in urllib.parse.urlparse(self.path).path.split("/") if p]
        if parts == ["health"]:
            return self.send_json({"status": "ok"})
        if not parts or parts[0] != TOKEN:
            return self.text(404, "Not found")
        parts = parts[1:]
        if parts == ["manifest.json"]:
            return self.send_json(MANIFEST)
        if len(parts) == 3 and parts[0] == "stream":
            kind, item_id = parts[1], parts[2].removesuffix(".json")
            if kind == "movie":
                local = library_file("movie", item_id)
                streams, partial = cached_search("movie", item_id)
                streams = mark_downloaded("movie", streams)
            else:
                imdb_id, season, episode = item_id.split(":")[:3]
                local = library_file("series", imdb_id, int(season), int(episode))
                streams, partial = cached_search("series", imdb_id, int(season), int(episode))
                streams = mark_downloaded("series", streams)
                # Adelanta la busqueda de los siguientes capitulos para que esten listos al llegar
                prefetch_after(imdb_id, int(season), int(episode))
            if local:
                streams = [library_stream(*local)] + [s for s in streams if s.get("url")]
            if not streams:
                streams, partial = [{"name": "AirDC++", "title": TEXTS["no_results_spanish" if SPANISH_ONLY else "no_results"],
                                     "externalUrl": PUBLIC_URL}], True
            log(f"stream {kind} {item_id}: {len(streams)} resultado(s){' (parcial)' if partial else ''}")
            return self.send_json({"streams": streams, "cacheMaxAge": 0 if partial else 600})
        if len(parts) == 3 and parts[0] == "local":
            return self.play_local(parts[1], parts[2], head_only)
        if len(parts) == 6 and parts[0] == "play":
            threading.Thread(target=register_in_arr, args=(parts[1], parts[4]), daemon=True).start()
            return self.play(parts[1], parts[2], int(parts[3]), parts[5], head_only)
        if len(parts) == 5 and parts[0] == "play":
            return self.play(parts[1], parts[2], int(parts[3]), parts[4], head_only)
        return self.text(404, "Not found")

    def parse_range(self, size):
        start, end, ranged = 0, size - 1, False
        match = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if match:
            ranged = True
            if match.group(1):
                start = int(match.group(1))
                end = int(match.group(2)) if match.group(2) else size - 1
            elif match.group(2):
                start = max(0, size - int(match.group(2)))
        return start, min(end, size - 1), ranged

    def play_local(self, signature, encoded, head_only):
        """Sirve un fichero de la biblioteca (ruta firmada, no se puede pedir cualquier fichero)."""
        if not hmac.compare_digest(signature, sign(encoded)):
            return self.text(403, "Forbidden")
        path = in_library(base64.urlsafe_b64decode(encoded.encode()).decode())
        if path is None:
            return self.text(403, "Forbidden")
        if not os.path.isfile(path):
            return self.text(404, TEXTS["gone"])
        size = os.path.getsize(path)
        ctype = "video/mp4" if path.lower().endswith((".mp4", ".m4v")) else "video/x-matroska"
        start, end, ranged = self.parse_range(size)
        if start >= size:
            return self.head(416, ctype, 0, {"Content-Range": f"bytes */{size}"})
        headers = {"Accept-Ranges": "bytes", "Cache-Control": "no-store"}
        if ranged:
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        self.head(206 if ranged else 200, ctype, end - start + 1, headers)
        if head_only:
            return None
        try:
            with open(path, "rb") as handle:
                handle.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    chunk = handle.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            # El reproductor ha cerrado la conexion (pausa, salto o salida): no es un error
            pass
        return None

    def play(self, kind, release_id, size, name, head_only):
        if kind not in BRIDGES or not re.fullmatch(r"[A-Za-z0-9]{1,64}", release_id) \
                or name != os.path.basename(name) or name in ("", ".", "..") or "\x00" in name:
            return self.text(400, "Bad request")
        ctype = "video/mp4" if name.lower().endswith((".mp4", ".m4v")) else "video/x-matroska"
        start, end = 0, size - 1
        ranged = False
        match = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if match:
            ranged = True
            if match.group(1):
                start = int(match.group(1))
                end = int(match.group(2)) if match.group(2) else size - 1
            elif match.group(2):
                start = max(0, size - int(match.group(2)))
        end = min(end, size - 1)
        if start >= size:
            return self.head(416, ctype, 0, {"Content-Range": f"bytes */{size}"})

        session = get_session(kind, release_id, size, name)
        try:
            session.start()
        except Exception as exc:  # noqa: BLE001
            log(f"ERROR al iniciar {name}: {exc}")
            return self.text(502, str(exc))

        log(f"play {'HEAD' if head_only else 'GET'} {name} rango={start}-{end} disponible={session.available} completo={session.complete}")
        if not head_only:
            # Espera el buffer inicial o, en un salto (p. ej. el indice al final del MKV),
            # a que la descarga llegue a esa posicion mientras siga avanzando.
            needed = start + (START_BUFFER if start == 0 else 0)
            if not session.wait_for(min(needed, size - 1), START_WAIT if session.available == 0 else STALL_WAIT):
                log(f"Sin datos en la posicion {start} de {name} (disponible {session.available})")
                return self.head(416, ctype, 0, {"Content-Range": f"bytes */{size}"})

        headers = {"Accept-Ranges": "bytes", "Cache-Control": "no-store"}
        if ranged:
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        log(f"sirviendo {name} desde {start} (disponible {session.available})")
        self.head(206 if ranged else 200, ctype, end - start + 1, headers)
        if head_only:
            return None

        patches = session.header_patches() if not session.complete else []
        position, stalled = start, time.monotonic()
        with session.lock:
            session.active += 1
        try:
            while position <= end:
                session.refresh()
                limit = size if session.complete else session.available
                if position >= limit:
                    if time.monotonic() - stalled > 300:
                        log(f"Descarga parada en {position} de {name}")
                        break
                    time.sleep(1)
                    continue
                chunk = os.pread(session.open(), min(256 * 1024, limit - position, end - position + 1), position)
                if not chunk:
                    time.sleep(1)
                    continue
                if patches:
                    chunk = apply_patches(chunk, position, patches)
                self.wfile.write(chunk)
                position += len(chunk)
                stalled = session.last_used = time.monotonic()
        except (BrokenPipeError, ConnectionResetError):
            # El reproductor ha cerrado la conexion (pausa, salto o salida): no es un error
            pass
        finally:
            with session.lock:
                session.active -= 1
                session.last_used = time.monotonic()
        return None


if __name__ == "__main__":
    log(f"Addon en {PUBLIC_URL}/{TOKEN}/manifest.json")
    threading.Thread(target=close_idle_sessions, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
