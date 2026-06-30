from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    FeedbackRequest,
    Member,
    MemberUpdateRequest,
    PlannerRequest,
    ProfileSetupRequest,
    WeekPlanRequest,
)
from app.services.llm import LLM
from app.services.planner import MealPlanner
from app.services.profile import ProfileStore

router = APIRouter()
store = ProfileStore()
planner = MealPlanner()
llm = LLM()


# ── profile ───────────────────────────────────────────────────────

@router.post("/profile/setup")
def setup_profile(req: ProfileSetupRequest):
    members = [m.model_dump() for m in req.members]
    store.setup(req.family, members)
    return {"status": "ok"}


@router.get("/profile")
def get_profile():
    return store.get_profile()


@router.post("/profile/members")
def add_member(member: Member, reason: str = ""):
    try:
        store.add_member(member.model_dump(), reason=reason)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"status": "ok"}


@router.patch("/profile/members/{name}")
def update_member(name: str, req: MemberUpdateRequest):
    try:
        store.update_member(name, req.model_dump(exclude={"reason"}), reason=req.reason)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "ok"}


@router.post("/profile/refresh")
def refresh_profile():
    updated = store.refresh(llm)
    return updated


# ── history ───────────────────────────────────────────────────────

@router.get("/history")
def get_history():
    return store.get_history()


@router.post("/history/feedback")
def log_feedback(req: FeedbackRequest):
    store.log_feedback(
        recipe_id=req.recipe_id,
        recipe_name=req.recipe_name,
        member=req.member,
        sentiment=req.sentiment,
        note=req.note,
    )
    return {"status": "ok"}


# ── planner ───────────────────────────────────────────────────────

@router.post("/chat")
def chat(req: PlannerRequest):
    profile = req.profile or store.get_profile()
    return planner.chat(req.message, profile, history=req.history)


@router.post("/plan/week")
def plan_week(req: WeekPlanRequest = WeekPlanRequest()):
    profile = req.profile or store.get_profile()
    return planner.plan_week(profile)


@router.get("/recipes/search")
def search_recipes(q: str, n: int = 3):
    _, metas, ids = planner.retriever.search(q, k=n)
    return [{"recipe_id": rid, "recipe_name": m.get("name"), "category": m.get("category"), "method": m.get("method")}
            for rid, m in zip(ids, metas)]


@router.get("/recipes/{recipe_id}")
def get_recipe(recipe_id: str):
    recipe = planner.retriever.get_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe
