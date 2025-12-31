import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List

# Merged of team_data_filter.py + test5.py
# - parse nodes from LLM output
# - remove source_time/source_entry_id
# - write team_strategy_entities_cleaned.json directly


def slug(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^\u4e00-\u9fff0-9A-Za-z_-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "UNKNOWN"


ELEMENT_SLOTS = {"水位", "火位", "冰位", "雷位", "草位", "风位"}
DROP_FIELDS = {"source_time", "source_entry_id"}


def dedup_by_id(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for it in items:
        by_id[it["id"]] = it
    return list(by_id.values())


def parse_nodes(input_path: Path) -> Dict[str, List[Dict[str, Any]]]:
    data = json.load(input_path.open("r", encoding="utf-8"))

    team_templates: List[Dict[str, Any]] = []
    slot_groups: List[Dict[str, Any]] = []
    slot_templates: List[Dict[str, Any]] = []

    for entry in data:
        llm = entry.get("llm_result") or {}
        core_character = llm.get("core_character") or entry.get("id") or "UNKNOWN_CORE"
        core_key = slug(core_character)

        for arch in (llm.get("archetypes") or []):
            archetype_name = arch.get("name") or "UNKNOWN_ARCHETYPE"
            arch_key = slug(archetype_name)

            team_template_id = f"TT:{core_key}:{arch_key}"
            team_templates.append(
                {
                    "id": team_template_id,
                    "label": "TeamTemplate",
                    "core_character": core_character,
                    "archetype_name": archetype_name,
                    "focus": bool(arch.get("focus", False)),
                    "core_role": arch.get("core_role"),
                    "core_evidence": arch.get("core_evidence"),
                    "source_entry_id": entry.get("id"),
                    "source_time": entry.get("time"),
                    "example_team_members": (arch.get("example_team") or {}).get("members", []),
                    "example_team_evidence": (arch.get("example_team") or {}).get("evidence"),
                }
            )

            slots = arch.get("slots") or []

            required_slot_ids: List[str] = []
            optional_non_element: List[Dict[str, Any]] = []
            optional_element: List[Dict[str, Any]] = []

            for s in slots:
                slot_name = s.get("slot") or "UNKNOWN_SLOT"
                must = bool(s.get("must", False))
                slot_key = slug(slot_name)

                slot_template_id = f"ST:{team_template_id}:{slot_key}"
                slot_obj: Dict[str, Any] = {
                    "id": slot_template_id,
                    "label": "SlotTemplate",
                    "team_template_id": team_template_id,
                    "slot": slot_name,
                    "need": s.get("need"),
                    "must": must,
                    "evidence": s.get("evidence"),
                    "slot_group_id": None,
                }
                slot_templates.append(slot_obj)

                if must:
                    required_slot_ids.append(slot_template_id)
                else:
                    if slot_name in ELEMENT_SLOTS:
                        optional_element.append(slot_obj)
                    else:
                        optional_non_element.append(slot_obj)

            # SlotGroup 1: fixed required
            if required_slot_ids:
                sg_required_id = f"SG:{team_template_id}:fixed_required"
                slot_groups.append(
                    {
                        "id": sg_required_id,
                        "label": "SlotGroup",
                        "team_template_id": team_template_id,
                        "name": "fixed_required",
                        "group_type": "fixed_required",
                        "min_select": len(required_slot_ids),
                        "max_select": len(required_slot_ids),
                        "mutual_exclusive": False,
                        "slot_template_ids": required_slot_ids,
                        "description": "该组内所有 Slot 必须全部满足（固定必选）。",
                    }
                )
                for st in slot_templates:
                    if st["team_template_id"] == team_template_id and st["id"] in required_slot_ids:
                        st["slot_group_id"] = sg_required_id

            # SlotGroup 2: flex element (mutual exclusive, max 1)
            if optional_element:
                sg_flex_id = f"SG:{team_template_id}:flex_element"
                flex_slot_ids = [x["id"] for x in optional_element]
                slot_groups.append(
                    {
                        "id": sg_flex_id,
                        "label": "SlotGroup",
                        "team_template_id": team_template_id,
                        "name": "flex_element",
                        "group_type": "flex",
                        "min_select": 0,
                        "max_select": 1,
                        "mutual_exclusive": True,
                        "slot_template_ids": flex_slot_ids,
                        "description": "元素灵活位：水/火/冰/雷/草/风 等位通常互斥，最多选择一个。",
                    }
                )
                for x in optional_element:
                    x["slot_group_id"] = sg_flex_id

            # SlotGroup 3..N: other optional slots independent
            for x in optional_non_element:
                sg_opt_id = f"SG:{team_template_id}:opt_{slug(x['slot'])}"
                slot_groups.append(
                    {
                        "id": sg_opt_id,
                        "label": "SlotGroup",
                        "team_template_id": team_template_id,
                        "name": f"opt_{slug(x['slot'])}",
                        "group_type": "optional_independent",
                        "min_select": 0,
                        "max_select": 1,
                        "mutual_exclusive": False,
                        "slot_template_ids": [x["id"]],
                        "description": "独立可选位：该槽可选填 0 或 1 个。",
                    }
                )
                x["slot_group_id"] = sg_opt_id

    return {
        "TeamTemplate": dedup_by_id(team_templates),
        "SlotGroup": dedup_by_id(slot_groups),
        "SlotTemplate": dedup_by_id(slot_templates),
    }


def remove_fields_inplace(data: Any) -> None:
    if not isinstance(data, dict):
        raise ValueError("Expected a dict with node-type keys.")
    for _, nodes in data.items():
        if not isinstance(nodes, list):
            continue
        for n in nodes:
            if not isinstance(n, dict):
                continue
            for k in list(DROP_FIELDS):
                if k in n:
                    del n[k]


def print_counts(data: Dict[str, Any]) -> None:
    print("Counts:")
    for node_type, nodes in data.items():
        cnt = len(nodes) if isinstance(nodes, list) else 0
        print(f"  {node_type:12s} {cnt}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input",
        type=Path,
        default=Path("data_preprocess/dataKG/LLM_extracted/team_strategy_LLM.json"),
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=Path("data_preprocess/dataKG/entities/team_strategy_entities_cleaned.json"),
    )
    args = ap.parse_args()

    nodes = parse_nodes(args.input)
    remove_fields_inplace(nodes)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(nodes, f, ensure_ascii=False, indent=2)

    print("Wrote:", args.output)
    print_counts(nodes)


if __name__ == "__main__":
    main()
