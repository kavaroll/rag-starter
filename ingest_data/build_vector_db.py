import json
import time
from pathlib import Path

from tqdm import tqdm

from app.db.chroma import get_collection

ROOT = Path(__file__).resolve().parent.parent
BATCH_SIZE = 128

recipes = json.load(
    open(ROOT / "data" / "raw" / "recipes.json", encoding="utf-8")
)

collection = get_collection()


def to_document(recipe):
    steps = [
        recipe[f"MANUAL{i:02d}"]
        for i in range(1, 21)
        if recipe.get(f"MANUAL{i:02d}")
    ]

    return f"""
제목: {recipe['RCP_NM']}

종류: {recipe['RCP_PAT2']}
조리방법: {recipe['RCP_WAY2']}

재료:
{recipe['RCP_PARTS_DTLS']}

조리순서:
{chr(10).join(steps)}

영양정보
탄수화물 {recipe['INFO_CAR']}g
단백질 {recipe['INFO_PRO']}g
지방 {recipe['INFO_FAT']}g
나트륨 {recipe['INFO_NA']}mg

태그:
{recipe['HASH_TAG']}

Tip:
{recipe['RCP_NA_TIP']}
""".strip()


start = time.time()

ids = []
docs = []
metas = []

for i, recipe in enumerate(tqdm(recipes, desc="Embedding recipes"), 1):

    ids.append(recipe["RCP_SEQ"])
    docs.append(to_document(recipe))
    metas.append({
        "name": recipe["RCP_NM"],
        "category": recipe["RCP_PAT2"],
        "method": recipe["RCP_WAY2"],
        "image": recipe["ATT_FILE_NO_MAIN"],
    })

    if len(ids) == BATCH_SIZE or i == len(recipes):

        t = time.time()

        collection.add(
            ids=ids,
            documents=docs,
            metadatas=metas,
        )

        tqdm.write(
            f"[{i:5d}/{len(recipes)}] saved {len(ids):3d} "
            f"({time.time() - t:.2f}s) elapsed {time.time() - start:.1f}s"
        )

        ids.clear()
        docs.clear()
        metas.clear()

print(f"\nFinished: {len(recipes)} recipes")