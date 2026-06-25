import json
import re
import time
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from local_fallback_images import product_fallback_image


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "BioMimetix product image connector/0.1"
CACHE_PATH = Path(__file__).parent / "data" / "product_image_cache.json"
CACHE_TTL_SECONDS = 60 * 60 * 24 * 14
CACHE_VERSION = "v1"


def product_image_search(product, hint=""):
    product = (product or "").strip()
    hint = (hint or "").strip()
    if not product:
        return _empty_response(product)

    # Bypass cache when a hint is provided so users always get a fresh search
    if hint:
        return _with_local_fallback(_commons_product_image(product, hint=hint), product, hint)

    cache = _load_cache()
    cache_key = f"{CACHE_VERSION}:commons:{product.lower()}"
    now = int(time.time())
    cached = cache.get(cache_key)
    if cached and now - cached.get("fetched_at", 0) < CACHE_TTL_SECONDS:
        return _with_local_fallback(cached.get("result", _empty_response(product)), product, hint)

    result = _with_local_fallback(_commons_product_image(product), product, hint)
    cache[cache_key] = {"fetched_at": now, "result": result}
    _save_cache(cache)
    return result


def _with_local_fallback(result, product, hint=""):
    if result.get("image_url"):
        return result
    return product_fallback_image(product, hint) or result


def _commons_product_image(product, hint=""):
    candidates = []
    for query in _search_queries(product, hint=hint):
        candidates.extend(_commons_search(query))
        if len(candidates) >= 8:
            break

    ranked = sorted(candidates, key=lambda item: _score_candidate(hint or product, item), reverse=True)
    if not ranked:
        return _empty_response(product)

    best = ranked[0]
    image = best.get("imageinfo", [{}])[0]
    metadata = image.get("extmetadata") or {}
    title = best.get("title", "").removeprefix("File:")
    license_name = _metadata_value(metadata, "LicenseShortName") or _metadata_value(metadata, "UsageTerms")
    attribution = _clean_text(_metadata_value(metadata, "Artist") or _metadata_value(metadata, "Credit"))

    return {
        "image_url": image.get("thumburl") or image.get("url") or "",
        "source_url": image.get("descriptionurl") or "",
        "source": "Wikimedia Commons",
        "title": _clean_text(_metadata_value(metadata, "ObjectName")) or title,
        "attribution": attribution,
        "license": _clean_text(license_name),
        "search_url": f"https://commons.wikimedia.org/wiki/Special:MediaSearch?{urlencode({'type': 'image', 'search': product})}",
    }


def _search_queries(product, hint=""):
    normalized = re.sub(r"\s+", " ", product).strip()
    if hint:
        h = re.sub(r"\s+", " ", hint).strip()
        return [
            f'"{h}" filetype:bitmap',
            f"{h} filetype:bitmap",
            f'"{normalized}" filetype:bitmap',
            f"{normalized} filetype:bitmap",
        ]
    queries = [
        f'"{normalized}" filetype:bitmap',
        f"{normalized} product filetype:bitmap",
        f"{normalized} object filetype:bitmap",
        f"{normalized} filetype:bitmap",
    ]
    if "drone" in normalized.lower() and "blade" in normalized.lower():
        queries.insert(1, "drone propeller filetype:bitmap")
    if "shoe" in normalized.lower():
        queries.insert(1, f"{normalized} footwear filetype:bitmap")
    return queries


def _commons_search(search):
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": search,
        "gsrnamespace": 6,
        "gsrlimit": 8,
        "prop": "imageinfo",
        "iiprop": "url|mime|size|extmetadata",
        "iiurlwidth": 900,
        "format": "json",
    }
    data = _fetch_json(f"{COMMONS_API}?{urlencode(params)}")
    pages = (data.get("query") or {}).get("pages") or {}
    return [page for page in pages.values() if _usable_image(page)]


def _usable_image(page):
    image = (page.get("imageinfo") or [{}])[0]
    mime = image.get("mime", "")
    width = int(image.get("width") or 0)
    height = int(image.get("height") or 0)
    title = page.get("title", "").lower()
    if not mime.startswith("image/") or mime in {"image/svg+xml", "image/gif"}:
        return False
    if width < 240 or height < 180:
        return False
    return not any(term in title for term in ["logo", "icon", "map", "diagram", "chart"])


def _score_candidate(product, item):
    title = item.get("title", "").lower()
    words = [word for word in re.findall(r"[a-z0-9]+", product.lower()) if len(word) > 2]
    score = 0
    for word in words:
        if word in title:
            score += 8
    if product.lower() in title:
        score += 20
    if any(term in title for term in ["product", "object", "front", "studio"]):
        score += 3
    if any(term in title for term in ["person", "athlete", "portrait", "event"]):
        score -= 6
    image = (item.get("imageinfo") or [{}])[0]
    score += min(int(image.get("width") or 0), 1600) / 1600
    return score


def _fetch_json(url):
    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return {}


def _metadata_value(metadata, key):
    value = metadata.get(key)
    if isinstance(value, dict):
        return value.get("value") or ""
    return ""


def _clean_text(value):
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(value))
    text = unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _empty_response(product):
    return {
        "image_url": "",
        "source_url": "",
        "source": "Wikimedia Commons",
        "title": product,
        "attribution": "",
        "license": "",
        "search_url": f"https://commons.wikimedia.org/wiki/Special:MediaSearch?{urlencode({'type': 'image', 'search': product})}",
    }


def _load_cache():
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache):
    CACHE_PATH.parent.mkdir(exist_ok=True)
    tmp_path = CACHE_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(CACHE_PATH)
