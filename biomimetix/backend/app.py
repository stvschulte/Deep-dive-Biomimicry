import base64
from pathlib import Path

import streamlit as st

from core import (
    AbstractReq,
    BackendError,
    BiomimicryReq,
    DeconstructReq,
    IdeateReq,
    PromptReq,
    ReferenceImageReq,
    biodiversity_reference,
    biomimetic_search,
    deconstruct_product,
    generate_prompt,
    get_health_status,
    image_dir,
    ideate_concepts,
    principle_abstraction,
    product_image_search,
)


STEP_NAMES = [
    "Product Analyse",
    "Product Functions",
    "Biomimicry",
    "Principle Abstraction",
    "Ideation",
    "2D Image",
    "3D Model",
    "Evaluate",
]


def image_path_from_url(url):
    if not url:
        return ""
    if url.startswith("/generated_images/"):
        return str(image_dir / url.removeprefix("/generated_images/"))
    return url


def show_image(image_info, caption=""):
    if not image_info:
        return
    url = image_path_from_url(str(image_info.get("image_url", "")))
    if not url:
        return
    if url.startswith("http"):
        st.image(url, caption=caption, width="stretch")
        return

    path = Path(url)
    if not path.exists():
        return
    if path.suffix.lower() == ".svg":
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        st.markdown(
            f'<img src="data:image/svg+xml;base64,{b64}" style="width:100%;border-radius:10px">',
            unsafe_allow_html=True,
        )
        if caption:
            st.caption(caption)
    else:
        st.image(str(path), caption=caption, width="stretch")


def run_backend(action, *args):
    try:
        return action(*args)
    except BackendError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"Something went wrong: {exc}")
    return None


def card(title, body, active=False):
    border = "#7fffd0" if active else "rgba(151,255,207,0.22)"
    return f"""
    <div class="choice-card {'active' if active else ''}" style="border-color:{border}">
      <strong>{title}</strong>
      <p>{body}</p>
    </div>
    """


def reset_app():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


def init_state():
    defaults = {
        "stage": 0,
        "product": "",
        "product_image": None,
        "components": [],
        "selected_function": "",
        "biomimicry_options": [],
        "selected_organism": None,
        "selected_organism_image": None,
        "abstractions": None,
        "selected_principle": None,
        "concepts": [],
        "selected_concept": None,
        "final_prompt": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


st.set_page_config(page_title="BioMimetix AI", page_icon="🌿", layout="wide")
init_state()

st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] {
      background:
        radial-gradient(ellipse at 50% -10%, rgba(127,255,208,.24), transparent 42%),
        radial-gradient(ellipse at 92% 18%, rgba(157,231,111,.16), transparent 34%),
        radial-gradient(ellipse at 12% 70%, rgba(64,160,198,.18), transparent 38%),
        linear-gradient(145deg, #020907 0%, #062019 48%, #020b14 100%);
    }
    [data-testid="stHeader"] { background: transparent; }
    section[data-testid="stSidebar"] { background: rgba(5, 21, 18, .88); }
    h1, h2, h3 { color: #e8fff1 !important; }
    p, li, label, .stMarkdown { color: rgba(232,255,241,.78) !important; }
    .hero {
      padding: 28px 30px;
      border: 1px solid rgba(151,255,207,.18);
      border-radius: 22px;
      background: linear-gradient(145deg, rgba(8,32,28,.86), rgba(6,23,29,.76));
      box-shadow: 0 28px 90px rgba(0,0,0,.30), inset 0 1px 0 rgba(255,255,255,.06);
    }
    .hero h1 {
      margin: 0;
      font-size: clamp(2.5rem, 6vw, 4.8rem);
      line-height: 1;
      letter-spacing: 0;
    }
    .hero p {
      max-width: 760px;
      margin-top: 14px;
      font-size: 1.08rem;
      line-height: 1.65;
    }
    .status-pill {
      display: inline-flex;
      padding: 8px 12px;
      border: 1px solid rgba(127,255,208,.32);
      border-radius: 999px;
      background: rgba(127,255,208,.08);
      color: #7fffd0;
      font-size: .78rem;
      font-weight: 700;
    }
    .choice-card {
      min-height: 142px;
      padding: 18px;
      border: 1px solid rgba(151,255,207,.22);
      border-radius: 14px;
      background: rgba(8,35,30,.66);
      box-shadow: inset 0 1px 0 rgba(255,255,255,.05);
    }
    .choice-card.active {
      background: rgba(16,67,56,.78);
      box-shadow: 0 0 40px rgba(127,255,208,.10), inset 0 1px 0 rgba(255,255,255,.08);
    }
    .choice-card strong {
      display: block;
      color: #e8fff1;
      font-size: 1.05rem;
      line-height: 1.3;
    }
    .choice-card p {
      margin: 10px 0 0;
      color: rgba(232,255,241,.68) !important;
      line-height: 1.5;
    }
    .context-strip {
      padding: 12px 14px;
      border: 1px solid rgba(151,255,207,.16);
      border-radius: 14px;
      background: rgba(7,28,24,.62);
      margin: 14px 0 18px;
    }
    .stButton > button {
      border-radius: 10px;
      font-weight: 700;
    }
    .stTextInput input, .stTextArea textarea {
      border-radius: 10px;
      background: rgba(3,18,15,.58);
      color: #e8fff1;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

health = get_health_status()
gemini_ready = bool(health.get("gemini_configured"))

with st.sidebar:
    st.markdown("### BioMimetix AI")
    if health.get("gemini_configured"):
        st.success("Gemini ready")
    else:
        st.error("Gemini key missing")
        st.caption("Set GEMINI_API_KEY in Streamlit Secrets.")
    st.caption(f"Model: `{health.get('model')}`")
    st.divider()
    for index, name in enumerate(STEP_NAMES):
        marker = "●" if st.session_state.stage == index else "✓" if st.session_state.stage > index else "○"
        st.caption(f"{marker} {index + 1}. {name}")
    st.divider()
    if st.button("New cycle", width="stretch"):
        reset_app()

st.markdown(
    """
    <div class="hero">
      <span class="status-pill">Streamlit end-user app</span>
      <h1>BioMimetix AI</h1>
      <p>Explore a product through biological strategies, sketch the mechanism, generate concepts, and prepare a physical prototype pathway.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if st.session_state.stage > 0:
    st.progress(st.session_state.stage / 8)
    context = [f"**Product:** {st.session_state.product}"]
    if st.session_state.selected_function:
        context.append(f"**Function:** {st.session_state.selected_function}")
    if st.session_state.selected_organism:
        context.append(f"**Organism:** {st.session_state.selected_organism.get('organism')}")
    if st.session_state.selected_principle:
        context.append(f"**Principle:** {st.session_state.selected_principle.get('title')}")
    st.markdown(f'<div class="context-strip">{" · ".join(context)}</div>', unsafe_allow_html=True)

st.divider()

stage = st.session_state.stage

if stage == 0:
    st.header("Step 1 — Product Analyse")
    st.write("Define a product. The app breaks it into functions, then guides you toward biological strategies.")
    if not gemini_ready:
        st.warning("Gemini is not configured. Add GEMINI_API_KEY in Streamlit Secrets and reboot the app before analyzing a product.")

    examples = st.columns(5)
    for i, value in enumerate(["Helmet", "Running shoe", "Drone blade", "Bicycle frame", "Water bottle"]):
        with examples[i]:
            if st.button(value, key=f"example_{i}", width="stretch"):
                st.session_state.product_input = value

    product_name = st.text_input(
        "Product name",
        value=st.session_state.get("product_input", ""),
        placeholder="Helmet, running shoe, drone blade...",
    )

    if st.button("Analyze product", type="primary", disabled=(not product_name.strip() or not gemini_ready)):
        with st.spinner("Deconstructing product and finding a reference image..."):
            components = run_backend(deconstruct_product, DeconstructReq(product=product_name.strip()))
            product_image = product_image_search(product_name.strip())
        if components:
            st.session_state.product = product_name.strip()
            st.session_state.components = components
            st.session_state.product_image = product_image
            st.session_state.selected_function = ""
            st.session_state.stage = 1
            st.rerun()

elif stage == 1:
    st.header(f"Step 2 — Product Functions: {st.session_state.product}")
    image_col, function_col = st.columns([1, 2])

    with image_col:
        show_image(st.session_state.product_image, st.session_state.product)

    with function_col:
        st.write("Select the single function you want to redesign through nature.")
        cols = st.columns(min(3, len(st.session_state.components)))
        for index, item in enumerate(st.session_state.components):
            with cols[index % len(cols)]:
                selected = st.session_state.selected_function == item["function"]
                st.markdown(card(item["component"], item["function"], selected), unsafe_allow_html=True)
                if st.button(
                    "Selected" if selected else "Select",
                    key=f"function_{index}",
                    type="primary" if selected else "secondary",
                    width="stretch",
                ):
                    st.session_state.selected_function = item["function"]
                    st.rerun()

    if st.button("Start Nature Quest", type="primary", disabled=not st.session_state.selected_function):
        with st.spinner("Finding biological strategies..."):
            options = run_backend(
                biomimetic_search,
                BiomimicryReq(product=st.session_state.product, function=st.session_state.selected_function),
            )
        if options:
            st.session_state.biomimicry_options = options
            st.session_state.selected_organism = None
            st.session_state.selected_organism_image = None
            st.session_state.stage = 2
            st.rerun()

elif stage == 2:
    st.header("Step 3 — Biomimicry: Nature Quest")
    st.write("Choose one organism, then complete the exploration pack before abstraction unlocks.")

    options = st.session_state.biomimicry_options
    cols = st.columns(min(5, len(options)))
    current = (st.session_state.selected_organism or {}).get("organism")
    for index, option in enumerate(options):
        with cols[index % len(cols)]:
            selected = current == option["organism"]
            st.markdown(card(option["organism"], option.get("rationale", ""), selected), unsafe_allow_html=True)
            if st.button(
                "Open" if not selected else "Opened",
                key=f"organism_{index}",
                type="primary" if selected else "secondary",
                width="stretch",
            ):
                st.session_state.selected_organism = option
                with st.spinner("Loading organism image..."):
                    st.session_state.selected_organism_image = run_backend(
                        biodiversity_reference,
                        ReferenceImageReq(
                            organism=option["organism"],
                            function=st.session_state.selected_function,
                        ),
                    )
                st.rerun()

    organism = st.session_state.selected_organism
    if organism:
        st.divider()
        media_col, pack_col = st.columns([1, 2])
        with media_col:
            show_image(st.session_state.selected_organism_image, organism["organism"])
        with pack_col:
            st.subheader(organism["organism"])
            st.write(organism.get("rationale", ""))
            pack = organism.get("exploration_pack", {})
            watch = pack.get("watch", [])
            read = pack.get("read", [])
            act = pack.get("act", {})

            if watch:
                st.markdown("**Watch**")
                for item in watch:
                    st.markdown(f"- [{item.get('title')}]({item.get('url')}) — {item.get('description', '')}")
            if read:
                st.markdown("**Read**")
                for item in read:
                    st.markdown(f"- [{item.get('title')}]({item.get('url')}) — {item.get('description', '')}")
            if act:
                with st.expander(act.get("title", "Nature Quest"), expanded=True):
                    st.write(act.get("description", ""))
                    for item in act.get("checklist", []):
                        st.markdown(f"- {item}")

        explored = st.checkbox("I have explored these resources and made my own observations.", key="explored_gate")
        if st.button("Abstract the principle", type="primary", disabled=not explored):
            with st.spinner("Abstracting principles..."):
                abstractions = run_backend(
                    principle_abstraction,
                    AbstractReq(
                        product=st.session_state.product,
                        function=st.session_state.selected_function,
                        organism=organism["organism"],
                    ),
                )
            if abstractions:
                st.session_state.abstractions = abstractions
                st.session_state.selected_principle = None
                st.session_state.stage = 3
                st.rerun()

elif stage == 3:
    st.header("Step 4 — Principle Abstraction")
    st.write("Select one abstract principle, then sketch it before ideation.")

    abstractions = st.session_state.abstractions or {}
    principles = abstractions.get("principles", [])
    cols = st.columns(min(3, len(principles)))
    for index, principle in enumerate(principles):
        with cols[index % len(cols)]:
            selected = (st.session_state.selected_principle or {}).get("title") == principle["title"]
            st.markdown(card(principle["title"], principle["principle"], selected), unsafe_allow_html=True)
            if st.button(
                "Selected" if selected else "Select",
                key=f"principle_{index}",
                type="primary" if selected else "secondary",
                width="stretch",
            ):
                st.session_state.selected_principle = principle
                st.rerun()

    sketch_pack = abstractions.get("sketch_pack", {})
    if sketch_pack:
        st.subheader(sketch_pack.get("title", "Sketching Assignment"))
        st.write(sketch_pack.get("prompt", "Sketch the mechanism as forces, surfaces, gradients, and failure modes."))
        for item in sketch_pack.get("checks", []):
            st.markdown(f"- {item}")

    sketch_done = st.checkbox("Sketch completed.", key="sketch_done_gate")
    if st.button("Move to ideation", type="primary", disabled=not (st.session_state.selected_principle and sketch_done)):
        with st.spinner("Generating concepts..."):
            concepts = run_backend(
                ideate_concepts,
                IdeateReq(
                    product=st.session_state.product,
                    principle=st.session_state.selected_principle["title"],
                ),
            )
        if concepts:
            st.session_state.concepts = concepts
            st.session_state.selected_concept = None
            st.session_state.stage = 4
            st.rerun()

elif stage == 4:
    st.header("Step 5 — Ideation and Creation")
    st.write("Select one concept and confirm what must remain physically testable.")

    concepts = st.session_state.concepts
    cols = st.columns(min(3, len(concepts)))
    for index, concept in enumerate(concepts):
        with cols[index % len(cols)]:
            selected = (st.session_state.selected_concept or {}).get("concept_name") == concept["concept_name"]
            st.markdown(card(concept["concept_name"], concept.get("description", ""), selected), unsafe_allow_html=True)
            if st.button(
                "Selected" if selected else "Select",
                key=f"concept_{index}",
                type="primary" if selected else "secondary",
                width="stretch",
            ):
                st.session_state.selected_concept = concept
                st.rerun()

    refined = st.checkbox("I have refined this concept and identified what should be tested physically.", key="refined_gate")
    if st.button("Generate strict 2D prompt", type="primary", disabled=not (st.session_state.selected_concept and refined)):
        with st.spinner("Generating prompt..."):
            result = run_backend(
                generate_prompt,
                PromptReq(
                    product=st.session_state.product,
                    concept=st.session_state.selected_concept["concept_name"],
                ),
            )
        if result:
            st.session_state.final_prompt = result.get("prompt", "")
            st.session_state.stage = 5
            st.rerun()

elif stage == 5:
    st.header("Step 6 — 2D Image Prompt")
    st.write("Copy this into your image generator. Keep the output clean for 3D conversion.")
    st.code(st.session_state.final_prompt, language=None)
    prompt_used = st.checkbox("I have copied or used the prompt externally.", key="prompt_used_gate")
    if st.button("Continue to 3D pathway", type="primary", disabled=not prompt_used):
        st.session_state.stage = 6
        st.rerun()

elif stage == 6:
    st.header("Step 7 — 3D Model: Printpal Pathway")
    st.write("Convert the clean 2D image into a printable model. The AI stops here; your hands take over.")
    cols = st.columns(4)
    steps = [
        ("Upload", "Upload the image into Printpal or another image-to-3D tool."),
        ("Inspect", "Rotate the mesh and check impossible geometry."),
        ("Export", "Export an STL and save a screenshot before slicing."),
        ("Print", "3D print a small prototype, even if imperfect."),
    ]
    for index, (title, body) in enumerate(steps):
        with cols[index]:
            st.markdown(card(title, body), unsafe_allow_html=True)

    stl_done = st.checkbox("I have created or inspected an STL pathway.", key="stl_done_gate")
    if st.button("Evaluate physical result", type="primary", disabled=not stl_done):
        st.session_state.stage = 7
        st.rerun()

elif stage == 7:
    st.header("Step 8 — Evaluate")
    st.write("Log what failed. Biomimicry improves when the physical prototype argues back.")

    failure = st.text_area("How did the translation from nature to AI to physical object fail?", key="ev_failure")
    nuance = st.text_area("What nuances of the biological organism were lost?", key="ev_nuance")
    printed = st.text_area("Did the 3D print function as expected?", key="ev_print")
    next_iteration = st.text_area("What should change in the next iteration?", key="ev_next")
    complete = all(len(value.strip()) > 8 for value in [failure, nuance, printed, next_iteration])

    if st.button("Finish and start new cycle", type="primary", disabled=not complete):
        reset_app()
