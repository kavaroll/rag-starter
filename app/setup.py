from app.services.profile import ProfileStore


def prompt(label, default=None):
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default or ""


def prompt_list(label):
    raw = input(f"{label} (comma-separated, or leave blank): ").strip()
    return [x.strip() for x in raw.split(",") if x.strip()]


def collect_member():
    name = prompt("  Name")
    if not name:
        return None
    return {
        "name": name,
        "restrictions": prompt_list("  Dietary restrictions"),
        "likes": prompt_list("  Likes"),
        "dislikes": prompt_list("  Dislikes"),
        "notes": prompt("  Notes", default=""),
    }


def main():
    print("=== Family Meal Planner — Initial Setup ===\n")
    family = prompt("Family name")
    members = []

    print("\nAdd family members (leave name blank to finish):")
    while True:
        print(f"\n  Member {len(members) + 1}")
        member = collect_member()
        if not member:
            break
        members.append(member)

    if not members:
        print("No members added. Exiting.")
        return

    ProfileStore().setup(family, members)
    print(f"\nProfile saved with {len(members)} member(s). Run the app to start planning meals.")


if __name__ == "__main__":
    main()
