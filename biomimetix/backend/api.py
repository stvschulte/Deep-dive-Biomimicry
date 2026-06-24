from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import core


app = FastAPI(title="BioMimetix API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/generated_images", StaticFiles(directory=core.image_dir), name="generated_images")


def _respond(handler, *args):
    try:
        result = handler(*args)
    except core.BackendError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=500, detail="The backend did not return a result.")
    return result


@app.get("/api/health")
def health():
    return core.get_health_status()


@app.post("/api/deconstruct")
def deconstruct(req: core.DeconstructReq):
    return _respond(core.deconstruct_product, req)


@app.post("/api/product-image")
def product_image(req: core.ProductImageReq):
    return _respond(core.product_image_search, req.product)


@app.post("/api/biomimicry")
def biomimicry(req: core.BiomimicryReq):
    return _respond(core.biomimetic_search, req)


@app.post("/api/reference-image")
def reference_image(req: core.ReferenceImageReq):
    return _respond(core.biodiversity_reference, req)


@app.post("/api/abstract")
def abstract(req: core.AbstractReq):
    return _respond(core.principle_abstraction, req)


@app.post("/api/ideate")
def ideate(req: core.IdeateReq):
    return _respond(core.ideate_concepts, req)


@app.post("/api/prompt-gen")
def prompt_gen(req: core.PromptReq):
    return _respond(core.generate_prompt, req)


@app.post("/api/exploded-view")
def exploded_view(req: core.ExplodedViewReq):
    return _respond(core.exploded_view, req)


@app.post("/api/asknature-search")
def asknature_search(req: core.AskNatureSearchReq):
    return _respond(core.asknature_search, req.query, req.limit)
