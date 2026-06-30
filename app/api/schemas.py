from pydantic import BaseModel


class Member(BaseModel):
    name: str
    restrictions: list[str] = []
    likes: list[str] = []
    dislikes: list[str] = []
    notes: str = ""


class ProfileSetupRequest(BaseModel):
    family: str
    members: list[Member]


class MemberUpdateRequest(BaseModel):
    restrictions: list[str] | None = None
    likes: list[str] | None = None
    dislikes: list[str] | None = None
    notes: str | None = None
    reason: str = ""


class FeedbackRequest(BaseModel):
    recipe_id: str
    recipe_name: str
    member: str
    sentiment: str  # "liked" | "disliked" | "neutral"
    note: str = ""


class PlannerRequest(BaseModel):
    message: str
    profile: dict | None = None
    history: list[dict] = []


class WeekPlanRequest(BaseModel):
    profile: dict | None = None
