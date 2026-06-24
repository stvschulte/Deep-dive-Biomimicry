import json
import re
import time
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ASKNATURE_BASE = "https://asknature.org"
ASKNATURE_API = f"{ASKNATURE_BASE}/wp-json/wp/v2"
USER_AGENT = "BioMimetix AskNature metadata connector/0.1"
CACHE_PATH = Path(__file__).parent / "data" / "asknature_cache.json"
CACHE_TTL_SECONDS = 60 * 60 * 24 * 7
CACHE_VERSION = "v2"

USAGE_NOTE = (
    "AskNature metadata cache. Keep attribution and link users to the source; "
    "do not use cached records for AI training or republish full AskNature materials "
    "without permission from the Biomimicry Institute."
)


def asknature_search(query, limit=5):
    query = (query or "").strip()
    if not query:
        return []

    limit = max(1, min(int(limit or 5), 10))
    cache = _load_cache()
    cache_key = f"{CACHE_VERSION}:search:{query.lower()}:{limit}"
    cached = cache.get(cache_key)
    now = int(time.time())
    if cached and now - cached.get("fetched_at", 0) < CACHE_TTL_SECONDS:
        return cached.get("results", [])

    params = urlencode({"search": query, "subtype": "strategy", "per_page": limit})
    search_results = _fetch_json(f"{ASKNATURE_API}/search?{params}") or []
    records = []
    for item in search_results[:limit]:
        record = _record_from_search_item(item, cache)
        if record:
            records.append(record)

    cache[cache_key] = {"fetched_at": now, "results": records}
    _save_cache(cache)
    return records


def asknature_biomimicry_options(function, product="", limit=5):
    records = asknature_search(function, limit)
    options = []
    for record in records:
        organism = record.get("organism") or "AskNature strategy"
        functions = ", ".join(record.get("functions") or [])
        context = f" Related AskNature functions: {functions}." if functions else ""
        product_context = f" for {product}" if product else ""
        options.append(
            {
                "organism": organism,
                "rationale": (
                    f"{record.get('title')} is an AskNature biological strategy relevant to "
                    f"{function}{product_context}.{context}"
                ),
                "source": "AskNature",
                "source_url": record.get("url"),
                "asknature_id": record.get("id"),
                "image_url": record.get("image_url"),
                "image_attribution": record.get("image_attribution"),
            }
        )
    return options


def _record_from_search_item(item, cache):
    item_id = item.get("id")
    if not item_id:
        return None

    detail_key = f"{CACHE_VERSION}:strategy:{item_id}"
    now = int(time.time())
    detail = cache.get(detail_key)
    if not detail or now - detail.get("fetched_at", 0) >= CACHE_TTL_SECONDS:
        fetched = _fetch_json(f"{ASKNATURE_API}/strategy/{item_id}?_embed=1")
        if not fetched:
            return _fallback_record(item)
        detail = {"fetched_at": now, "data": fetched}
        cache[detail_key] = detail

    data = detail.get("data") or {}
    link = data.get("link") or item.get("url")
    page_meta = _cached_page_metadata(item_id, link, cache)
    title = _clean_text((data.get("title") or {}).get("rendered")) or item.get("title", "")
    terms = _terms_by_taxonomy(data)
    system_terms = terms.get("system", [])
    functions = _functions_from_class_list(data.get("class_list") or [])
    media = ((data.get("_embedded") or {}).get("wp:featuredmedia") or [{}])[0]
    image_attribution = _clean_text(
        ((media.get("caption") or {}).get("rendered"))
        or ((media.get("description") or {}).get("rendered"))
        or media.get("alt_text")
    )

    return {
        "id": item_id,
        "title": title,
        "url": link,
        "subtype": item.get("subtype") or data.get("type") or "strategy",
        "organism": page_meta.get("organism") or _organism_from_system_terms(system_terms),
        "summary": page_meta.get("summary", ""),
        "systems": system_terms,
        "functions": functions,
        "image_url": media.get("source_url"),
        "image_attribution": page_meta.get("image_attribution") or image_attribution,
        "modified": data.get("modified_gmt") or data.get("modified"),
        "source": "AskNature",
        "usage_note": USAGE_NOTE,
    }


def _fallback_record(item):
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "url": item.get("url"),
        "subtype": item.get("subtype") or "strategy",
        "organism": "",
        "systems": [],
        "functions": [],
        "image_url": "",
        "image_attribution": "",
        "modified": "",
        "source": "AskNature",
        "usage_note": USAGE_NOTE,
    }


def _fetch_json(url):
    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def _fetch_text(url):
    if not url:
        return ""
    request = Request(url, headers={"Accept": "text/html", "User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=12) as response:
            return response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError):
        return ""


def _cached_page_metadata(item_id, url, cache):
    cache_key = f"{CACHE_VERSION}:page:{item_id}"
    now = int(time.time())
    cached = cache.get(cache_key)
    if cached and now - cached.get("fetched_at", 0) < CACHE_TTL_SECONDS:
        return cached.get("data", {})

    data = _page_metadata(url)
    cache[cache_key] = {"fetched_at": now, "data": data}
    return data


def _page_metadata(url):
    html = _fetch_text(url)
    if not html:
        return {}

    header_match = re.search(
        r"<small>\s*Biological Strategy\s*</small>.*?<h2[^>]*>.*?</h2>\s*(?:<[^>]+>\s*)*<h3[^>]*>(.*?)</h3>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    description_match = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    credit_match = re.search(
        r'<div[^>]*class=["\'][^"\']*image-credit[^"\']*["\'][^>]*>\s*Image:\s*(.*?)</div>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return {
        "organism": _clean_text(header_match.group(1)) if header_match else "",
        "summary": _clean_text(description_match.group(1)) if description_match else "",
        "image_attribution": _clean_text(credit_match.group(1)) if credit_match else "",
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


def _clean_text(value):
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(value))
    text = unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _terms_by_taxonomy(data):
    grouped = {}
    for group in (data.get("_embedded") or {}).get("wp:term", []):
        for term in group:
            taxonomy = term.get("taxonomy")
            name = _clean_text(term.get("name"))
            if taxonomy and name:
                grouped.setdefault(taxonomy, []).append(name)
    return grouped


def _organism_from_system_terms(system_terms):
    if not system_terms:
        return ""
    return system_terms[-1]


def _functions_from_class_list(class_list):
    functions = []
    for item in class_list:
        if not item.startswith("function-"):
            continue
        label = item.removeprefix("function-").replace("-", " ")
        label = label[:1].upper() + label[1:]
        if label not in functions:
            functions.append(label)
    return functions
