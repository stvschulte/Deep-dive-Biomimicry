import json
import random
import re
from pathlib import Path


FRONTEND_PUBLIC_DIR = Path(__file__).parents[1] / "frontend" / "public"
FALLBACK_IMAGE_DIR = FRONTEND_PUBLIC_DIR / "images" / "fallback"
MANIFEST_PATH = FALLBACK_IMAGE_DIR / "image_manifest.json"


def product_fallback_image(product="", hint=""):
    return _fallback_image("product_helmets", f"{product} {hint}", "Local helmet backup")


def animal_fallback_image(organism="", function=""):
    return _fallback_image("animals", f"{organism} {function}", "Local animal backup")


def _fallback_image(category, query, source):
    manifest = _load_manifest()
    candidates = [
        item for item in manifest.get("images", [])
        if item.get("category") == category and _local_file_exists(item)
    ]
    if not candidates:
        return None

    selected = _ranked_choice(candidates, query)
    rel_path = selected["path"].replace("\\", "/")
    local_path = FALLBACK_IMAGE_DIR / rel_path
    return {
        "image_url": f"/images/fallback/{rel_path}",
        "local_path": str(local_path),
        "fallback": True,
        "fallback_reason": "External image API unavailable; using a local backup image.",
        "source": source,
        "source_url": selected.get("source_url", ""),
        "title": selected.get("title", ""),
        "attribution": selected.get("attribution", ""),
        "license": selected.get("license", ""),
        "taxon_name": selected.get("common_name") or selected.get("title", ""),
    }


def _load_manifest():
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"images": []}


def _local_file_exists(item):
    rel_path = item.get("path")
    return bool(rel_path and (FALLBACK_IMAGE_DIR / rel_path).exists())


def _ranked_choice(candidates, query):
    terms = {term for term in re.findall(r"[a-z0-9]+", (query or "").lower()) if len(term) > 2}
    if not terms:
        return random.choice(candidates)

    ranked = []
    for item in candidates:
        haystack = " ".join([
            item.get("title", ""),
            item.get("common_name", ""),
            item.get("scientific_name", ""),
            " ".join(item.get("tags", [])),
            " ".join(item.get("functions", [])),
        ]).lower()
        score = sum(1 for term in terms if term in haystack)
        ranked.append((score, item))

    best_score = max(score for score, _ in ranked)
    best = [item for score, item in ranked if score == best_score]
    return random.choice(best)
