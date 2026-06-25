import os
import json
import re
import hashlib
import math
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
import streamlit as st
from pydantic import BaseModel
from dotenv import load_dotenv
from google.genai import Client, types
from asknature import asknature_biomimicry_options, asknature_search
from product_images import product_image_search

# --- Pydantic Data Models ---
class DeconstructReq(BaseModel):
    product: str

class ProductImageReq(BaseModel):
    product: str

class BiomimicryReq(BaseModel):
    product: str
    function: str

class AbstractReq(BaseModel):
    product: str
    function: str
    organism: str

class IdeateReq(BaseModel):
    product: str
    principle: str

class PromptReq(BaseModel):
    product: str
    concept: str

class ComponentItem(BaseModel):
    component: str
    function: str

class ExplodedViewReq(BaseModel):
    product: str
    components: list[ComponentItem]

class ReferenceImageReq(BaseModel):
    organism: str
    function: str

class AskNatureSearchReq(BaseModel):
    query: str
    limit: int = 5


load_dotenv(Path(__file__).with_name(".env"))

api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
image_model_name = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
client = Client(api_key=api_key) if api_key else None
image_dir = Path(__file__).parent / "generated_images"
image_dir.mkdir(exist_ok=True)


# --- Helper Functions (mostly unchanged) ---

def get_gemini_client():
    if client is None:
        st.error(
            "GEMINI_API_KEY is missing. Add `GEMINI_API_KEY=your_key_here` to `biomimetix/backend/.env` and restart the app."
        )
        st.stop()
    return client

# --- Defensive Parser ---
def safe_parse_gemini(response):
    """Extracts and parses JSON, aggressively handling safety blocks and markdown artifacts."""
    try:
        if not response.text:
            raise ValueError("Response blocked by safety filters. Please try a different query.")

        raw_text = response.text.strip()
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE)
        raw_text = re.sub(r"\s*```$", "", raw_text)

        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"AI returned malformed organic data: {str(e)}")

def api_error(status_code, error):
    message = str(error)
    if is_quota_error(error) or status_code == 429:
        st.error(
            (
                "Gemini quota is exhausted for the selected model. Wait for the retry window, "
                "or enable billing / raise limits in Google AI Studio. Text uses GEMINI_MODEL; "
                "generated visuals use GEMINI_IMAGE_MODEL."
            )
        )
    else:
        st.error(f"An error occurred: {message} (Status: {status_code})")

def is_quota_error(error):
    message = str(error)
    return "RESOURCE_EXHAUSTED" in message or "429" in message or "quota" in message.lower()

def cache_name(prefix, *values):
    raw = "|".join(values).lower().encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:18]
    return f"{prefix}-{digest}.png"

def image_response(filename, fallback=False):
    return {"image_url": str(image_dir / filename), "fallback": fallback}

def write_svg(filename, svg):
    path = image_dir / filename
    path.write_text(svg, encoding="utf-8")
    return image_response(filename, fallback=True)

def fallback_exploded_svg(req):
    filename = cache_name("exploded-fallback", req.product, ",".join([item.component for item in req.components])).replace(".png", ".svg")
    path = image_dir / filename
    if path.exists():
        response = image_response(filename, fallback=True)
        response["fallback_reason"] = "Gemini image generation was unavailable."
        return response
    count = max(3, min(6, len(req.components)))
    shapes = []
    width = 1200
    start_x = 180
    gap = 160
    colors = ["#d8e2c0", "#9fb675", "#5f7b4b", "#c98f65", "#e9d6b8", "#758f66"]
    for i in range(count):
        x = start_x + i * gap
        y = 330 + (i % 2) * 120
        w = 110 + (i % 3) * 26
        h = 210 - (i % 2) * 30
        color = colors[i % len(colors)]
        shapes.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{42}" fill="{color}" opacity="0.95"/>')
        shapes.append(f'<circle cx="{x + w / 2}" cy="{y + h / 2}" r="{min(w,h)/4}" fill="#fffaf0" opacity="0.28"/>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="760" viewBox="0 0 1200 760">
<defs>
  <radialGradient id="bg" cx="50%" cy="45%" r="70%"><stop offset="0" stop-color="#fffaf0"/><stop offset="1" stop-color="#e8dec9"/></radialGradient>
  <filter id="shadow"><feDropShadow dx="0" dy="18" stdDeviation="18" flood-color="#2f3a28" flood-opacity="0.16"/></filter>
</defs>
<rect width="1200" height="760" fill="url(#bg)"/>
<g filter="url(#shadow)">
{''.join(shapes)}
</g>
<path d="M130 575 C 330 610, 580 620, 1030 560" fill="none" stroke="#6f8f52" stroke-width="3" opacity="0.22"/>
</svg>'''
    response = write_svg(filename, svg)
    response["fallback_reason"] = "Gemini image generation was unavailable."
    return response

def svg_color(value, fallback):
    if not isinstance(value, str):
        return fallback
    value = value.strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return value
    return fallback

def render_ai_exploded_svg(req, layout):
    filename = cache_name("exploded-ai-svg-v3", req.product, ",".join([item.component for item in req.components])).replace(".png", ".svg")
    path = image_dir / filename
    if path.exists():
        response = image_response(filename, fallback=True)
        response["fallback_reason"] = "Gemini image quota exhausted; generated an AI-directed SVG diagram instead."
        return response

    components = req.components[:6]
    layout = layout if isinstance(layout, list) else []
    width = 1200
    height = 760
    palette = ["#d8e2c0", "#9fb675", "#5f7b4b", "#c98f65", "#e9d6b8", "#758f66"]
    shapes = []
    center_x = width / 2
    center_y = height / 2
    count = max(1, len(components))
    for index, component in enumerate(components):
        item = layout[index] if index < len(layout) and isinstance(layout[index], dict) else {}
        angle = -math.pi / 2 + (index / count) * math.pi * 2
        x = int(center_x + math.cos(angle) * 330)
        y = int(center_y + math.sin(angle) * 205)
        x = max(130, min(1070, x))
        y = max(145, min(570, y))
        w = max(72, min(220, int(item.get("width", 128 + (index % 3) * 24))))
        h = max(48, min(210, int(item.get("height", 94 + (index % 2) * 56))))
        rx = max(10, min(42, int(item.get("radius", 28))))
        color = svg_color(item.get("color"), palette[index % len(palette)])
        rotate = max(-14, min(14, int(item.get("rotation", 0))))
        label = re.sub(r"[^a-zA-Z0-9 .,/()_-]", "", component.component)[:38]
        function = re.sub(r"[^a-zA-Z0-9 .,/()_-]", "", component.function)[:58]
        shapes.append(f'<path d="M{center_x:.0f} {center_y:.0f} C {(center_x + x) / 2:.0f} {center_y - 54:.0f}, {(center_x + x) / 2:.0f} {y + 54:.0f}, {x:.0f} {y:.0f}" fill="none" stroke="#263020" stroke-opacity="0.16" stroke-width="2" stroke-dasharray="8 11"/>')
        shapes.append(f'<g transform="translate({x - w / 2:.0f} {y - h / 2:.0f}) rotate({rotate} {w / 2:.0f} {h / 2:.0f})">')
        shapes.append(f'<rect width="{w}" height="{h}" rx="{rx}" fill="{color}" opacity="0.97"/>')
        shapes.append(f'<path d="M{w * 0.16:.0f} {h * 0.58:.0f} C {w * 0.34:.0f} {h * 0.28:.0f}, {w * 0.66:.0f} {h * 0.25:.0f}, {w * 0.84:.0f} {h * 0.55:.0f}" fill="none" stroke="#fffaf0" stroke-opacity="0.42" stroke-width="8" stroke-linecap="round"/>')
        shapes.append(f'<circle cx="{w * 0.74:.0f}" cy="{h * 0.32:.0f}" r="{min(w, h) * 0.12:.0f}" fill="#263020" opacity="0.1"/>')
        shapes.append("</g>")
        shapes.append(f'<text x="{x:.0f}" y="{y + h / 2 + 34:.0f}" text-anchor="middle" fill="#263020" font-family="Arial, sans-serif" font-size="18" font-weight="700">{label}</text>')
        shapes.append(f'<text x="{x:.0f}" y="{y + h / 2 + 58:.0f}" text-anchor="middle" fill="#4e5d43" font-family="Arial, sans-serif" font-size="13">{function}</text>')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="760" viewBox="0 0 1200 760">
<defs>
  <radialGradient id="bg" cx="50%" cy="45%" r="72%"><stop offset="0" stop-color="#fffaf0"/><stop offset="1" stop-color="#e8ecd6"/></radialGradient>
  <filter id="shadow"><feDropShadow dx="0" dy="18" stdDeviation="16" flood-color="#20291c" flood-opacity="0.16"/></filter>
</defs>
<rect width="1200" height="760" fill="url(#bg)"/>
<ellipse cx="600" cy="380" rx="210" ry="122" fill="none" stroke="#263020" stroke-opacity="0.13" stroke-width="3" stroke-dasharray="11 13"/>
<g filter="url(#shadow)">
{''.join(shapes)}
</g>
</svg>'''
    response = write_svg(filename, svg)
    response["fallback_reason"] = "Gemini image quota exhausted; generated an AI-directed SVG diagram instead."
    return response

def ai_svg_exploded_view(req):
    component_list = ", ".join([f"{item.component} ({item.function})" for item in req.components])
    prompt = f"""
    Create layout data for a clean exploded technical SVG diagram of a {req.product}.
    Components: {component_list}.
    Return ONLY a JSON array with one object per component in the same order.
    Each object must have integer x, y, width, height, radius, rotation and a muted hex color.
    Keep all coordinates inside a 1200 by 760 canvas and spread parts around the center.
    Example object: {{"x": 260, "y": 300, "width": 150, "height": 90, "radius": 28, "rotation": -5, "color": "#9fb675"}}.
    """
    try:
        response = get_gemini_client().models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return render_ai_exploded_svg(req, safe_parse_gemini(response))
    except Exception:
        return fallback_exploded_svg(req)

def fallback_reference_svg(req):
    filename = cache_name("reference-fallback", req.organism, req.function).replace(".png", ".svg")
    path = image_dir / filename
    if path.exists():
        return image_response(filename, fallback=True)
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="620" viewBox="0 0 900 620">
<defs>
  <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#fffaf0"/><stop offset="1" stop-color="#dfe8c9"/></linearGradient>
  <radialGradient id="glow" cx="58%" cy="42%" r="45%"><stop offset="0" stop-color="#f5b77d" stop-opacity="0.55"/><stop offset="1" stop-color="#f5b77d" stop-opacity="0"/></radialGradient>
  <filter id="shadow"><feDropShadow dx="0" dy="20" stdDeviation="18" flood-color="#2f3a28" flood-opacity="0.18"/></filter>
</defs>
<rect width="900" height="620" fill="url(#bg)"/>
<rect width="900" height="620" fill="url(#glow)"/>
<g filter="url(#shadow)" opacity="0.96">
  <ellipse cx="440" cy="330" rx="230" ry="115" fill="#6f8f52"/>
  <circle cx="640" cy="275" r="78" fill="#8fa764"/>
  <path d="M220 330 C120 270 92 185 135 126 C185 185 248 228 318 254 Z" fill="#5f7b4b"/>
  <path d="M430 235 C470 165 550 135 650 145 C590 190 548 238 525 298 Z" fill="#c98f65"/>
  <circle cx="665" cy="260" r="12" fill="#263020"/>
  <path d="M320 355 C415 330 510 324 620 348" fill="none" stroke="#fffaf0" stroke-width="10" stroke-linecap="round" opacity="0.42"/>
</g>
<circle cx="560" cy="340" r="96" fill="none" stroke="#c98f65" stroke-width="10" opacity="0.72"/>
</svg>'''
    return write_svg(filename, svg)

def fetch_json(url):
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "BioMimetix local biomimicry prototype/1.0",
        },
    )
    try:
        with urlopen(request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None

def larger_inaturalist_url(url):
    if not url:
        return ""
    return (
        url.replace("/square.", "/medium.")
        .replace("/small.", "/medium.")
        .replace("/thumb.", "/medium.")
    )

def inaturalist_reference(req):
    taxa_params = urlencode({"q": req.organism, "per_page": 5})
    taxa_data = fetch_json(f"https://api.inaturalist.org/v1/taxa/autocomplete?{taxa_params}")
    taxa = (taxa_data or {}).get("results") or []
    if not taxa:
        return None

    taxon = next((item for item in taxa if item.get("default_photo")), taxa[0])
    taxon_id = taxon.get("id")
    taxon_name = taxon.get("preferred_common_name") or taxon.get("matched_term") or taxon.get("name") or req.organism

    if taxon_id:
        observation_params = urlencode({
            "taxon_id": taxon_id,
            "photos": "true",
            "quality_grade": "research",
            "photo_license": "cc0,cc-by,cc-by-sa",
            "per_page": 1,
            "order_by": "votes",
        })
        observation_data = fetch_json(f"https://api.inaturalist.org/v1/observations?{observation_params}")
        observations = (observation_data or {}).get("results") or []
        for observation in observations:
            photos = observation.get("observation_photos") or []
            if photos:
                photo = photos[0].get("photo") or {}
                image_url = photo.get("medium_url") or larger_inaturalist_url(photo.get("url"))
                if image_url:
                    return {
                        "image_url": image_url,
                        "fallback": False,
                        "source": "iNaturalist",
                        "source_url": observation.get("uri") or f"https://www.inaturalist.org/taxa/{taxon_id}",
                        "attribution": photo.get("attribution") or "iNaturalist observation photo",
                        "taxon_name": taxon_name,
                        "license": photo.get("license_code") or "",
                    }

    default_photo = taxon.get("default_photo") or {}
    image_url = default_photo.get("medium_url") or larger_inaturalist_url(default_photo.get("url"))
    if image_url:
        return {
            "image_url": image_url,
            "fallback": False,
            "source": "iNaturalist",
            "source_url": f"https://www.inaturalist.org/taxa/{taxon_id}" if taxon_id else "https://www.inaturalist.org",
            "attribution": default_photo.get("attribution") or "iNaturalist taxon photo",
            "taxon_name": taxon_name,
            "license": default_photo.get("license_code") or "",
        }
    return None

def wikimedia_reference(req):
    title = quote(req.organism.replace(" ", "_"))
    data = fetch_json(f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}")
    if not data:
        return None
    image = (data.get("thumbnail") or {}).get("source") or (data.get("originalimage") or {}).get("source")
    if not image:
        return None
    return {
        "image_url": image,
        "fallback": False,
        "source": "Wikimedia",
        "source_url": (data.get("content_urls") or {}).get("desktop", {}).get("page") or f"https://en.wikipedia.org/wiki/{title}",
        "attribution": "Wikimedia Commons / Wikipedia",
        "taxon_name": data.get("title") or req.organism,
        "license": "",
    }

def biodiversity_reference(req):
    return inaturalist_reference(req) or wikimedia_reference(req) or fallback_reference_svg(req)

def generate_image(prompt, filename):
    path = image_dir / filename
    if path.exists():
        return image_response(filename)

    try:
        response = get_gemini_client().models.generate_content(
            model=image_model_name,
            contents=[prompt],
        )
        for part in response.parts:
            if part.inline_data is not None:
                image = part.as_image()
                image.save(path)
                return image_response(filename)
        raise ValueError("Gemini did not return image data.")
    except HTTPException:
        raise
    except Exception as e:
        api_error(500, e)

def fallback_deconstruct(product):
    base = [
        ("Outer structure", "Protects and defines the main form"),
        ("Load-bearing core", "Transfers force and maintains stability"),
        ("Connection points", "Joins parts and controls movement"),
        ("Interface surface", "Supports contact with the user or environment"),
        ("Regulation feature", "Controls airflow, pressure, grip, sound, or motion"),
    ]
    return [{"component": name, "function": function} for name, function in base]

def fallback_biomimicry(function):
    options = [
        {"organism": "Armadillo", "rationale": f"Uses layered protective armor that can inspire {function}."},
        {"organism": "Honeybee", "rationale": f"Builds efficient cellular structures that can support {function}."},
        {"organism": "Gecko", "rationale": f"Uses micro-scale surface interaction relevant to {function}."},
        {"organism": "Pinecone", "rationale": f"Passively changes structure in response to moisture, useful for {function}."},
        {"organism": "Kingfisher", "rationale": f"Uses streamlined geometry that can inform low-resistance {function}."},
    ]
    return [with_exploration_pack(option, function) for option in options]

def fallback_abstract(organism, function):
    return {
        "principles": [
            {"title": "Layered protection", "principle": f"Use nested material layers inspired by {organism} to improve {function}."},
            {"title": "Gradient stiffness", "principle": "Transition from soft to rigid zones so forces are absorbed before they peak."},
            {"title": "Responsive geometry", "principle": "Let form adapt passively to environmental or user pressure."},
        ],
        "sketch_pack": sketch_pack(organism, function),
    }

def fallback_ideate(product, principle):
    return [
        {"concept_name": "Layered Bio-Shell", "description": f"A {product} concept using {principle} through nested organic layers."},
        {"concept_name": "Adaptive Surface", "description": f"A {product} surface that changes grip, airflow, or stiffness based on use."},
        {"concept_name": "Vein-Frame Structure", "description": "A branching internal frame that places strength only where forces travel."},
        {"concept_name": "Soft-Hard Gradient", "description": "A concept with soft contact zones and rigid support zones blended continuously."},
        {"concept_name": "Passive Flow Form", "description": "A smoother product geometry that reduces resistance through natural streamlining."},
    ]

def exploration_pack(organism, function):
    query = quote(f"{organism} {function} biomimicry slow motion mechanism")
    literature_query = quote(f"{organism} biomimicry {function} mechanism")
    return {
        "watch": [
            {
                "title": f"Watch {organism} performing the function",
                "description": "Look for timing, force direction, contact surfaces, and repeated motion.",
                "url": f"https://www.youtube.com/results?search_query={query}",
            },
            {
                "title": f"Search slow-motion footage of {organism}",
                "description": "Pause the video and sketch the sequence in three frames.",
                "url": f"https://www.youtube.com/results?search_query={quote(f'{organism} slow motion biology')}",
            },
        ],
        "read": [
            {
                "title": "AskNature strategy search",
                "description": "Read related biological strategies and note the mechanism, not the organism name.",
                "url": f"https://asknature.org/?s={literature_query}",
            },
            {
                "title": "Wikipedia background",
                "description": "Use taxonomy and anatomy terms to refine your observations.",
                "url": f"https://en.wikipedia.org/w/index.php?search={quote(organism)}",
            },
        ],
        "act": {
            "title": "Nature Quest",
            "description": (
                f"Step away from the screen for 10 minutes. Find a local natural object that also deals with "
                f"'{function}'. Photograph or sketch the part that transfers force, protects, grips, flows, or adapts."
            ),
            "checklist": [
                "Observe with your eyes before reading explanations.",
                "Draw the mechanism as arrows, surfaces, pivots, pores, layers, or gradients.",
                "Write one sentence about what the organism does that your product does not yet do.",
            ],
        },
    }

def with_exploration_pack(option, function):
    organism = option.get("organism") or "biological strategy"
    enriched = dict(option)
    enriched["exploration_pack"] = enriched.get("exploration_pack") or exploration_pack(organism, function)
    return enriched

def sketch_pack(organism, function):
    return {
        "title": "Sketch the principle outside its biology",
        "prompt": (
            f"Grab pen and paper. Draw how the {organism} principle performs '{function}' in a mechanical vacuum: "
            "no product, no decoration, only forces, surfaces, material gradients, joints, pores, layers, and flow paths."
        ),
        "checks": [
            "Use arrows for force or flow direction.",
            "Label at least three functional zones.",
            "Draw one failure mode where the mechanism breaks down.",
        ],
    }

# --- API Logic (converted to functions) ---

def get_health_status():
    return {
        "status": "ok",
        "gemini_configured": client is not None,
        "model": model_name,
        "image_model": image_model_name,
    }

def deconstruct_product(req: DeconstructReq):
    prompt = f"""
    You are a biological-mechanical design hybrid. Deconstruct the product: "{req.product}".
    Identify 5 distinct physical or functional components. Define its pure abstract function.
    Return ONLY a JSON array of 5 objects: {{"component": "str", "function": "str"}}.
    """
    try:
        response = get_gemini_client().models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return safe_parse_gemini(response)
    except Exception as e:
        if is_quota_error(e):
            return fallback_deconstruct(req.product)
        api_error(500, e)
        return None


def biomimetic_search(req: BiomimicryReq):
    asknature_options = asknature_biomimicry_options(req.function, req.product, limit=5)
    if asknature_options:
        return [with_exploration_pack(option, req.function) for option in asknature_options]

    prompt = f"""
    You are a biomimicry exploration guide, not an answer machine.
    Product: "{req.product}". Function targeted: "{req.function}".
    Find 5 distinct biological organisms or biological strategies that perform this function.
    For each option, create an exploration_pack that pushes the user toward active research before they can proceed.
    Return ONLY a JSON array of 5 objects with this exact shape:
    {{
      "organism": "str",
      "rationale": "str explaining the biological mechanism",
      "exploration_pack": {{
        "watch": [{{"title": "str", "description": "str", "url": "YouTube search URL"}}],
        "read": [{{"title": "str", "description": "str", "url": "article/search URL"}}],
        "act": {{"title": "Nature Quest", "description": "physical observation assignment", "checklist": ["str", "str", "str"]}}
      }}
    }}.
    """
    try:
        response = get_gemini_client().models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return [with_exploration_pack(option, req.function) for option in safe_parse_gemini(response)]
    except Exception as e:
        if is_quota_error(e):
            return fallback_biomimicry(req.function)
        api_error(500, e)
        return None

def principle_abstraction(req: AbstractReq):
    prompt = f"""
    Translate biology to mechanics. Organism: "{req.organism}". Function: "{req.function}".
    Strip the biology away. Extract 3 pure, scalable engineering/physics principles from this mechanism.
    Also create a sketching assignment that forces the user to draw the mechanism before ideation.
    Return ONLY a JSON object:
    {{
      "principles": [{{"title": "str", "principle": "str"}}],
      "sketch_pack": {{"title": "str", "prompt": "str", "checks": ["str", "str", "str"]}}
    }}.
    """
    try:
        response = get_gemini_client().models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        data = safe_parse_gemini(response)
        if isinstance(data, list):
            return {"principles": data, "sketch_pack": sketch_pack(req.organism, req.function)}
        data["sketch_pack"] = data.get("sketch_pack") or sketch_pack(req.organism, req.function)
        return data
    except Exception as e:
        if is_quota_error(e):
            return fallback_abstract(req.organism, req.function)
        api_error(500, e)
        return None

def ideate_concepts(req: IdeateReq):
    prompt = f"""
    You are an avant-garde product designer. Product: "{req.product}". Engineering Principle: "{req.principle}".
    Generate 5 distinct, fluid, and highly organic product application concepts utilizing this principle.
    Return ONLY a JSON array of 5 objects: {{"concept_name": "str", "description": "str"}}.
    """
    try:
        response = get_gemini_client().models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return safe_parse_gemini(response)
    except Exception as e:
        if is_quota_error(e):
            return fallback_ideate(req.product, req.principle)
        api_error(500, e)
        return None

def generate_prompt(req: PromptReq):
    prompt = f"""
    You are an AI image prompt specialist. Concept: "{req.concept}" for "{req.product}".
    Write a highly rigid text prompt for a 2D generative AI to visualize this physical biomimetic product.
    The prompt must describe only one product object and must be optimized for clean image-to-3D conversion.
    Do NOT output JSON. Output ONLY the prompt string.
    """
    try:
        response = get_gemini_client().models.generate_content(model=model_name, contents=prompt)
        base_prompt = response.text.strip().replace('"', '').replace('\n', ' ')
        strict_constraints = "Pure white background, single object, isometric view, no shadows, high contrast silhouette, centered composition, complete object visible, no text, no labels, no hands, no people."
        final_prompt = f"{base_prompt}, {strict_constraints}"
        return {"prompt": final_prompt}
    except Exception as e:
        if is_quota_error(e):
            return {
                "prompt": (
                    f"{req.concept} for {req.product}, biomimetic product design, organic but functional form, "
                    "Pure white background, single object, isometric view, no shadows, high contrast silhouette, "
                    "centered composition, complete object visible, no text, no labels, no hands, no people."
                )
            }
        api_error(500, e)
        return None

def exploded_view(req: ExplodedViewReq):
    component_list = ", ".join([f"{item.component} ({item.function})" for item in req.components])
    filename = cache_name("exploded", req.product, component_list)
    prompt = f"""
    Create a clean front-view exploded product diagram of a {req.product}.
    Show exactly these separated physical components: {component_list}.
    The parts should be pulled apart along clear vertical and horizontal offsets, aligned as a readable technical exploded view.
    No text, no labels, no numbers, no arrows, no watermark.
    Style: realistic industrial design render, natural studio light, white or warm neutral background, high contrast, crisp component separation.
    Composition: centered, complete product visible, all components distinct, no hands, no people.
    """
    try:
        return generate_image(prompt, filename)
    except Exception as e:
        if is_quota_error(e):
            return ai_svg_exploded_view(req)
        api_error(500, e)
        return None

# --- Streamlit UI ---
import base64
import math

# ══════════════════════════════════════════════════════════════════════════════
# VISUAL CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

STEP_NAMES  = ["Product Analyse","Functions","Biomimicry","Principles","Ideation","2D Image","3D Model","Evaluate"]
STEP_ICONS  = ["🔬","⚙️","🌿","🧬","💡","🎨","🖨️","📋"]

_ORGANISMS = [
    ("Lotus leaf",         "Superhydrophobic self-cleaning nanostructure"),
    ("Sharkskin",          "Turbulence-breaking dermal denticles"),
    ("Spider silk",        "5× tensile strength of high-grade steel"),
    ("Mantis shrimp club", "1,500 N impact at 23 m/s without fracture"),
    ("Kingfisher bill",    "Zero-splash water entry via gradient taper"),
    ("Gecko foot",         "Van der Waals dry adhesion — no glue needed"),
    ("Boxfish shell",      "Rigid-yet-flexible interlocking lattice"),
    ("Bone trabeculate",   "Porous load-path optimisation"),
]

# ══════════════════════════════════════════════════════════════════════════════
# CSS — matching index.css palette exactly
# ══════════════════════════════════════════════════════════════════════════════

_FONTS = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,400;0,500;0,600;0,700;0,800;0,900;1,400&display=swap" rel="stylesheet">'

_CSS = """
<style>

:root {
  --deep:   #07130a;
  --line:   rgba(63,207,196,0.14);
  --line-b: rgba(63,207,196,0.34);
  --text:   #dff0e2;
  --muted:  rgba(223,240,226,0.64);
  --faint:  rgba(223,240,226,0.38);
  --bio:    #3fcfc4;
  --amber:  #c8973d;
  --spore:  #9b7bc4;
  --bio2:   #6ed688;
}

/* Page — multiple selectors for compatibility across Streamlit versions */
html, body,
[data-testid="stAppViewContainer"],
.stApp,
.main                           {
  background:
    radial-gradient(ellipse at 40% -5%,  rgba(63,207,196,0.20), transparent 44%),
    radial-gradient(ellipse at 90% 20%,  rgba(200,151,61,0.13),  transparent 38%),
    radial-gradient(ellipse at 8%  74%,  rgba(155,123,196,0.15), transparent 44%),
    radial-gradient(ellipse at 62% 92%,  rgba(63,207,196,0.09),  transparent 40%),
    linear-gradient(162deg, #050e07 0%, #081a0a 38%, #06100d 68%, #070b10 100%) !important;
  font-family: 'Inter', ui-sans-serif, system-ui, sans-serif !important;
  color: var(--text) !important;
}
/* Transparent header — multiple selectors */
[data-testid="stHeader"],
header[data-testid="stHeader"]      { background: transparent !important; }
/* Hide toolbar / hamburger / footer */
[data-testid="stToolbar"],
[data-testid="stDecoration"],
#MainMenu, footer, .css-1rs6os     { display: none !important; }
/* Sidebar — hide it */
section[data-testid="stSidebar"],
[data-testid="stSidebar"]           { display: none !important; }
/* Main content max-width */
[data-testid="stMainBlockContainer"],
.block-container,
.css-18e3th9,
.css-1d391kg                        { padding-top: 12px !important; max-width: 1240px !important; padding-left: 2rem !important; padding-right: 2rem !important; }

/* Typography */
h1,h2,h3,h4 { color: var(--text) !important; font-family: 'Inter', sans-serif !important; }
p, li, small, .stMarkdown, .stCaption { color: var(--muted) !important; font-family: 'Inter', sans-serif !important; }

/* ── Topbar ── */
.bm-topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 20px; margin-bottom: 24px;
  border: 1px solid var(--line);
  border-radius: 48px 22px 48px 22px;
  background: rgba(7,22,10,0.74);
  backdrop-filter: blur(32px) saturate(1.3);
  box-shadow: 0 18px 80px rgba(0,0,0,0.28), inset 0 1px 0 rgba(255,255,255,0.05);
}
.bm-brand  { font-size: 1.06rem; font-weight: 800; color: var(--text); }
.bm-tagline { color: var(--muted); font-size: 0.86rem; margin: 3px 0 0; }
.bm-pill {
  display: inline-flex; align-items: center; min-height: 34px; padding: 0 14px;
  border: 1px solid rgba(63,207,196,0.38); border-radius: 999px;
  background: rgba(63,207,196,0.10); color: var(--bio);
  font-size: 0.78rem; font-weight: 760; white-space: nowrap;
}

/* ── Timeline ── */
.bm-timeline { display: grid; grid-template-columns: repeat(8,1fr); gap: 8px; margin-bottom: 20px; }
.bm-tstep {
  padding: 10px 8px; text-align: center;
  border: 1px solid var(--line); border-radius: 26px 12px 26px 12px;
  background: rgba(7,22,10,0.54); color: var(--faint);
}
.bm-tstep-n {
  display: inline-flex; width: 26px; height: 26px;
  align-items: center; justify-content: center; margin-bottom: 8px;
  border-radius: 50% 32% 50% 32% / 32% 50% 32% 50%;
  background: rgba(223,240,226,0.07); font-size: 0.76rem; font-weight: 800; color: inherit;
}
.bm-tstep small { display: block; font-size: 0.72rem; font-weight: 640; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: inherit; }
.bm-tstep.active { border-color: rgba(63,207,196,0.58); color: var(--text); background: rgba(21,82,72,0.64); box-shadow: 0 0 40px rgba(63,207,196,0.12); }
.bm-tstep.done   { border-color: rgba(200,151,61,0.28); color: rgba(220,186,118,0.84); }

/* ── Context strip ── */
.bm-ctx { display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; margin-bottom: 20px; }
.bm-ctx-card {
  display: flex; flex-direction: column; align-items: flex-start; justify-content: center;
  min-height: 78px; padding: 10px 14px;
  border: 1px solid var(--line); border-radius: 34px 14px 34px 14px;
  background: rgba(8,24,12,0.70);
}
.bm-ctx-lbl { color: var(--amber) !important; font-size: 0.72rem !important; font-weight: 760 !important; letter-spacing: 0.11em; text-transform: uppercase; }
.bm-ctx-val { color: var(--text) !important; font-size: 0.94rem !important; font-weight: 700 !important; margin-top: 4px; display: block; word-break: break-word; }

/* ── Step panel (glass card) ── */
.bm-panel {
  padding: clamp(24px,4vw,50px); margin-bottom: 24px;
  border: 1px solid var(--line); border-radius: 56px 28px 56px 28px;
  background: linear-gradient(148deg, rgba(9,28,14,0.90), rgba(7,20,18,0.80));
  backdrop-filter: blur(40px) saturate(1.24);
  box-shadow: 0 36px 130px rgba(0,0,0,0.40), inset 0 1px 0 rgba(255,255,255,0.05);
}
.bm-step-header { max-width: 780px; margin-bottom: 28px; }
.bm-icon-bubble {
  display: inline-flex; width: 54px; height: 54px;
  align-items: center; justify-content: center; margin-bottom: 18px;
  border: 1px solid rgba(63,207,196,0.36); border-radius: 50% 32% 50% 32% / 32% 50% 32% 50%;
  background: rgba(63,207,196,0.10); color: var(--bio);
  box-shadow: 0 0 40px rgba(63,207,196,0.16); font-size: 1.4rem;
}
.bm-step-title { margin: 8px 0 10px; color: var(--text); font-size: clamp(2.1rem,5vw,3.6rem); font-weight: 800; line-height: 1.04; }
.bm-step-desc  { margin: 0; color: var(--muted); font-size: 1.06rem; line-height: 1.68; }

/* ── Cards ── */
.bm-grid   { display: grid; gap: 14px; margin-bottom: 16px; }
.bm-grid3  { grid-template-columns: repeat(3,1fr); }
.bm-grid4  { grid-template-columns: repeat(4,1fr); }
.bm-grid2  { grid-template-columns: repeat(2,1fr); }
.bm-card {
  position: relative; overflow: hidden; min-height: 160px; padding: 20px;
  border: 1px solid var(--line); border-radius: 38px 16px 38px 16px;
  background: rgba(9,28,14,0.68); color: var(--text); text-align: left;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
  transition: border-color 220ms ease, background 220ms ease, box-shadow 220ms ease;
}
.bm-card:hover    { border-color: rgba(63,207,196,0.52); background: rgba(18,72,60,0.60); box-shadow: 0 0 54px rgba(63,207,196,0.12); }
.bm-card.sel      { border-color: rgba(63,207,196,0.60); background: rgba(18,72,60,0.80); box-shadow: 0 0 54px rgba(63,207,196,0.18), inset 0 1px 0 rgba(255,255,255,0.07); }
.bm-lbl           { color: var(--amber); font-size: 0.72rem; font-weight: 760; letter-spacing: 0.11em; text-transform: uppercase; }
.bm-card-title    { display: block; color: var(--text); font-size: 1.10rem; font-weight: 700; margin: 6px 0 10px; }
.bm-card-body     { color: var(--muted); font-size: 0.88rem; line-height: 1.58; margin: 0; }
.bm-card-tag      { display: inline-flex; margin-top: 12px; color: var(--bio); font-size: 0.80rem; font-weight: 760; letter-spacing: 0.08em; text-transform: uppercase; }

/* ── Buttons ── */
.stButton > button {
  border-radius: 38px 12px 38px 12px !important;
  background: linear-gradient(138deg, #3fcfc4, #6ed688) !important;
  color: #051208 !important; font-weight: 800 !important;
  border: 0 !important; min-height: 52px !important; padding: 0 24px !important;
  box-shadow: 0 0 40px rgba(63,207,196,0.24), 0 4px 24px rgba(0,0,0,0.22) !important;
  transition: transform 180ms ease, box-shadow 180ms ease !important;
  font-family: 'Inter', sans-serif !important; font-size: 0.95rem !important;
}
.stButton > button:hover:not(:disabled) {
  transform: scale(1.025) !important;
  box-shadow: 0 0 64px rgba(63,207,196,0.40), 0 8px 32px rgba(0,0,0,0.24) !important;
}
.stButton > button:disabled { opacity: 0.44 !important; box-shadow: none !important; cursor: not-allowed !important; }
.stButton > button[kind="secondary"] {
  background: rgba(223,240,226,0.07) !important;
  border: 1px solid var(--line) !important;
  color: var(--text) !important; box-shadow: none !important;
}
.stButton > button[kind="secondary"]:hover:not(:disabled) {
  background: rgba(63,207,196,0.12) !important; border-color: var(--line-b) !important;
}
/* Landing CTA — bigger, breathing glow */
.bm-cta .stButton > button {
  min-height: 64px !important; font-size: 1.08rem !important;
  padding: 0 40px !important; border-radius: 50px 18px 50px 18px !important;
  animation: ctaBreathe 3.4s ease-in-out infinite !important;
}

/* ── Inputs ── */
.stTextInput > div > div > input {
  min-height: 52px !important; border-radius: 34px 10px 34px 10px !important;
  background: rgba(2,10,5,0.44) !important; border: 1px solid var(--line) !important;
  color: var(--text) !important; font-size: 1.0rem !important; padding: 0 20px !important;
}
.stTextInput > div > div > input::placeholder { color: rgba(223,240,226,0.34) !important; }
.stTextInput > div > div { border: none !important; box-shadow: none !important; }
.stTextInput label { display: none !important; }
.stTextArea > div > div > textarea {
  border-radius: 20px 8px 20px 8px !important;
  background: rgba(3,12,6,0.56) !important; border: 1px solid var(--line) !important;
  color: var(--text) !important; padding: 14px !important; line-height: 1.5 !important;
}
.stTextArea > div > div > textarea:focus { border-color: rgba(63,207,196,0.60) !important; }
.stTextArea label { color: var(--text) !important; font-weight: 700 !important; }

/* ── Checkbox ── */
.stCheckbox > label {
  display: flex !important; align-items: flex-start !important; gap: 12px !important;
  padding: 14px 16px !important;
  border: 1px solid rgba(200,151,61,0.28) !important;
  border-radius: 24px 10px 24px 10px !important;
  background: rgba(200,151,61,0.07) !important;
}
.stCheckbox span { color: var(--text) !important; font-weight: 680 !important; }

/* ── Misc ── */
hr { border-color: var(--line) !important; margin: 20px 0 !important; }
.stCode { border-radius: 20px 8px 20px 8px !important; }
.bm-resource {
  display: block; padding: 12px; margin-bottom: 8px;
  border: 1px solid var(--line); border-radius: 18px 8px 18px 8px;
  background: rgba(223,240,226,0.05); text-decoration: none;
  transition: border-color 160ms, background 160ms;
}
.bm-resource:hover { border-color: var(--line-b); background: rgba(63,207,196,0.08); }
.bm-rtitle { font-size: 0.96rem; font-weight: 600; color: var(--text); display: block; }
.bm-rdesc  { font-size: 0.82rem; color: var(--muted); display: block; margin-top: 3px; }

/* ── Keyframes ── */
@keyframes ctaBreathe {
  0%,100% { box-shadow: 0 0 48px rgba(63,207,196,0.30), 0 0 96px rgba(63,207,196,0.12), 0 8px 28px rgba(0,0,0,0.28); }
  50%     { box-shadow: 0 0 80px rgba(63,207,196,0.55), 0 0 160px rgba(63,207,196,0.24), 0 12px 40px rgba(0,0,0,0.34); }
}
@keyframes spiralTurn {
  from { transform: rotate(0deg) scale(1); opacity: 0.78; }
  50%  { transform: rotate(180deg) scale(1.04); opacity: 0.62; }
  to   { transform: rotate(360deg) scale(1); opacity: 0.78; }
}
@keyframes ringPulse { 0%,100%{opacity:0.14} 50%{opacity:0.38} }
@keyframes drawCycle  { 0%{stroke-dashoffset:1500;opacity:0} 30%{stroke-dashoffset:0;opacity:1} 65%{stroke-dashoffset:0;opacity:1} 100%{stroke-dashoffset:1500;opacity:0.10} }
@keyframes drawCycleS { 0%{stroke-dashoffset:800;opacity:0}  30%{stroke-dashoffset:0;opacity:.88} 65%{stroke-dashoffset:0;opacity:.88} 100%{stroke-dashoffset:800;opacity:0.10} }
@keyframes drawCycleXS{ 0%{stroke-dashoffset:500;opacity:0}  30%{stroke-dashoffset:0;opacity:.80} 65%{stroke-dashoffset:0;opacity:.80} 100%{stroke-dashoffset:500;opacity:0.10} }
@keyframes spokeCycle { 0%{stroke-dashoffset:250;opacity:0} 25%{stroke-dashoffset:0;opacity:1} 65%{stroke-dashoffset:0;opacity:1} 100%{stroke-dashoffset:250;opacity:0} }
@keyframes petalBloom { 0%{opacity:0;transform:scale(0)} 28%{opacity:.52;transform:scale(1)} 72%{opacity:.52;transform:scale(1)} 100%{opacity:0;transform:scale(0)} }
@keyframes dotBreathe { from{transform:scale(0.90)} to{transform:scale(1.18)} }
@keyframes fadeInUp   { from{opacity:0;transform:translateY(20px)} to{opacity:1;transform:translateY(0)} }
@keyframes orgItem {
  0%    { opacity:0; transform:translateY(10px); }
  4%    { opacity:1; transform:translateY(0);    }
  85%   { opacity:1; transform:translateY(0);    }
  92%   { opacity:0; transform:translateY(-8px); }
  100%  { opacity:0; transform:translateY(-8px); }
}

/* ── Landing page ── */
.bm-landing-badge {
  display:inline-flex; align-items:center; padding:6px 16px;
  border:1px solid rgba(63,207,196,0.32); border-radius:999px;
  background:rgba(63,207,196,0.08); color:#3fcfc4;
  font-size:0.78rem; font-weight:760; letter-spacing:0.12em; text-transform:uppercase;
  animation: fadeInUp 0.6s ease-out 0.2s both;
}
.bm-landing-title {
  margin: 8px 0;
  font-size: clamp(3.2rem,7vw,6.4rem); font-weight:820; line-height:0.94; letter-spacing:-0.03em;
  background: linear-gradient(135deg,#dff0e2 18%,#3fcfc4 55%,#c8973d 100%);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
  animation: fadeInUp 0.7s ease-out 0.4s both;
}
.bm-landing-tagline {
  margin:0; font-size:clamp(1.0rem,2vw,1.45rem);
  color:rgba(223,240,226,0.64); line-height:1.55; font-style:italic; max-width:440px;
  animation: fadeInUp 0.7s ease-out 1.1s both;
}
.bm-org-cycle { position:relative; min-height:70px; display:flex; align-items:center; overflow:hidden; }
.bm-org-item  { position:absolute; opacity:0; padding:10px 18px; border-left:2px solid rgba(63,207,196,0.45); }
.bm-org-name  { color:#3fcfc4; font-size:1.04rem; font-weight:740; display:block; }
.bm-org-trait { color:rgba(223,240,226,0.64); font-size:0.86rem; }
.bm-stats { display:flex; gap:36px; animation:fadeInUp 0.6s ease-out 1.65s both; }
.bm-stat  { display:flex; flex-direction:column; gap:2px; }
.bm-stat strong { color:#dff0e2; font-size:1.55rem; font-weight:800; line-height:1; }
.bm-stat span   { color:rgba(223,240,226,0.64); font-size:0.78rem; font-weight:580; letter-spacing:0.04em; }

@media (max-width:760px) {
  .bm-grid3,.bm-grid4 { grid-template-columns:1fr !important; }
  .bm-grid2 { grid-template-columns:1fr !important; }
  .bm-timeline { grid-template-columns:repeat(4,1fr); }
  .bm-ctx { grid-template-columns:repeat(2,1fr); }
  .bm-stats { gap:20px; }
}
</style>
"""

# ══════════════════════════════════════════════════════════════════════════════
# SVG ORGANISM — CSS-animated (mirrors React's Framer Motion version)
# ══════════════════════════════════════════════════════════════════════════════

def _organism_svg():
    spokes = ""
    for i in range(24):
        a = (i / 24) * math.pi * 2
        bold = (i % 4 == 0)
        r2 = 272 if i % 4 == 0 else (214 if i % 2 == 0 else 152)
        x1 = 300 + math.cos(a) * 40;  y1 = 300 + math.sin(a) * 40
        x2 = 300 + math.cos(a) * r2;  y2 = 300 + math.sin(a) * r2
        op = 0.40 if bold else 0.14;   sw = 1.5 if bold else 0.6
        delay = 0.5 + i * 0.022
        spokes += (
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="rgba(63,207,196,{op})" stroke-width="{sw}" '
            f'stroke-dasharray="250" style="animation:spokeCycle 11s ease-in-out infinite;animation-delay:{delay:.2f}s"/>'
        )

    petals = ""
    for i in range(8):
        a = (i / 8) * math.pi * 2
        cx = 300 + math.cos(a) * 214;  cy = 300 + math.sin(a) * 214
        rot = (a * 180) / math.pi + 90;  delay = 1.6 + i * 0.1
        petals += (
            f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="12" ry="30" '
            f'transform="rotate({rot:.1f},{cx:.1f},{cy:.1f})" '
            f'stroke="rgba(110,214,136,0.52)" stroke-width="1.4" fill="none" '
            f'filter="url(#bg)" '
            f'style="animation:petalBloom 7s ease-in-out infinite;animation-delay:{delay:.2f}s"/>'
        )

    hexagons = ""
    for i in range(6):
        a = (i / 6) * math.pi * 2
        hcx = 300 + math.cos(a) * 152;  hcy = 300 + math.sin(a) * 152
        pts = " ".join(f"{hcx+math.cos((j/6)*math.pi*2)*13:.1f},{hcy+math.sin((j/6)*math.pi*2)*13:.1f}" for j in range(6))
        delay = 1.9 + i * 0.12
        hexagons += (
            f'<polygon points="{pts}" stroke="rgba(63,207,196,0.44)" stroke-width="1.1" fill="none" '
            f'style="animation:petalBloom 6s ease-in-out infinite;animation-delay:{delay:.2f}s"/>'
            f'<circle cx="{hcx:.1f}" cy="{hcy:.1f}" r="3" fill="rgba(63,207,196,0.65)" filter="url(#bg)" '
            f'style="animation:petalBloom 6s ease-in-out infinite;animation-delay:{delay+0.2:.2f}s"/>'
        )

    mData = [
        (300+272*math.cos(0.3), 300+272*math.sin(0.3), 0.72, 55),
        (300+272*math.cos(1.5), 300+272*math.sin(1.5), 1.88, 46),
        (300+272*math.cos(2.8), 300+272*math.sin(2.8), 2.42, 60),
        (300+272*math.cos(4.2), 300+272*math.sin(4.2), 4.72, 42),
        (300+272*math.cos(5.4), 300+272*math.sin(5.4), 5.12, 50),
        (300+272*math.cos(3.6), 300+272*math.sin(3.6), 3.20, 38),
    ]
    mycelium = ""
    for idx, (sx, sy, angle, ln) in enumerate(mData):
        ex = sx + math.cos(angle) * ln;  ey = sy + math.sin(angle) * ln
        delay = 2.5 + idx * 0.18
        mycelium += (
            f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" '
            f'stroke="rgba(155,123,196,0.70)" stroke-width="1.4" stroke-linecap="round" '
            f'stroke-dasharray="80" style="animation:spokeCycle 5.5s ease-in-out infinite;animation-delay:{delay:.2f}s"/>'
            f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="4.5" fill="rgba(155,123,196,0.80)" filter="url(#bg)" '
            f'style="animation:petalBloom 5.5s ease-in-out infinite;animation-delay:{delay:.2f}s"/>'
        )

    dots_data = [
        (300,300,9,  "rgba(63,207,196,0.95)","url(#sg)","dotBreathe 3.0s ease-in-out infinite alternate;animation-delay:0.60s"),
        (322,300,5,  "rgba(63,207,196,0.85)","url(#bg)","dotBreathe 2.5s ease-in-out infinite alternate;animation-delay:0.85s"),
        (300,344,5,  "rgba(200,151,61,0.85)","url(#bg)","dotBreathe 2.5s ease-in-out infinite alternate;animation-delay:1.00s"),
        (229,300,5,  "rgba(155,123,196,0.85)","url(#bg)","dotBreathe 2.5s ease-in-out infinite alternate;animation-delay:1.15s"),
        (300,185,5,  "rgba(63,207,196,0.85)","url(#bg)","dotBreathe 2.5s ease-in-out infinite alternate;animation-delay:1.30s"),
        (486,300,5,  "rgba(200,151,61,0.85)","url(#bg)","dotBreathe 2.5s ease-in-out infinite alternate;animation-delay:1.45s"),
    ]
    dots = "".join(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" filter="{flt}" style="animation:{anim}"/>'
        for cx,cy,r,fill,flt,anim in dots_data
    )

    return f"""
<svg viewBox="0 0 600 600" fill="none" xmlns="http://www.w3.org/2000/svg"
     style="width:100%;height:100%;animation:spiralTurn 90s linear infinite">
  <defs>
    <filter id="bg" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="5" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="sg" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur stdDeviation="9" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <circle cx="300" cy="300" r="290" fill="rgba(4,12,6,0.50)"/>
  <circle cx="300" cy="300" r="272" stroke="rgba(63,207,196,0.22)" stroke-width="1.1" stroke-dasharray="5 11" fill="none" style="animation:ringPulse 5s ease-in-out infinite"/>
  <circle cx="300" cy="300" r="214" stroke="rgba(155,123,196,0.18)" stroke-width="0.75" stroke-dasharray="4 9" fill="none" style="animation:ringPulse 6.8s ease-in-out infinite;animation-delay:0.4s"/>
  <circle cx="300" cy="300" r="152" stroke="rgba(63,207,196,0.12)" stroke-width="0.75" stroke-dasharray="3 7" fill="none" style="animation:ringPulse 8.6s ease-in-out infinite;animation-delay:0.8s"/>
  {spokes}
  <path d="M300 300 A22 22 0 0 1 322 300 A44 44 0 0 1 300 344 A71 71 0 0 1 229 300 A115 115 0 0 1 300 185 A186 186 0 0 1 486 300 A301 301 0 0 1 300 601"
        stroke="rgba(63,207,196,0.94)" stroke-width="4.8" stroke-linecap="round" fill="none" filter="url(#sg)"
        stroke-dasharray="1500" style="animation:drawCycle 14s ease-in-out infinite;animation-delay:0.65s"/>
  <path d="M300 300 A14 14 0 0 0 286 300 A28 28 0 0 0 300 272 A45 45 0 0 0 345 300 A73 73 0 0 0 300 373 A118 118 0 0 0 182 300"
        stroke="rgba(200,151,61,0.88)" stroke-width="3.2" stroke-linecap="round" fill="none" filter="url(#bg)"
        stroke-dasharray="800" style="animation:drawCycleS 11.5s ease-in-out infinite;animation-delay:1.4s"/>
  <path d="M300 300 A8 8 0 0 1 308 300 A16 16 0 0 1 300 316 A26 26 0 0 1 274 300 A42 42 0 0 1 300 258 A68 68 0 0 1 368 300"
        stroke="rgba(155,123,196,0.80)" stroke-width="2.4" stroke-linecap="round" fill="none" filter="url(#bg)"
        stroke-dasharray="500" style="animation:drawCycleXS 9s ease-in-out infinite;animation-delay:2.2s"/>
  {petals}
  {hexagons}
  {mycelium}
  {dots}
</svg>"""

# ══════════════════════════════════════════════════════════════════════════════
# HTML BUILDERS
# ══════════════════════════════════════════════════════════════════════════════

def _topbar_html(stage):
    status = '<span class="bm-pill">● Online</span>'
    return (
        f'<div class="bm-topbar">'
        f'<div><span class="bm-brand">BioMimetix AI</span>'
        f'<p class="bm-tagline">AI compass for hands-on biomimicry exploration</p></div>'
        f'<div style="display:flex;align-items:center;gap:10px">{status}</div>'
        f'</div>'
    )

def _timeline_html(stage):
    items = ""
    for i,(icon,name) in enumerate(zip(STEP_ICONS, STEP_NAMES)):
        s = i + 1
        cls = "bm-tstep active" if s == stage else ("bm-tstep done" if s < stage else "bm-tstep")
        num = icon if s < stage else str(s)
        items += f'<div class="{cls}"><div class="bm-tstep-n">{num}</div><small>{name}</small></div>'
    return f'<div class="bm-timeline">{items}</div>'

def _context_html(product, fn, organism, principle):
    slots = [("🔬 PRODUCT", product), ("⚙️ FUNCTION", fn), ("🌿 ORGANISM", organism), ("🧬 PRINCIPLE", principle)]
    cards = "".join(
        f'<div class="bm-ctx-card"><span class="bm-ctx-lbl">{lbl}</span>'
        f'<strong class="bm-ctx-val">{(val or "—")[:38]}</strong></div>'
        for lbl, val in slots
    )
    return f'<div class="bm-ctx">{cards}</div>'

def _step_header(icon, title, desc):
    return (
        f'<div class="bm-step-header">'
        f'<div class="bm-icon-bubble">{icon}</div>'
        f'<h1 class="bm-step-title">{title}</h1>'
        f'<p class="bm-step-desc">{desc}</p>'
        f'</div>'
    )

def _choice_card(label, title, body, selected=False, tag=""):
    cls = "bm-card sel" if selected else "bm-card"
    tag_html = '<span class="bm-card-tag">✓ Selected</span>' if selected else (f'<span class="bm-card-tag">{tag}</span>' if tag else "")
    return (
        f'<div class="{cls}">'
        f'<span class="bm-lbl">{label}</span>'
        f'<strong class="bm-card-title">{title}</strong>'
        f'<p class="bm-card-body">{body}</p>'
        f'{tag_html}</div>'
    )

def _show_image(image_info, caption=""):
    if not image_info:
        return
    url = str(image_info.get("image_url", ""))
    if not url:
        return
    try:
        if url.startswith("http"):
            st.image(url, caption=caption, use_container_width=True)
        else:
            path = Path(url)
            if not path.exists():
                return
            if path.suffix.lower() == ".svg":
                b64 = base64.b64encode(path.read_bytes()).decode()
                html = f'<img src="data:image/svg+xml;base64,{b64}" style="width:100%;border-radius:20px 8px 20px 8px">'
                if caption:
                    html += f'<p style="font-size:0.78em;color:rgba(223,240,226,0.64);margin-top:6px">{caption}</p>'
                st.markdown(html, unsafe_allow_html=True)
            else:
                st.image(str(path), caption=caption, use_container_width=True)
    except Exception:
        pass

def _organism_cycle_html():
    n = len(_ORGANISMS)
    total = n * 3.2
    items = ""
    for i, (name, trait) in enumerate(_ORGANISMS):
        delay = i * 3.2
        items += (
            f'<div class="bm-org-item" style="animation:orgItem {total:.1f}s linear infinite;animation-delay:{delay:.1f}s">'
            f'<span class="bm-org-name">{name}</span>'
            f'<span class="bm-org-trait">{trait}</span>'
            f'</div>'
        )
    return f'<div class="bm-org-cycle" style="animation:fadeInUp 0.5s ease-out 1.4s both">{items}</div>'

# ══════════════════════════════════════════════════════════════════════════════
# STREAMLIT APP ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="BioMimetix AI", page_icon="🌿", layout="wide")
st.markdown(_FONTS, unsafe_allow_html=True)
st.markdown(_CSS, unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────

for _k, _v in {
    "stage": 0, "product": "", "product_image": None,
    "components": [], "selected_function": "",
    "biomimicry_options": [], "selected_organism_data": None,
    "abstractions": None, "selected_principle": None,
    "concepts": [], "selected_concept": None,
    "final_prompt": "",
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

_stage = st.session_state.stage

# ══════════════════════════════════════════════════════════════════════════════
# LANDING PAGE (stage 0)
# ══════════════════════════════════════════════════════════════════════════════

if _stage == 0:
    svg_html = _organism_svg()
    cycle_html = _organism_cycle_html()
    left, right = st.columns([1, 1], gap="large")
    with left:
        st.markdown(
            f'''<div style="display:flex;flex-direction:column;gap:24px;padding:clamp(20px,4vw,60px) 0;animation:fadeInUp 1s ease-out both">
  <span class="bm-landing-badge">Biomimicry × Industrial Design AI</span>
  <h1 class="bm-landing-title">BioMimetix AI</h1>
  <p class="bm-landing-tagline">4 billion years of R&amp;D.&ensp;Zero patents.</p>
  {cycle_html}
  <div class="bm-stats">
    <div class="bm-stat"><strong>3M+</strong><span>species catalogued</span></div>
    <div class="bm-stat"><strong>4B yr</strong><span>of evolution</span></div>
    <div class="bm-stat"><strong>0</strong><span>patents held</span></div>
  </div>
</div>''',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="bm-cta">', unsafe_allow_html=True)
        if st.button("🌿  Enter the Forest  →", type="primary", key="enter_forest"):
            st.session_state.stage = 1
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:center;min-height:520px;opacity:0.78">{svg_html}</div>',
            unsafe_allow_html=True,
        )
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# SHARED CHROME (stages 1-8)
# ══════════════════════════════════════════════════════════════════════════════

_new_cycle_col, _spacer = st.columns([6, 1])
with _spacer:
    if st.button("↺ New cycle", type="secondary", key="new_cycle_top"):
        for _k in list(st.session_state.keys()):
            del st.session_state[_k]
        st.rerun()

st.markdown(_topbar_html(_stage), unsafe_allow_html=True)
st.markdown(_timeline_html(_stage), unsafe_allow_html=True)
st.markdown(_context_html(
    st.session_state.product,
    st.session_state.selected_function,
    (st.session_state.selected_organism_data or {}).get("organism", ""),
    (st.session_state.selected_principle or {}).get("title", ""),
), unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Product Analyse
# ══════════════════════════════════════════════════════════════════════════════

if _stage == 1:
    st.markdown('<div class="bm-panel">', unsafe_allow_html=True)
    st.markdown(_step_header("🔬", "Product Analyse",
        "Nature has solved every engineering problem you face. Name your product — we find its biological twin."),
        unsafe_allow_html=True)

    _ex_cols = st.columns(5)
    for _i, _ex in enumerate(["Helmet", "Running shoe", "Drone blade", "Bicycle frame", "Water bottle"]):
        with _ex_cols[_i]:
            if st.button(_ex, key=f"ex_{_i}", type="secondary"):
                st.session_state["_product_input"] = _ex
                st.rerun()

    _product_name = st.text_input(
        "Product name",
        value=st.session_state.get("_product_input", ""),
        placeholder="e.g. Helmet, running shoe, drone blade…",
        label_visibility="collapsed",
    )
    if st.button("🔬  Analyze product", type="primary", disabled=not (_product_name or "").strip()):
        with st.spinner("Deconstructing product and fetching reference image…"):
            _components = deconstruct_product(DeconstructReq(product=_product_name.strip()))
            _prod_image = product_image_search(_product_name.strip())
        if _components:
            st.session_state.product = _product_name.strip()
            st.session_state.components = _components
            st.session_state.product_image = _prod_image
            if "_product_input" in st.session_state:
                del st.session_state["_product_input"]
            st.session_state.stage = 2
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Functions
# ══════════════════════════════════════════════════════════════════════════════

elif _stage == 2:
    st.markdown('<div class="bm-panel">', unsafe_allow_html=True)
    st.markdown(_step_header("⚙️", f"{st.session_state.product}: Functions",
        "AI-suggested breakdown. Select the function you want to redesign through nature."),
        unsafe_allow_html=True)

    _img_col, _fn_col = st.columns([1, 2], gap="large")
    with _img_col:
        if st.session_state.product_image:
            _show_image(st.session_state.product_image, caption=st.session_state.product)

    with _fn_col:
        _comps = st.session_state.components
        _per_row = min(3, len(_comps))
        _rows = [_comps[i:i+_per_row] for i in range(0, len(_comps), _per_row)]
        for _row in _rows:
            _cols = st.columns(len(_row))
            for _j, (_item, _col) in enumerate(zip(_row, _cols)):
                with _col:
                    _sel = st.session_state.selected_function == _item["function"]
                    st.markdown(_choice_card(_item["component"], _item["function"], "", selected=_sel), unsafe_allow_html=True)
                    if st.button("✓ Selected" if _sel else "Select",
                                 key=f"fn_{id(_item)}_{_item['function'][:10]}",
                                 type="primary" if _sel else "secondary",
                                 use_container_width=True):
                        st.session_state.selected_function = _item["function"]
                        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
    if st.button("🌿  Start Nature Quest", type="primary", disabled=not st.session_state.selected_function):
        with st.spinner(f"Finding biological inspiration for '{st.session_state.selected_function}'…"):
            _bio_opts = biomimetic_search(BiomimicryReq(
                product=st.session_state.product,
                function=st.session_state.selected_function,
            ))
        if _bio_opts:
            st.session_state.biomimicry_options = _bio_opts
            st.session_state.selected_organism_data = None
            st.session_state.stage = 3
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Biomimicry: Nature Quest
# ══════════════════════════════════════════════════════════════════════════════

elif _stage == 3:
    st.markdown('<div class="bm-panel">', unsafe_allow_html=True)
    st.markdown(_step_header("🌿", "Biomimicry: Nature Quest",
        "Choose an organism, explore its resources, then abstract the principle."),
        unsafe_allow_html=True)

    _options = st.session_state.biomimicry_options
    _sel_org = (st.session_state.selected_organism_data or {}).get("organism", "")
    _org_cols = st.columns(min(5, len(_options)))
    for _i, _opt in enumerate(_org_cols):
        with _opt:
            _o = _options[_i]
            _active = _sel_org == _o["organism"]
            if st.button(_o["organism"], key=f"org_{_i}",
                         type="primary" if _active else "secondary",
                         use_container_width=True):
                st.session_state.selected_organism_data = _options[_i]
                st.rerun()

    _org_data = st.session_state.selected_organism_data
    if _org_data:
        st.divider()
        _org_name = _org_data["organism"]
        _img_c, _info_c = st.columns([1, 2], gap="large")
        with _img_c:
            with st.spinner(f"Loading image for {_org_name}…"):
                _org_img = biodiversity_reference(ReferenceImageReq(
                    organism=_org_name,
                    function=st.session_state.selected_function,
                ))
            _cap = _org_name + (f" — {_org_img.get('source', '')}" if _org_img else "")
            _show_image(_org_img, caption=_cap)

        with _info_c:
            st.markdown(f'<strong style="color:#dff0e2;font-size:1.4rem;font-weight:800">{_org_name}</strong>', unsafe_allow_html=True)
            st.write(_org_data.get("rationale", ""))
            _pack = _org_data.get("exploration_pack", {})
            _watch = _pack.get("watch", [])
            if _watch:
                st.markdown('**📺 Watch**')
                for _w in _watch:
                    _wu = _w.get("url", "#")
                    _wt = _w.get("title", "")
                    _wd = _w.get("description", "")
                    st.markdown(
                        f'<a class="bm-resource" href="{_wu}" target="_blank">'
                        f'<span class="bm-rtitle">{_wt}</span>'
                        f'<span class="bm-rdesc">{_wd}</span></a>',
                        unsafe_allow_html=True)
            _read = _pack.get("read", [])
            if _read:
                st.markdown('**📖 Read**')
                for _r in _read:
                    _ru = _r.get("url", "#")
                    _rt = _r.get("title", "")
                    _rd = _r.get("description", "")
                    st.markdown(
                        f'<a class="bm-resource" href="{_ru}" target="_blank">'
                        f'<span class="bm-rtitle">{_rt}</span>'
                        f'<span class="bm-rdesc">{_rd}</span></a>',
                        unsafe_allow_html=True)
            _act = _pack.get("act", {})
            if _act:
                with st.expander(f"🔭 Nature Quest — {_act.get('title', 'Act')}", expanded=True):
                    st.write(_act.get("description", ""))
                    for _c in _act.get("checklist", []):
                        st.markdown(f"- {_c}")

    st.markdown('</div>', unsafe_allow_html=True)
    if _org_data:
        _gate = st.checkbox("I have explored these resources and made my own observations.", key="gate_explore")
        if st.button("🔬  Abstract the principle", type="primary", disabled=not _gate):
            with st.spinner(f"Abstracting principles from {_org_data['organism']}…"):
                _abstractions = principle_abstraction(AbstractReq(
                    product=st.session_state.product,
                    function=st.session_state.selected_function,
                    organism=_org_data["organism"],
                ))
            if _abstractions:
                st.session_state.abstractions = _abstractions
                st.session_state.selected_principle = None
                st.session_state.stage = 4
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Principle Abstraction
# ══════════════════════════════════════════════════════════════════════════════

elif _stage == 4:
    st.markdown('<div class="bm-panel">', unsafe_allow_html=True)
    st.markdown(_step_header("🧬", "Principle Abstraction",
        "Select one abstract principle, then sketch it before ideation becomes available."),
        unsafe_allow_html=True)

    _abstractions = st.session_state.abstractions or {}
    _principles = _abstractions.get("principles", [])
    _sketch_pack = _abstractions.get("sketch_pack", {})

    _pr_rows = [_principles[i:i+3] for i in range(0, len(_principles), 3)]
    for _row in _pr_rows:
        _cols = st.columns(len(_row))
        for _p, _col in zip(_row, _cols):
            with _col:
                _sel = (st.session_state.selected_principle or {}).get("title") == _p["title"]
                st.markdown(_choice_card("PRINCIPLE", _p["title"], _p["principle"], selected=_sel), unsafe_allow_html=True)
                if st.button("✓ Selected" if _sel else "Select",
                             key=f"pr_{_p['title'][:12]}",
                             type="primary" if _sel else "secondary",
                             use_container_width=True):
                    st.session_state.selected_principle = _p
                    st.rerun()

    if _sketch_pack:
        st.divider()
        st.markdown(f'<strong style="color:#3fcfc4">✏️ {_sketch_pack.get("title","Sketching Assignment")}</strong>', unsafe_allow_html=True)
        st.write(f"**Grab pen and paper** — {_sketch_pack.get('prompt', '')}")
        for _c in _sketch_pack.get("checks", []):
            st.markdown(f"- {_c}")

    st.markdown('</div>', unsafe_allow_html=True)
    _sketch_done = st.checkbox("Sketch completed.", key="sketch_done_gate")
    _can_ideate = bool(st.session_state.selected_principle) and _sketch_done
    if st.button("💡  Move to ideation", type="primary", disabled=not _can_ideate):
        with st.spinner("Generating concepts…"):
            _concepts = ideate_concepts(IdeateReq(
                product=st.session_state.product,
                principle=st.session_state.selected_principle["title"],
            ))
        if _concepts:
            st.session_state.concepts = _concepts
            st.session_state.selected_concept = None
            st.session_state.stage = 5
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Ideation
# ══════════════════════════════════════════════════════════════════════════════

elif _stage == 5:
    st.markdown('<div class="bm-panel">', unsafe_allow_html=True)
    st.markdown(_step_header("💡", "Ideation and Creation",
        "Select one concept. Pause to refine what must remain physically testable."),
        unsafe_allow_html=True)

    _concepts = st.session_state.concepts
    _c_rows = [_concepts[i:i+3] for i in range(0, len(_concepts), 3)]
    for _row in _c_rows:
        _cols = st.columns(len(_row))
        for _c, _col in zip(_row, _cols):
            with _col:
                _sel = (st.session_state.selected_concept or {}).get("concept_name") == _c["concept_name"]
                st.markdown(_choice_card("CONCEPT", _c["concept_name"], _c.get("description",""), selected=_sel), unsafe_allow_html=True)
                if st.button("✓ Selected" if _sel else "Select",
                             key=f"concept_{_c['concept_name'][:12]}",
                             type="primary" if _sel else "secondary",
                             use_container_width=True):
                    st.session_state.selected_concept = _c
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
    _refined = st.checkbox("I have mentally refined this concept and identified what should be tested physically.", key="concept_refined_gate")
    _can_prompt = bool(st.session_state.selected_concept) and _refined
    if st.button("🎨  Generate strict 2D prompt", type="primary", disabled=not _can_prompt):
        with st.spinner("Generating image prompt…"):
            _result = generate_prompt(PromptReq(
                product=st.session_state.product,
                concept=st.session_state.selected_concept["concept_name"],
            ))
        if _result:
            st.session_state.final_prompt = _result.get("prompt", "")
            st.session_state.stage = 6
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — 2D Image Prompt
# ══════════════════════════════════════════════════════════════════════════════

elif _stage == 6:
    st.markdown('<div class="bm-panel">', unsafe_allow_html=True)
    st.markdown(_step_header("🎨", "2D Image Prompt",
        "Copy this strict prompt into your external image generator (Midjourney, DALL-E, Stable Diffusion)."),
        unsafe_allow_html=True)
    st.code(st.session_state.final_prompt, language=None)
    st.info("💡 Click the copy icon in the top-right corner of the box above to copy the prompt.")
    st.markdown('</div>', unsafe_allow_html=True)
    _prompt_used = st.checkbox("I have copied or used the prompt externally.", key="prompt_used_gate")
    if st.button("➡️  Continue to 3D pathway", type="primary", disabled=not _prompt_used):
        st.session_state.stage = 7
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# STEP 7 — 3D Model
# ══════════════════════════════════════════════════════════════════════════════

elif _stage == 7:
    st.markdown('<div class="bm-panel">', unsafe_allow_html=True)
    st.markdown(_step_header("🖨️", "3D Model: Printpal Pathway",
        "Convert the clean 2D image into a printable model. The AI stops here; your hands take over."),
        unsafe_allow_html=True)

    _steps_3d = [
        ("Upload",  "Take the single-object 2D image and upload it into Printpal or another image-to-3D tool."),
        ("Inspect", "Rotate the mesh. Look for broken surfaces, impossible overhangs, and lost biological features."),
        ("Export",  "Export an STL. Keep a screenshot of the mesh before slicing."),
        ("Print",   "3D print a small prototype, even if the model is imperfect."),
    ]
    _grid_html = '<div class="bm-grid bm-grid4">' + "".join(
        f'<div class="bm-card"><span class="bm-lbl">STEP {i+1}</span>' +
        f'<strong class="bm-card-title">{t}</strong><p class="bm-card-body">{b}</p></div>'
        for i, (t, b) in enumerate(_steps_3d)
    ) + '</div>'
    st.markdown(_grid_html, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    _stl_done = st.checkbox("I have created or inspected an STL pathway.", key="stl_done_gate")
    if st.button("📋  Evaluate physical result", type="primary", disabled=not _stl_done):
        st.session_state.stage = 8
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# STEP 8 — Evaluate
# ══════════════════════════════════════════════════════════════════════════════

elif _stage == 8:
    st.markdown('<div class="bm-panel">', unsafe_allow_html=True)
    st.markdown(_step_header("📋", "Evaluate",
        "Log what failed. Biomimicry improves when the physical prototype argues back."),
        unsafe_allow_html=True)

    _q1 = st.text_area("How did the translation from nature → AI → physical object fail?",  key="ev_failure",  height=110)
    _q2 = st.text_area("What nuances of the biological organism were lost?",                  key="ev_nuance",   height=110)
    _q3 = st.text_area("Did the 3D print function as expected?",                              key="ev_printfn",  height=110)
    _q4 = st.text_area("What should change in the next iteration?",                           key="ev_nextiter", height=110)
    st.markdown('</div>', unsafe_allow_html=True)

    _all_done = all(len((v or "").strip()) > 8 for v in [_q1, _q2, _q3, _q4])
    if st.button("✅  Finish and start new cycle", type="primary", disabled=not _all_done):
        for _k in list(st.session_state.keys()):
            del st.session_state[_k]
        st.rerun()
    if not _all_done:
        st.caption("Complete every evaluation field to finish.")
