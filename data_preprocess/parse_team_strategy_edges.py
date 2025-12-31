import json
import re
from typing import Dict, Any, List, Optional, Tuple, Set


# -------------------------
# helpers
# -------------------------
def slug(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^\u4e00-\u9fff0-9A-Za-z_-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "UNKNOWN"

def build_tt_id(core: str, archetype: str) -> str:
    return f"TT:{slug(core)}:{slug(archetype)}"

def build_st_id(tt_id: str, slot_name: str) -> str:
    return f"ST:{tt_id}:{slug(slot_name)}"

def dedup_edges(edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for e in edges:
        key = (
            e["subject_id"], e["predicate"], e["object_id"],
            e.get("evidence_field",""), e.get("evidence_value","")
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


# -------------------------
# load indexes
# -------------------------
def load_character_name2id(path: str) -> Dict[str, str]:
    obj = json.load(open(path, "r", encoding="utf-8"))
    chars = obj if isinstance(obj, list) else (obj.get("Character") or obj.get("characters") or [])
    m = {}
    for c in chars:
        if c.get("id") and c.get("name"):
            m[c["name"].strip()] = c["id"]
    return m

def norm(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", "", s)
    s = s.replace("后 台", "后台")
    return s

def load_role_alias_index(role_tag_path: str) -> Dict[str, str]:
    role_tags = json.load(open(role_tag_path, "r", encoding="utf-8"))
    idx: Dict[str, str] = {}
    for rt in role_tags:
        rid = rt["id"]  # 英文主键
        name = rt.get("name")
        if name:
            idx[norm(name)] = rid
        for a in rt.get("aliases", []) or []:
            idx[norm(a)] = rid
    return idx


# -------------------------
# role align (规则版)
# -------------------------
SPLIT_RE = re.compile(r"[\/、,，\+\|｜\s]+")
QUAL_RE = re.compile(r"(高频|持续|稳定|对群|对单|泛用|可持续|主要|一般|能力|收益|体系|配合|提供|维持|帮助|绑定)")

def split_role_text(role_text: str) -> List[str]:
    s = norm(role_text)
    if not s:
        return []
    s = re.sub(r"(兼|及|与|和|以及|并|同时)", "/", s)
    return [p for p in SPLIT_RE.split(s) if p]

def heuristic_role(tok: str) -> Set[str]:
    t = tok
    out: Set[str] = set()
    if re.search(r"(后台输出|副C|脱手|协同攻击|后台伤害)", t):
        out.add("role_sub_dps")
    if re.search(r"(增伤|增益|加攻|伤害加成|攻击力加成|输出辅助)", t):
        out.add("role_buffer")
    if re.search(r"(减抗|抗性减益|减防|全元素减抗)", t):
        out.add("role_debuffer")
    if re.search(r"(治疗|回复|奶)", t):
        out.add("role_healer")
    if re.search(r"(护盾|盾辅)", t):
        out.add("role_shielder")
    if re.search(r"(生存|减伤|抗打断)", t):
        out.add("role_survivability")
    if "驾驶员" in t:
        out.add("role_driver")
    if re.search(r"(充能|回能|产球|充电宝)", t):
        out.add("role_energy_support")
    if re.search(r"(挂水|水元素附着|后台挂水|持续挂水)", t):
        out.add("role_enabler_hydro")
    if re.search(r"(挂火|火元素附着|后台挂火|持续挂火)", t):
        out.add("role_enabler_pyro")
    if re.search(r"(挂雷|雷元素附着|后台挂雷)", t):
        out.add("role_enabler_electro")
    if re.search(r"(挂冰|冰元素附着|后台挂冰)", t):
        out.add("role_enabler_cryo")
    if re.search(r"(挂草|草元素附着|后台挂草)", t):
        out.add("role_enabler_dendro")
    return out

def align_role_text_to_role_ids(role_text: str, alias_index: Dict[str, str]) -> Tuple[List[str], List[str]]:
    tokens = split_role_text(role_text)
    role_ids: Set[str] = set()
    used_tokens: List[str] = []

    for raw in tokens:
        tok = norm(QUAL_RE.sub("", raw))
        if not tok:
            continue
        if tok in alias_index:
            role_ids.add(alias_index[tok])
            used_tokens.append(raw)
        else:
            hits = heuristic_role(tok)
            if hits:
                role_ids |= hits
                used_tokens.append(raw)

    return sorted(role_ids), used_tokens


# -------------------------
# edge factory (你的模板字段)
# -------------------------
def make_edge(subject_id: str,
              predicate: str,
              object_id: str,
              evidence_field: str,
              evidence_value: str,
              evidence_rule: str,
              reasoning_hint: str,
              evidence_side: str = "subject",
              evidence_confidence: float = 1.0) -> Dict[str, Any]:
    return {
        "subject_id": subject_id,
        "predicate": predicate,
        "object_id": object_id,
        "evidence_side": evidence_side,
        "evidence_field": evidence_field,
        "evidence_value": evidence_value,
        "evidence_confidence": evidence_confidence,
        "evidence_rule": evidence_rule,
        "reasoning_hint": reasoning_hint
    }


# -------------------------
# main: build edges
# -------------------------
def build_edges_rich(team_nodes_path: str,
                     team_llm_path: str,
                     character_nodes_path: str,
                     role_tag_path: str,
                     out_path: str) -> None:

    nodes = json.load(open(team_nodes_path, "r", encoding="utf-8"))
    team_llm = json.load(open(team_llm_path, "r", encoding="utf-8"))

    name2cid = load_character_name2id(character_nodes_path)
    role_alias = load_role_alias_index(role_tag_path)

    team_templates = nodes.get("TeamTemplate", [])
    slot_groups = nodes.get("SlotGroup", [])
    slot_templates = nodes.get("SlotTemplate", [])

    # index for convenience
    st_by_id = {st["id"]: st for st in slot_templates}

    edges: List[Dict[str, Any]] = []

    # (1) TeamTemplate -> SlotGroup
    for sg in slot_groups:
        tt_id = sg.get("team_template_id")
        sg_id = sg.get("id")
        if not tt_id or not sg_id:
            continue
        ev = f"group_type={sg.get('group_type')} min={sg.get('min_select')} max={sg.get('max_select')} " \
             f"mutual_exclusive={sg.get('mutual_exclusive')} slots={sg.get('slot_template_ids')}"
        edges.append(make_edge(
            subject_id=tt_id,
            predicate="HAS_SLOT_GROUP",
            object_id=sg_id,
            evidence_field="LLM结构化槽位解析",
            evidence_value=ev,
            evidence_rule="team_strategy_entities.json SlotGroup(team_template_id)->HAS_SLOT_GROUP",
            reasoning_hint=f"{tt_id} 包含槽位组 {sg.get('name')}"
        ))

    # (2) SlotGroup -> SlotTemplate
    for st in slot_templates:
        sg_id = st.get("slot_group_id")
        st_id = st.get("id")
        if not sg_id or not st_id:
            continue
        ev = f"slot={st.get('slot')} must={st.get('must')} need={st.get('need')} evidence={st.get('evidence')}"
        edges.append(make_edge(
            subject_id=sg_id,
            predicate="HAS_SLOT",
            object_id=st_id,
            evidence_field="LLM结构化槽位解析",
            evidence_value=ev,
            evidence_rule="team_strategy_entities.json SlotTemplate(slot_group_id)->HAS_SLOT",
            reasoning_hint=f"{sg_id} 包含槽位 {st.get('slot')}"
        ))

    # (3) SlotTemplate -> RoleTag (from slot.need)
    for st in slot_templates:
        need = st.get("need") or ""
        if not need:
            continue
        role_ids, used_tokens = align_role_text_to_role_ids(need, role_alias)
        for rid in role_ids:
            edges.append(make_edge(
                subject_id=st["id"],
                predicate="REQUIRES_ROLE_TAG",
                object_id=rid,  # 英文 role_tag.id
                evidence_field="slot.need 对齐 role_tag",
                evidence_value=f"need={need} -> tokens={used_tokens}",
                evidence_rule="role_align(slot.need)->role_tag.id",
                reasoning_hint=f"{st.get('slot')} 槽位需要能力：{need}（对齐到 {rid}）",
                evidence_confidence=0.85
            ))

    # (4) CORE / EXAMPLE_MEMBER / CANDIDATE from original LLM file
    fit2conf = {"good": 0.85, "ok": 0.65, "bad": 0.35}
    for entry in team_llm:
        llm = entry.get("llm_result") or {}
        core_name = llm.get("core_character") or entry.get("id") or ""
        for arch in (llm.get("archetypes") or []):
            tt_id = build_tt_id(core_name, arch.get("name") or "")
            # CORE
            core_cid = name2cid.get(core_name)
            if core_cid:
                edges.append(make_edge(
                    subject_id=tt_id,
                    predicate="CORE",
                    object_id=core_cid,
                    evidence_field="archetype.core_evidence",
                    evidence_value=str(arch.get("core_evidence") or ""),
                    evidence_rule="team_strategy_LLM.archetypes.core_evidence",
                    reasoning_hint=f"{core_name} 是 {arch.get('name')} 模板的核心"
                ))

            # EXAMPLE
            ex = arch.get("example_team") or {}
            ex_ev = str(ex.get("evidence") or "")
            for m in (ex.get("members") or []):
                cid = name2cid.get(m)
                if not cid:
                    continue
                edges.append(make_edge(
                    subject_id=tt_id,
                    predicate="EXAMPLE_MEMBER",
                    object_id=cid,
                    evidence_field="example_team.evidence",
                    evidence_value=ex_ev,
                    evidence_rule="team_strategy_LLM.archetypes.example_team",
                    reasoning_hint=f"{m} 出现在 {tt_id} 的示例队伍中"
                ))

            # CANDIDATE
            for c in (arch.get("candidates") or []):
                slot = c.get("slot") or ""
                st_id = build_st_id(tt_id, slot)
                cname = c.get("character") or ""
                cid = name2cid.get(cname)
                if not cid:
                    continue
                why = c.get("why") or []
                evs = c.get("evidence") or []
                ev_text = " | ".join([*why, *evs])[:800]  # 防止太长
                conf = fit2conf.get(c.get("fit"), 0.5)

                edges.append(make_edge(
                    subject_id=st_id,
                    predicate="CANDIDATE",
                    object_id=cid,
                    evidence_field="candidate.why/evidence",
                    evidence_value=ev_text,
                    evidence_rule="team_strategy_LLM.archetypes.candidates",
                    reasoning_hint=f"{cname} 可作为 {slot} 的候选（fit={c.get('fit')} role={c.get('role')}）",
                    evidence_confidence=conf
                ))

    edges = dedup_edges(edges)

    out = {"edges": edges, "edge_count": len(edges)}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("Wrote:", out_path, "edge_count=", len(edges))


if __name__ == "__main__":
    build_edges_rich(
        team_nodes_path="data_preprocess/team_strategy_entities.json",
        team_llm_path="data_preprocess/dataKG/LLM_extracted/team_strategy_LLM.json",
        character_nodes_path="data_preprocess/dataKG/entities/character.json",
        role_tag_path="data_preprocess/dataKG/entities/role_tag.json",
        out_path="data_preprocess/dataKG/relations/team_strategy_edges_rich.json"
    )
