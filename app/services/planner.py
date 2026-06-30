import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from app.services.llm import LLM
from app.services.retriever import Retriever

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_recipes",
            "description": "Search the recipe database for recipes matching a query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Semantic search query"},
                    "n_results": {"type": "integer", "default": 5},
                    "category": {"type": "string", "description": "Filter by recipe category (e.g. 국·탕, 반찬)"},
                    "method": {"type": "string", "description": "Filter by cooking method (e.g. 볶기, 찌기)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_recommendation",
            "description": "Record that a recipe was recommended to the family. Always call this after recommending a recipe.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipe_id": {"type": "string"},
                    "recipe_name": {"type": "string"},
                    "members": {"type": "array", "items": {"type": "string"}},
                    "plan_id": {"type": "string"},
                },
                "required": ["recipe_id", "recipe_name", "members"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_feedback",
            "description": "Record a family member's reaction to a recipe they ate.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member": {"type": "string"},
                    "recipe_id": {"type": "string"},
                    "recipe_name": {"type": "string"},
                    "sentiment": {"type": "string", "enum": ["liked", "disliked", "neutral"]},
                    "note": {"type": "string"},
                },
                "required": ["member", "recipe_id", "recipe_name", "sentiment"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "refresh_profile",
            "description": "Rewrite the family profile based on accumulated feedback history. Call when the user mentions updating preferences.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_member",
            "description": "Add a new family member to the profile.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "restrictions": {"type": "array", "items": {"type": "string"}, "default": []},
                    "likes": {"type": "array", "items": {"type": "string"}, "default": []},
                    "dislikes": {"type": "array", "items": {"type": "string"}, "default": []},
                    "notes": {"type": "string", "default": ""},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_member",
            "description": "Update an existing family member's preferences, restrictions, or notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "restrictions": {"type": "array", "items": {"type": "string"}},
                    "likes": {"type": "array", "items": {"type": "string"}},
                    "dislikes": {"type": "array", "items": {"type": "string"}},
                    "notes": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
]


class MealPlanner:

    def __init__(self):
        self.retriever = Retriever()
        self.llm = LLM()
        self.system_prompt = Path("app/prompts/meal_planner.txt").read_text()
        self.plan_prompt = Path("app/prompts/plan_week.txt").read_text()
        self.refresh_prompt = Path("app/prompts/refresh_profile.txt").read_text()

    def chat(self, message, profile, history=None):
        self._profile = deepcopy(profile)
        self._history = history or []
        self._events = []

        messages = [
            {
                "role": "system",
                "content": self.system_prompt.format(
                    profile=json.dumps(self._profile, ensure_ascii=False, indent=2)
                ),
            },
            {"role": "user", "content": message},
        ]

        for _ in range(10):
            msg = self.llm.chat(messages, tools=TOOLS)

            if not msg.tool_calls:
                profile_changed = self._profile != profile
                return {
                    "result": msg.content,
                    "events": self._events,
                    "profile": self._profile if profile_changed else None,
                }

            messages.append(msg)

            for call in msg.tool_calls:
                result = self._execute(call.function.name, json.loads(call.function.arguments))
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        return {"result": "Sorry, I couldn't complete that request.", "events": self._events, "profile": None}

    def plan_week(self, profile):
        queries = [
            "seafood low sodium dinner",
            "chicken noodles kids friendly",
            "Korean BBQ style grilled",
            "light soup stew",
            "rice bowl family meal",
            "easy stir fry weeknight",
            "special weekend dinner",
        ]
        candidates = []
        seen = set()
        for query in queries:
            _, metas, ids = self.retriever.search(query, k=5)
            for rid, meta in zip(ids, metas):
                if rid not in seen:
                    seen.add(rid)
                    candidates.append({"recipe_id": rid, "name": meta["name"],
                                       "category": meta["category"], "method": meta["method"]})

        prompt = self.plan_prompt.format(
            profile=json.dumps(profile, ensure_ascii=False, indent=2),
            candidates=json.dumps(candidates, ensure_ascii=False, indent=2),
        )
        reply = self.llm.generate(prompt)
        match = re.search(r"\[.*\]", reply, re.S)
        if not match:
            raise ValueError(f"LLM did not return a valid plan:\n{reply}")
        return json.loads(match.group())

    def _ts(self):
        return datetime.now(timezone.utc).isoformat()

    def _execute(self, name, args):
        if name == "search_recipes":
            filters = {k: args[k] for k in ("category", "method") if args.get(k)}
            _, metas, ids = self.retriever.search(
                args["query"], k=args.get("n_results", 5), filters=filters or None,
            )
            return [
                {"recipe_id": rid, "name": m.get("name"), "category": m.get("category"), "method": m.get("method")}
                for rid, m in zip(ids, metas)
            ]

        if name == "log_recommendation":
            self._events.append({
                "type": "recommendation",
                "recipe_id": args["recipe_id"],
                "recipe_name": args["recipe_name"],
                "members": args["members"],
                "plan_id": args.get("plan_id"),
                "timestamp": self._ts(),
            })
            return {"status": "ok"}

        if name == "log_feedback":
            self._events.append({
                "type": "feedback",
                "recipe_id": args["recipe_id"],
                "recipe_name": args["recipe_name"],
                "member": args["member"],
                "sentiment": args["sentiment"],
                "note": args.get("note", ""),
                "timestamp": self._ts(),
            })
            return {"status": "ok"}

        if name == "refresh_profile":
            feedback = [h for h in self._history if h.get("type") == "feedback"]
            if not feedback:
                return self._profile
            prompt = self.refresh_prompt.format(
                profile=json.dumps(self._profile, ensure_ascii=False, indent=2),
                history=json.dumps(feedback, ensure_ascii=False, indent=2),
            )
            reply = self.llm.generate(prompt)
            match = re.search(r"\{.*\}", reply, re.S)
            if match:
                self._profile = json.loads(match.group())
                self._events.append({"type": "profile_update", "member": None,
                                     "changes": {"refreshed": True}, "timestamp": self._ts()})
            return self._profile

        if name == "add_member":
            member = {
                "name": args["name"],
                "restrictions": args.get("restrictions", []),
                "likes": args.get("likes", []),
                "dislikes": args.get("dislikes", []),
                "notes": args.get("notes", ""),
            }
            if any(m["name"] == member["name"] for m in self._profile["members"]):
                return {"error": f"Member '{member['name']}' already exists."}
            self._profile["members"].append(member)
            self._events.append({"type": "profile_update", "member": member["name"],
                                  "changes": {"added": member}, "timestamp": self._ts()})
            return {"status": "ok", "added": member["name"]}

        if name == "update_member":
            for m in self._profile["members"]:
                if m["name"] == args["name"]:
                    updates = {k: args[k] for k in ("restrictions", "likes", "dislikes", "notes") if k in args}
                    m.update(updates)
                    self._events.append({"type": "profile_update", "member": args["name"],
                                         "changes": updates, "timestamp": self._ts()})
                    return {"status": "ok", "updated": args["name"]}
            return {"error": f"Member '{args['name']}' not found."}

        return {"error": f"unknown tool: {name}"}
