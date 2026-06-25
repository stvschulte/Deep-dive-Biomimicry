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


def _show_image(image_info, caption=""):
    """Render an image from an HTTP URL or a local file (PNG / SVG)."""
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
                html = (
                    f'<img src="data:image/svg+xml;base64,{b64}" '
                    f'style="width:100%;border-radius:10px">'
                )
                if caption:
                    html += f'<p style="font-size:0.78em;color:#9bc;margin-top:4px">{caption}</p>'
                st.markdown(html, unsafe_allow_html=True)
            else:
                st.image(str(path), caption=caption, use_container_width=True)
    except Exception:
        pass


def _card(title, body, selected=False):
    border = "2px solid #3fCFC4" if selected else "1px solid rgba(100,200,150,0.28)"
    return (
        f'<div style="padding:14px;border-radius:10px;background:rgba(7,28,24,0.74);'
        f'border:{border};margin-bottom:10px">'
        f'<strong style="color:#c8ffe8">{title}</strong>'
        f'<br><small style="color:#a0c8b8">{body}</small></div>'
    )


STEP_NAMES = [
    "Product Analyse", "Functions", "Biomimicry",
    "Principles", "Ideation", "2D Image", "3D Model", "Evaluate",
]

# ── Page setup ───────────────────────────────────────────────────────────────

st.set_page_config(page_title="BioMimetix AI", page_icon="🌿", layout="wide")

st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background: linear-gradient(145deg, #020907 0%, #062019 48%, #020b14 100%);
}
[data-testid="stHeader"] { background: transparent; }
section[data-testid="stSidebar"] { background: rgba(5,21,18,0.85); }
h1, h2, h3 { color: #c8ffe8 !important; }
p, li, label, small, .stMarkdown { color: #cce8d8 !important; }
.stButton > button { border-radius: 8px; font-weight: 600; }
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: rgba(7,28,24,0.6);
    border: 1px solid rgba(100,200,150,0.4);
    color: #e8fff1;
    border-radius: 8px;
}
.stCheckbox label { color: #c8ffe8 !important; }
.stProgress > div > div > div { background: #3fCFC4; }
</style>
""", unsafe_allow_html=True)

# ── Session-state defaults ────────────────────────────────────────────────────

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

# ── Header ────────────────────────────────────────────────────────────────────

_hcol1, _hcol2 = st.columns([5, 1])
with _hcol1:
    st.title("🌿 BioMimetix AI")
    st.caption("AI compass for hands-on biomimicry exploration")
with _hcol2:
    st.write("")
    st.write("")
    if st.session_state.stage > 0:
        if st.button("↺ New cycle", use_container_width=True):
            for _k in list(st.session_state.keys()):
                del st.session_state[_k]
            st.rerun()

# ── Progress ──────────────────────────────────────────────────────────────────

_stage = st.session_state.stage
if _stage > 0:
    st.progress(_stage / 8)
    st.caption(f"Step {_stage} / 8 — **{STEP_NAMES[_stage - 1]}**")

# ── Context strip ─────────────────────────────────────────────────────────────

if st.session_state.product:
    _ctx = [f"**Product:** {st.session_state.product}"]
    if st.session_state.selected_function:
        _ctx.append(f"**Function:** {st.session_state.selected_function}")
    if st.session_state.selected_organism_data:
        _ctx.append(f"**Organism:** {st.session_state.selected_organism_data['organism']}")
    if st.session_state.selected_principle:
        _ctx.append(f"**Principle:** {st.session_state.selected_principle['title']}")
    st.markdown(" · ".join(_ctx))

st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# STEP 1 — Product Analyse
# ═════════════════════════════════════════════════════════════════════════════

if _stage == 0:
    st.header("Step 1 — Product Analyse")
    st.write(
        "Nature has already solved every engineering problem you face. "
        "Name your product — we find its biological twin."
    )

    st.caption("Quick picks:")
    _ex_cols = st.columns(5)
    for _i, _ex in enumerate(["Helmet", "Running shoe", "Drone blade", "Bicycle frame", "Water bottle"]):
        with _ex_cols[_i]:
            if st.button(_ex, key=f"ex_{_i}"):
                st.session_state["_product_input"] = _ex

    _product_name = st.text_input(
        "Product name",
        value=st.session_state.get("_product_input", ""),
        placeholder="e.g. Helmet, running shoe, drone blade...",
        label_visibility="collapsed",
    )

    if st.button("🔬 Analyze product", type="primary", disabled=not (_product_name or "").strip()):
        with st.spinner("Deconstructing product and fetching reference image..."):
            _components = deconstruct_product(DeconstructReq(product=_product_name.strip()))
            _prod_image = product_image_search(_product_name.strip())
        if _components:
            st.session_state.product = _product_name.strip()
            st.session_state.components = _components
            st.session_state.product_image = _prod_image
            if "_product_input" in st.session_state:
                del st.session_state["_product_input"]
            st.session_state.stage = 1
            st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# STEP 2 — Product Functions
# ═════════════════════════════════════════════════════════════════════════════

elif _stage == 1:
    st.header(f"Step 2 — {st.session_state.product}: Functions")
    st.write("AI-suggested breakdown. Click a function card to select the one you want to redesign through nature.")

    _img_col, _fn_col = st.columns([1, 2])
    with _img_col:
        if st.session_state.product_image:
            _show_image(st.session_state.product_image, caption=st.session_state.product)

    with _fn_col:
        _comps = st.session_state.components
        _fn_grid = st.columns(min(3, len(_comps)))
        for _i, _item in enumerate(_comps):
            with _fn_grid[_i % 3]:
                _sel = st.session_state.selected_function == _item["function"]
                st.markdown(_card(_item["component"], _item["function"], selected=_sel), unsafe_allow_html=True)
                if st.button(
                    "✓ Selected" if _sel else "Select",
                    key=f"fn_{_i}",
                    type="primary" if _sel else "secondary",
                    use_container_width=True,
                ):
                    st.session_state.selected_function = _item["function"]
                    st.rerun()

    st.write("")
    if st.button("🌿 Start Nature Quest", type="primary", disabled=not st.session_state.selected_function):
        with st.spinner(f"Finding biological inspiration for '{st.session_state.selected_function}'..."):
            _bio_opts = biomimetic_search(BiomimicryReq(
                product=st.session_state.product,
                function=st.session_state.selected_function,
            ))
        if _bio_opts:
            st.session_state.biomimicry_options = _bio_opts
            st.session_state.selected_organism_data = None
            st.session_state.stage = 2
            st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# STEP 3 — Biomimicry: Nature Quest
# ═════════════════════════════════════════════════════════════════════════════

elif _stage == 2:
    st.header("Step 3 — Biomimicry: Nature Quest")
    st.write("Choose one organism, explore its resources, then abstract the principle.")

    _options = st.session_state.biomimicry_options
    _sel_org = (st.session_state.selected_organism_data or {}).get("organism", "")

    _org_cols = st.columns(min(5, len(_options)))
    for _i, _opt in enumerate(_options):
        with _org_cols[_i]:
            _is_sel = _sel_org == _opt["organism"]
            if st.button(
                _opt["organism"],
                key=f"org_select_{_i}",
                type="primary" if _is_sel else "secondary",
                use_container_width=True,
            ):
                st.session_state.selected_organism_data = _opt
                st.rerun()

    _org_data = st.session_state.selected_organism_data
    if _org_data:
        st.divider()
        _org_name = _org_data["organism"]

        _img_c, _info_c = st.columns([1, 2])
        with _img_c:
            with st.spinner(f"Loading image for {_org_name}..."):
                _org_img = biodiversity_reference(ReferenceImageReq(
                    organism=_org_name,
                    function=st.session_state.selected_function,
                ))
            _caption = _org_name + (f" — {_org_img.get('source', '')}" if _org_img else "")
            _show_image(_org_img, caption=_caption)

        with _info_c:
            st.subheader(_org_name)
            st.write(_org_data.get("rationale", ""))

            _pack = _org_data.get("exploration_pack", {})
            _watch = _pack.get("watch", [])
            if _watch:
                st.markdown("**📺 Watch**")
                for _w in _watch:
                    st.markdown(f"- [{_w['title']}]({_w['url']}) — *{_w.get('description', '')}*")

            _read = _pack.get("read", [])
            if _read:
                st.markdown("**📖 Read**")
                for _r in _read:
                    st.markdown(f"- [{_r['title']}]({_r['url']}) — *{_r.get('description', '')}*")

            _act = _pack.get("act", {})
            if _act:
                with st.expander(f"🔭 Nature Quest — {_act.get('title', 'Act')}", expanded=True):
                    st.write(_act.get("description", ""))
                    for _c in _act.get("checklist", []):
                        st.markdown(f"- {_c}")

        st.divider()
        _gate = st.checkbox(
            "I have explored these resources and made my own observations.",
            key=f"gate_explore_{_org_name}",
        )
        if st.button("🔬 Abstract the principle", type="primary", disabled=not _gate):
            with st.spinner(f"Abstracting principles from {_org_name}..."):
                _abstractions = principle_abstraction(AbstractReq(
                    product=st.session_state.product,
                    function=st.session_state.selected_function,
                    organism=_org_name,
                ))
            if _abstractions:
                st.session_state.abstractions = _abstractions
                st.session_state.selected_principle = None
                st.session_state.stage = 3
                st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# STEP 4 — Principle Abstraction + Sketch Gate
# ═════════════════════════════════════════════════════════════════════════════

elif _stage == 3:
    st.header("Step 4 — Principle Abstraction")
    st.write("Select one abstract principle, then sketch it before ideation becomes available.")

    _abstractions = st.session_state.abstractions or {}
    _principles = _abstractions.get("principles", [])
    _sketch_pack = _abstractions.get("sketch_pack", {})

    _pr_cols = st.columns(min(3, len(_principles)))
    for _i, _p in enumerate(_principles):
        with _pr_cols[_i]:
            _sel = (st.session_state.selected_principle or {}).get("title") == _p["title"]
            st.markdown(_card(_p["title"], _p["principle"], selected=_sel), unsafe_allow_html=True)
            if st.button(
                "✓ Selected" if _sel else "Select",
                key=f"pr_{_i}",
                type="primary" if _sel else "secondary",
                use_container_width=True,
            ):
                st.session_state.selected_principle = _p
                st.rerun()

    st.divider()
    if _sketch_pack:
        st.subheader("✏️ " + _sketch_pack.get("title", "Sketching Assignment"))
        st.markdown(f"**Grab pen and paper** — {_sketch_pack.get('prompt', '')}")
        for _c in _sketch_pack.get("checks", []):
            st.markdown(f"- {_c}")
        st.write("")

    _sketch_done = st.checkbox("Sketch completed.", key="sketch_done_gate")
    _can_ideate = bool(st.session_state.selected_principle) and _sketch_done
    if st.button("💡 Move to ideation", type="primary", disabled=not _can_ideate):
        with st.spinner("Generating concepts..."):
            _concepts = ideate_concepts(IdeateReq(
                product=st.session_state.product,
                principle=st.session_state.selected_principle["title"],
            ))
        if _concepts:
            st.session_state.concepts = _concepts
            st.session_state.selected_concept = None
            st.session_state.stage = 4
            st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# STEP 5 — Ideation
# ═════════════════════════════════════════════════════════════════════════════

elif _stage == 4:
    st.header("Step 5 — Ideation and Creation")
    st.write("Select one concept. Before visualization, pause and refine what must remain physically testable.")

    _concepts = st.session_state.concepts
    _c_cols = st.columns(min(3, len(_concepts)))
    for _i, _c in enumerate(_concepts):
        with _c_cols[_i % 3]:
            _sel = (st.session_state.selected_concept or {}).get("concept_name") == _c["concept_name"]
            st.markdown(_card(_c["concept_name"], _c.get("description", ""), selected=_sel), unsafe_allow_html=True)
            if st.button(
                "✓ Selected" if _sel else "Select",
                key=f"concept_{_i}",
                type="primary" if _sel else "secondary",
                use_container_width=True,
            ):
                st.session_state.selected_concept = _c
                st.rerun()

    st.divider()
    _refined = st.checkbox(
        "I have mentally refined this concept and identified what should be tested physically.",
        key="concept_refined_gate",
    )
    _can_prompt = bool(st.session_state.selected_concept) and _refined
    if st.button("🎨 Generate strict 2D prompt", type="primary", disabled=not _can_prompt):
        with st.spinner("Generating image prompt..."):
            _result = generate_prompt(PromptReq(
                product=st.session_state.product,
                concept=st.session_state.selected_concept["concept_name"],
            ))
        if _result:
            st.session_state.final_prompt = _result.get("prompt", "")
            st.session_state.stage = 5
            st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# STEP 6 — 2D Image Prompt
# ═════════════════════════════════════════════════════════════════════════════

elif _stage == 5:
    st.header("Step 6 — 2D Image Prompt")
    st.write(
        "Copy this strict prompt into your external image generator "
        "(Midjourney, DALL-E, Stable Diffusion). Keep the output clean for 3D conversion."
    )

    st.code(st.session_state.final_prompt, language=None)
    st.info("💡 Click the copy icon in the top-right corner of the box above to copy the prompt.")

    _prompt_used = st.checkbox("I have copied or used the prompt externally.", key="prompt_used_gate")
    if st.button("➡️ Continue to 3D pathway", type="primary", disabled=not _prompt_used):
        st.session_state.stage = 6
        st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# STEP 7 — 3D Model
# ═════════════════════════════════════════════════════════════════════════════

elif _stage == 6:
    st.header("Step 7 — 3D Model: Printpal Pathway")
    st.write("Convert the clean 2D image into a printable model. The AI stops here; your hands take over.")

    _steps_3d = [
        ("Upload", "Take the single-object 2D image and upload it into Printpal or another image-to-3D tool."),
        ("Inspect", "Rotate the mesh. Look for broken surfaces, impossible overhangs, and lost biological features."),
        ("Export", "Export an STL. Keep a screenshot of the mesh before slicing."),
        ("Print", "3D print a small prototype, even if the model is imperfect."),
    ]
    _s3d_cols = st.columns(4)
    for _i, (_t, _tx) in enumerate(_steps_3d):
        with _s3d_cols[_i]:
            st.markdown(
                f'<div style="padding:16px;border-radius:10px;background:rgba(7,28,24,0.74);'
                f'border:1px solid rgba(100,200,150,0.3);min-height:160px">'
                f'<strong style="color:#3fCFC4">{_t}</strong><br><br>'
                f'<small style="color:#a0c8b8">{_tx}</small></div>',
                unsafe_allow_html=True,
            )

    st.divider()
    _stl_done = st.checkbox("I have created or inspected an STL pathway.", key="stl_done_gate")
    if st.button("📋 Evaluate physical result", type="primary", disabled=not _stl_done):
        st.session_state.stage = 7
        st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# STEP 8 — Evaluate
# ═════════════════════════════════════════════════════════════════════════════

elif _stage == 7:
    st.header("Step 8 — Evaluate")
    st.write("Log what failed. Biomimicry improves when the physical prototype argues back.")

    _f  = st.text_area("How did the translation from nature → AI → physical object fail?", key="ev_failure",   height=100)
    _n  = st.text_area("What nuances of the biological organism were lost?",                key="ev_nuance",    height=100)
    _pf = st.text_area("Did the 3D print function as expected?",                            key="ev_printfn",   height=100)
    _ni = st.text_area("What should change in the next iteration?",                         key="ev_nextiter",  height=100)

    _all_done = all(len((v or "").strip()) > 8 for v in [_f, _n, _pf, _ni])
    if st.button("✅ Finish and start new cycle", type="primary", disabled=not _all_done):
        for _k in list(st.session_state.keys()):
            del st.session_state[_k]
        st.rerun()
    if not _all_done:
        st.caption("Complete every evaluation field to finish.")
