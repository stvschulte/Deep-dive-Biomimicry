#!/usr/bin/env python3
import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
FALLBACK_DIR = ROOT / "biomimetix" / "frontend" / "public" / "images" / "fallback"
HELMET_DIR = FALLBACK_DIR / "product_helmets"
ANIMAL_DIR = FALLBACK_DIR / "animals"
MANIFEST_PATH = FALLBACK_DIR / "image_manifest.json"
USER_AGENT = "BioMimetix fallback image fetcher/1.0"


ANIMALS = [
    ("Armadillo", ["protection", "impact", "armor", "layering"]),
    ("Pangolin", ["protection", "scales", "curling", "armor"]),
    ("Gecko", ["adhesion", "surface contact", "grip"]),
    ("Honeybee", ["lightweight structure", "hexagonal packing", "material efficiency"]),
    ("Kingfisher", ["streamlining", "low drag", "impact entry"]),
    ("Woodpecker", ["shock absorption", "impact protection", "vibration damping"]),
    ("Mantis shrimp", ["impact", "fracture resistance", "energy storage"]),
    ("Sea turtle", ["shell protection", "streamlining", "navigation"]),
    ("Porcupine", ["puncture", "deterrence", "barbed attachment"]),
    ("Shark", ["drag reduction", "surface texture", "flow control"]),
    ("Owl", ["silent flight", "noise reduction", "edge control"]),
    ("Dragonfly", ["lightweight wings", "maneuverability", "stability"]),
    ("Humpback whale", ["flow control", "tubercles", "maneuverability"]),
    ("Octopus", ["soft robotics", "camouflage", "distributed grip"]),
    ("Cuttlefish", ["camouflage", "adaptive texture", "color change"]),
    ("Spider", ["fiber strength", "web structure", "vibration sensing"]),
    ("Beaver", ["water management", "material assembly", "habitat engineering"]),
    ("Termite", ["passive ventilation", "thermal regulation", "porous structure"]),
    ("Morpho butterfly", ["structural color", "lightweight surface", "optics"]),
    ("Namib desert beetle", ["water harvesting", "surface wettability", "fog collection"]),
    ("Bat", ["echolocation", "folding wings", "agile flight"]),
    ("Falcon", ["high-speed flight", "vision", "aerodynamics"]),
    ("Chameleon", ["adaptive grip", "vision", "color change"]),
    ("Elephant", ["flexible manipulation", "thermal regulation", "load support"]),
    ("Snake", ["flexible locomotion", "scales", "friction control"]),
    ("Limpet", ["adhesion", "abrasion resistance", "mineralized teeth"]),
    ("Mussel", ["wet adhesion", "fiber anchoring", "wave resistance"]),
    ("Abalone", ["impact resistance", "layered nacre", "toughness"]),
    ("Boxfish", ["stability", "protected body", "flow"]),
    ("Sea urchin", ["spines", "modular shell", "puncture protection"]),
]

HELMET_QUERIES = [
    "cycling helmet",
    "bicycle helmet",
    "bike helmet",
    "cycling helmet closeup",
    "cardboard cycling helmet",
]

HELMET_TITLES = [
    "File:Bicycle Helmet 0085.jpg",
    "File:Bicycle white helmet from ABUS.jpg",
    "File:Bicycle white helmet from ABUS 2.jpg",
    "File:Bicycle white helmet from bikemate.jpg",
    "File:Casque vélo de course.jpg",
    "File:Bike Helmet.jpg",
    "File:Bike helmet.jpg",
    "File:Cycling Helmet.jpg",
    "File:Cycling helmet.JPG",
    "File:Met trenta 3k carbon mips bicycle helmet.jpg",
]


def main():
    HELMET_DIR.mkdir(parents=True, exist_ok=True)
    ANIMAL_DIR.mkdir(parents=True, exist_ok=True)
    images = []
    images.extend(fetch_helmet_images())
    images.extend(fetch_animal_images())
    MANIFEST_PATH.write_text(
        json.dumps({"generated_by": "scripts/fetch_fallback_images.py", "images": images}, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(images)} fallback image records to {MANIFEST_PATH}")


def fetch_helmet_images():
    records = []
    seen_urls = set()
    for item in commons_pages_by_titles(HELMET_TITLES):
        add_helmet_record(item, records, seen_urls)
        if len(records) >= 5:
            return records

    for query in HELMET_QUERIES:
        for item in commons_search(query, limit=8):
            add_helmet_record(item, records, seen_urls)
            if len(records) >= 5:
                return records
    return records


def add_helmet_record(item, records, seen_urls):
    title = item.get("title", "")
    if "transparent" in title.lower():
        return
    image = (item.get("imageinfo") or [{}])[0]
    url = image.get("thumburl") or image.get("url")
    if not url or url in seen_urls:
        return
    index = len(records) + 1
    path = HELMET_DIR / f"helmet-{index}.jpg"
    if not download(url, path):
        return
    seen_urls.add(url)
    records.append({
        "category": "product_helmets",
        "path": f"product_helmets/{path.name}",
        "title": clean_title(title or f"Cycling helmet {index}"),
        "source": "Wikimedia Commons",
        "source_url": image.get("descriptionurl", ""),
        "license": metadata_value(image.get("extmetadata") or {}, "LicenseShortName"),
        "attribution": clean_html(metadata_value(image.get("extmetadata") or {}, "Artist")),
        "tags": ["cycling helmet", "bike helmet", "product", "protection"],
        "functions": ["head protection", "impact absorption", "ventilation"],
    })


def fetch_animal_images():
    records = []
    for animal, functions in ANIMALS:
        taxon = inaturalist_taxon(animal)
        if not taxon:
            continue
        photo = taxon.get("default_photo") or {}
        url = larger_inaturalist_url(photo.get("medium_url") or photo.get("url"))
        if not url:
            continue
        path = ANIMAL_DIR / f"{slugify(animal)}.jpg"
        if not download(url, path):
            continue
        records.append({
            "category": "animals",
            "path": f"animals/{path.name}",
            "common_name": animal,
            "scientific_name": taxon.get("name", ""),
            "title": taxon.get("preferred_common_name") or animal,
            "source": "iNaturalist",
            "source_url": f"https://www.inaturalist.org/taxa/{taxon.get('id')}" if taxon.get("id") else "https://www.inaturalist.org",
            "license": photo.get("license_code") or "",
            "attribution": photo.get("attribution") or "iNaturalist taxon photo",
            "tags": [animal.lower(), taxon.get("name", "").lower()],
            "functions": functions,
        })
        time.sleep(0.15)
    return records


def commons_pages_by_titles(titles):
    params = {
        "action": "query",
        "titles": "|".join(titles),
        "prop": "imageinfo",
        "iiprop": "url|mime|size|extmetadata",
        "iiurlwidth": 1200,
        "format": "json",
    }
    data = fetch_json(f"https://commons.wikimedia.org/w/api.php?{urlencode(params)}")
    pages = (data.get("query") or {}).get("pages") or {}
    return [page for page in pages.values() if usable_commons_image(page)]


def commons_search(query, limit=8):
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap",
        "gsrnamespace": 6,
        "gsrlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|mime|size|extmetadata",
        "iiurlwidth": 1200,
        "format": "json",
    }
    data = fetch_json(f"https://commons.wikimedia.org/w/api.php?{urlencode(params)}")
    pages = (data.get("query") or {}).get("pages") or {}
    usable = []
    for page in pages.values():
        if usable_commons_image(page):
            usable.append(page)
    return usable


def usable_commons_image(page):
    image = (page.get("imageinfo") or [{}])[0]
    return image.get("mime", "").startswith("image/") and image.get("mime") not in {"image/svg+xml", "image/gif"}


def inaturalist_taxon(name):
    params = urlencode({"q": name, "per_page": 5})
    data = fetch_json(f"https://api.inaturalist.org/v1/taxa/autocomplete?{params}")
    taxa = (data.get("results") or []) if data else []
    return next((item for item in taxa if item.get("default_photo")), taxa[0] if taxa else None)


def fetch_json(url):
    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def download(url, path):
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=20) as response:
            data = response.read()
        if len(data) < 4096:
            return False
        path.write_bytes(data)
        return True
    except (HTTPError, URLError, TimeoutError, OSError):
        return False


def larger_inaturalist_url(url):
    if not url:
        return ""
    return url.replace("/square.", "/medium.").replace("/small.", "/medium.").replace("/thumb.", "/medium.")


def slugify(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def clean_title(value):
    return clean_html(str(value or "").removeprefix("File:"))


def metadata_value(metadata, key):
    value = metadata.get(key)
    if isinstance(value, dict):
        return clean_html(value.get("value", ""))
    return ""


def clean_html(value):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(value or ""))).strip()


if __name__ == "__main__":
    main()
