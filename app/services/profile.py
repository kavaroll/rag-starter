import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PROFILE_PATH = ROOT / "data" / "profile.json"
HISTORY_PATH = ROOT / "data" / "history.json"


class ProfileStore:

    def get_profile(self):
        return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))

    def get_history(self):
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))

    def save_profile(self, profile):
        profile["last_updated"] = datetime.now(timezone.utc).date().isoformat()
        PROFILE_PATH.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    def append_history(self, entry):
        history = self.get_history()
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        history.append(entry)
        HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── profile mutations ──────────────────────────────────────────

    def setup(self, family, members):
        profile = {"family": family, "members": members}
        self.save_profile(profile)
        self.append_history({
            "type": "profile_update",
            "member": None,
            "changes": {"setup": profile},
            "reason": "initial setup",
        })

    def add_member(self, member, reason=""):
        profile = self.get_profile()
        names = [m["name"] for m in profile["members"]]
        if member["name"] in names:
            raise ValueError(f"Member '{member['name']}' already exists.")
        profile["members"].append(member)
        self.save_profile(profile)
        self.append_history({
            "type": "profile_update",
            "member": member["name"],
            "changes": {"added": member},
            "reason": reason,
        })

    def update_member(self, name, updates, reason=""):
        profile = self.get_profile()
        for member in profile["members"]:
            if member["name"] == name:
                before = deepcopy(member)
                member.update({k: v for k, v in updates.items() if v is not None})
                self.save_profile(profile)
                self.append_history({
                    "type": "profile_update",
                    "member": name,
                    "changes": {
                        k: {"before": before.get(k), "after": member[k]}
                        for k in updates if updates[k] is not None
                    },
                    "reason": reason,
                })
                return
        raise ValueError(f"Member '{name}' not found.")

    # ── history mutations ──────────────────────────────────────────

    def log_recommendation(self, recipe_id, recipe_name, members, plan_id=None):
        self.append_history({
            "type": "recommendation",
            "recipe_id": recipe_id,
            "recipe_name": recipe_name,
            "members": members,
            "plan_id": plan_id,
        })

    def log_feedback(self, recipe_id, recipe_name, member, sentiment, note=""):
        self.append_history({
            "type": "feedback",
            "recipe_id": recipe_id,
            "recipe_name": recipe_name,
            "member": member,
            "sentiment": sentiment,
            "note": note,
        })

    # ── profile refresh via LLM ────────────────────────────────────

    def refresh(self, llm):
        from pathlib import Path as P
        prompt_template = P("app/prompts/refresh_profile.txt").read_text()
        profile = self.get_profile()
        history = self.get_history()

        feedback_entries = [h for h in history if h["type"] == "feedback"]
        if not feedback_entries:
            return profile

        prompt = prompt_template.format(
            profile=json.dumps(profile, ensure_ascii=False, indent=2),
            history=json.dumps(feedback_entries, ensure_ascii=False, indent=2),
        )
        reply = llm.generate(prompt)

        import re
        match = re.search(r"\{.*\}", reply, re.S)
        if not match:
            raise ValueError(f"LLM did not return valid JSON:\n{reply}")

        updated = json.loads(match.group())
        self.save_profile(updated)
        self.append_history({
            "type": "profile_update",
            "member": None,
            "changes": {"refreshed": True},
            "reason": f"auto-refresh from {len(feedback_entries)} feedback entries",
        })
        return updated
