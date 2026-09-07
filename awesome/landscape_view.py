"""Pure chart/table helpers for the landscape map. No Streamlit imports.

Same split as `awesome/network_view.py`. The 15-node neighbor SVG helpers stay in
`network_view` as optional detail after a list is selected — this module is the landing
chart (precomputed coordinates) plus inspector tables.
"""
from __future__ import annotations

from awesome.landscape import set_diff
from awesome.network import neighbors_of

UNKNOWN_POINT_SIZE = 12
SIGNATURE_CAPTION = "composition of citations, not quality"


def scatter_rows(landscape_lists: list[dict], list_index: dict, color_mode: str = "community") -> list[dict]:
    by_id = {item["id"]: item for item in list_index.get("lists", [])}
    rows = []
    for row in landscape_lists:
        item = by_id.get(row["id"], {})
        entries = item.get("entry_count")
        size = UNKNOWN_POINT_SIZE if entries is None else entries
        topic = (item.get("topics") or ["Other"])[0]
        color = row["community_id"] if color_mode == "community" else topic
        rows.append({
            "id": row["id"],
            "name": item.get("name", row["id"]),
            "x": row["x"],
            "y": row["y"],
            "color": color,
            "size": size,
            "entry_count": entries,
            "community_id": row["community_id"],
            "topic": topic,
            "unique": row["unique"],
            "family": row["family"],
            "shared": row["shared"],
            "hub": row["hub"],
        })
    return rows


def scatter_spec(rows: list[dict], color_title: str = "community"):
    import altair as alt
    data = rows
    return (
        alt.Chart(alt.Data(values=data))
        .mark_circle(opacity=0.75)
        .encode(
            x=alt.X("x:Q", title=None, axis=alt.Axis(labels=False, ticks=False)),
            y=alt.Y("y:Q", title=None, axis=alt.Axis(labels=False, ticks=False)),
            color=alt.Color("color:N", title=color_title),
            size=alt.Size("size:Q", title="Indexed entries"),
            tooltip=["name:N", "id:N", "topic:N", "community_id:N"],
        )
        .properties(height=480)
        .interactive()
    )


def signature_stack(row: dict) -> list[dict]:
    return [
        {"Part": "Unique", "Projects": row["unique"]},
        {"Part": "Family", "Projects": row["family"]},
        {"Part": "Shared", "Projects": row["shared"]},
        {"Part": "Hub", "Projects": row["hub"]},
    ]


def neighbors_filtered(list_pairs: list[dict], list_id: str, hide_clones: bool, limit: int = 15) -> list[dict]:
    rows = neighbors_of(list_pairs, list_id, limit=limit * 4 if hide_clones else limit)
    if hide_clones:
        rows = [row for row in rows if not row.get("near_duplicate")]
    return rows[:limit]


def edge_inspector_rows(preview: dict) -> list[dict]:
    rows = []
    for item in preview.get("independent", []):
        rows.append({"Project": item["title"], "This list": item["title"],
                     "Neighbor list": item.get("neighbor_title", ""), "Kind": "independent"})
    for item in preview.get("copy_lineage", []):
        rows.append({"Project": item["title"], "This list": item["title"],
                     "Neighbor list": item.get("neighbor_title", ""), "Kind": "copy-lineage"})
    return rows


def set_diff_rows(memberships: dict[str, list[dict]], hub_ids, names: dict[str, str] | None = None) -> list[dict]:
    names = names or {}
    diff = set_diff(memberships, hub_ids)
    rows = []
    for item in diff["shared_independent"]:
        rows.append({"Bucket": "shared_independent", "Project": next(iter(item["titles"].values())),
                     "Id": item["id"]})
    for item in diff["shared_copy_lineage"]:
        rows.append({"Bucket": "shared_copy_lineage", "Project": next(iter(item["titles"].values())),
                     "Id": item["id"]})
    for key, items in diff.items():
        if not key.startswith("unique_to_"):
            continue
        lid = key[len("unique_to_"):]
        label = names.get(lid, lid)
        for item in items:
            rows.append({"Bucket": f"unique_to_{label}", "Project": item["title"], "Id": item["id"]})
    for item in diff["unique_and_not_a_hub"]:
        rows.append({"Bucket": "unique_and_not_a_hub", "Project": item["title"], "Id": item["id"]})
    return rows
