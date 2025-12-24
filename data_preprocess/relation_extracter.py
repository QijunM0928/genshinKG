"""该脚本用于从指定目录加载最新爬取的源数据文件，并按 schema 定义的字段读取和清洗数据。同时抽取显性关系并保存于relations"""

import os
import re
import glob
import json
import csv
from pathlib import Path
from typing import Dict, Any, Iterable, Optional
from data_preprocess.prompts import NOISE_RELATIONS, RELATION_REWRITE_MAP

# 按材料类型配置 predicate 和解释模板
MATERIAL_REL_CONFIG = {
    # 通用 predicate
    "DEFAULT": {
        "predicate": "needs_material",
        "hint_template": "{subject_name} 需要材料 {material_name} 用于{usage}"
    }
}

def load_json_entities(
    base_dir: str = "data_preprocess/dataKG/entities",
    names: Optional[Iterable[str]] = None,
    encoding: str = "utf-8"
) -> Dict[str, Any]:
    """
    从 base_dir 读取多个 json 文件并返回：
      {"character": ..., "material": ..., ...}

    - names=None: 自动读取目录下所有 .json
    - names=['character','weapon'] 或 ['character.json', ...]: 只读指定文件
    """
    base = Path(base_dir)

    if names is None:
        paths = sorted(base.glob("*.json"))
    else:
        paths = []
        for n in names:
            n = f"{n}.json" if not str(n).endswith(".json") else str(n)
            paths.append(base / n)

    data: Dict[str, Any] = {}
    for p in paths:
        with p.open("r", encoding=encoding) as f:
            data[p.stem] = json.load(f)
    return data


def name_to_id(data):
    n2id = {}
    for d in data:
        d_name = d.get("name", "")
        if d_name:
            n2id[d_name] = d.get("id", "")
    return n2id


entities = load_json_entities(names=["character", "material", "weapon", "monster", "artifact", "country", "element", "reaction"])
characters = entities["character"]
materials  = entities["material"]
weapons    = entities["weapon"]
monsters   = entities["monster"]
artifacts  = entities["artifact"]
countries  = entities["country"]
elements = entities["element"]
reactions = entities["reaction"]

with open("data_preprocess/dataExternal/character_strategy.json", "r", encoding="utf-8") as f:
    strategies = json.load(f)


""" --- part2 关系抽取 --- """

# 实体名称跟id的字典，方面查找
name2id = {}
for d in [characters, materials, weapons, monsters, artifacts, countries, elements, reactions]:
    name2id.update(name_to_id(d))
all_entity_name_set = name2id.keys()


# 1、实体-需要-材料 关系
def get_needs_material_relations():
    needs_material_relations = []

    predicate_default = MATERIAL_REL_CONFIG.get("DEFAULT", {}).get("predicate", "needs_material")
    hint_default = MATERIAL_REL_CONFIG.get("DEFAULT", {}).get("hint_template", "实体 {subject_name} 需要材料 {material_name}，用途：{usage}")

    for mat in materials:
        mat_name = mat.get("name", "")
        mat_id = mat.get("id", "")
        mat_type = mat.get("type", "")

        usage = mat.get("usage", {})
        if not isinstance(usage, dict):
            continue

        # 选配置：优先使用具体 type，否则用 DEFAULT
        cfg = MATERIAL_REL_CONFIG.get(mat_type, MATERIAL_REL_CONFIG.get("DEFAULT", {}))
        predicate = cfg.get("predicate", predicate_default)
        hint_template = cfg.get("hint_template", hint_default)

        evidence_field = "usage"

        for subject_name, use_text in usage.items():
            # 只处理实体表中存在的名字（角色、武器、材料等）
            if subject_name not in all_entity_name_set or not use_text:
                continue

            subject_id = name2id.get(subject_name)
            if not subject_id:
                continue
            if not mat_id:
                continue

            relation = {
                "subject_id": subject_id,
                "predicate": predicate,
                "object_id": mat_id,

                "evidence_side": "object",               # 证据在材料侧（usage 字段）
                "evidence_field": evidence_field,
                "evidence_value": str(use_text),
                "evidence_confidence": 1.0,
                "evidence_rule": f"{evidence_field}=>{predicate}",

                "reasoning_hint": hint_template.format(
                    subject_name=subject_name,
                    material_name=mat_name,
                    usage=use_text
                )
            }

            needs_material_relations.append(relation)

    with open("data_preprocess/dataKG/relations/needs_material_relation.json", "w", encoding="utf-8") as f:
        json.dump(needs_material_relations, f, ensure_ascii=False, indent=2)

# 2、怪物-掉落-材料 关系
def get_drops_material_relations():
    drops_material_relations = []
    predicate = "drops_material"
    evidence_field = "drop"
    for m in monsters:
        m_name = m.get("name", "")
        m_id = m.get("id", "")
        m_drop = m.get("drop", [])
        if not isinstance(m_drop, list):
            continue

        for object_name in m_drop:
            if object_name not in all_entity_name_set:
                continue
            relation = {
                "subject_id": m_id,
                "predicate": predicate,
                "object_id": name2id.get(object_name),

                "evidence_side": "subject",
                "evidence_field": evidence_field,
                "evidence_value": m_drop,
                "evidence_confidence": 1.0,  # 结构化数据，置信度可以直接 1.0
                "evidence_rule": f"{evidence_field}=>{predicate}",

                "reasoning_hint": f"击杀怪物 {m_name} 掉落材料 {object_name}"
            }
            drops_material_relations.append(relation)
    with open("data_preprocess/dataKG/relations/drops_material_relation.json", "w", encoding="utf-8") as f:
        json.dump(drops_material_relations, f, ensure_ascii=False, indent=2)


# 3、角色-来自-国家 关系
def get_from_country_relations():
    from_country_relations = []
    predicate = "from_country"
    evidence_field = "country"
    for c in characters:
        c_name = c.get("name", "")
        c_id = c.get("id", "")
        c_country = c.get("country", "")
        for ct in countries:
            if ct.get("name", "") != c_country:
                continue
            relation = {
                "subject_id": c_id,
                "predicate": predicate,
                "object_id": ct.get("id", ""),
                "evidence_side": "subject",
                "evidence_field": evidence_field,
                "evidence_value": c_country,
                "evidence_confidence": 1.0,
                "evidence_rule": f"{evidence_field}=>{predicate}",
                "reasoning_hint": f"角色 {c_name} 来自于 {c_country} 地区"
            }
            from_country_relations.append(relation)
    with open("data_preprocess/dataKG/relations/from_country_relation.json", "w", encoding="utf-8") as f:
        json.dump(from_country_relations, f, ensure_ascii=False, indent=2)

# 4、角色-拥有-元素 关系
def get_has_element_relations():
    has_element_relations = []
    predicate = "has_element"
    evidence_field = "element"
    for c in characters:
        c_name = c.get("name", "")
        c_id = c.get("id", "")
        c_element = c.get("element", "")
        for e in elements:
            if e.get("name", "") != c_element:
                continue
            relation = {
                "subject_id": c_id,
                "predicate": predicate,
                "object_id": e.get("id", ""),
                "evidence_side": "subject",
                "evidence_field": evidence_field,
                "evidence_value": c_element,
                "evidence_confidence": 1.0,
                "evidence_rule": f"{evidence_field}=>{predicate}",
                "reasoning_hint": f"角色 {c_name} 拥有 {c_element} 元素能力"
            }
            has_element_relations.append(relation)
    with open("data_preprocess/dataKG/relations/has_element_relation.json", "w", encoding="utf-8") as f:
        json.dump(has_element_relations, f, ensure_ascii=False, indent=2)


# 5、角色-适合-圣遗物 关系
def get_suits_artifact_relations():
    suits_artifact_relations = []
    predicate = "suits"
    evidence_field = "圣遗物-角色攻略文本推理"
    for a in artifacts:
        a_name = a.get("name", "")
        a_id = a.get("id", "")
        a_suits_roles = a.get("recommended_roles", [])
        for _ in a_suits_roles:
            if not isinstance(_, dict) or not _.get("roles", []):
                continue
            for char_name in _.get("roles"):
                relation = {
                    "subject_id": name2id.get(char_name),
                    "predicate": predicate,
                    "object_id": a_id,
                    "evidence_side": "object",
                    "evidence_field": evidence_field,
                    "evidence_value": _.get("desc", ""),
                    "evidence_confidence": 0.9, # 攻略存在主观判断
                    "evidence_rule": f"{evidence_field}=>{predicate}",
                    "reasoning_hint": f"角色 {char_name} 适配圣遗物 {a_name} 的套装效果"
                }
                suits_artifact_relations.append(relation)
    with open("data_preprocess/dataKG/relations/suits_artifact_relation.json", "w", encoding="utf-8") as f:
        json.dump(suits_artifact_relations, f, ensure_ascii=False, indent=2)

# 6、角色-适合-武器 关系
def get_suits_weapon_relations():
    suits_weapon_relations = []
    predicate = "suits_weapon"
    evidence_field = "角色-武器列表抽取"
    for s in strategies:
        c_name = s.get("character", "")
        c_id = name2id.get(c_name)
        for w in s.get("weapons", []):
            w_name = w.get("weapon", "")
            w_id =name2id.get(w_name)
            if not c_id or not w_id:
                continue
            relation = {
                "subject_id": c_id,
                "predicate": predicate,
                "object_id": w_id,
                "priority": w.get("priority", ""),
                "evidence_side": "subject",
                "evidence_field": evidence_field,
                "evidence_value": w.get("description", ""),
                "evidence_confidence": 0.9, # 攻略存在主观判断
                "evidence_rule": f"{evidence_field}=>{predicate}",
                "reasoning_hint": f"角色 {c_name} 适合武器 {w_name} 的效果"
            }
            suits_weapon_relations.append(relation)
    with open("data_preprocess/dataKG/relations/suits_weapon_relation.json", "w", encoding="utf-8") as f:
        json.dump(suits_weapon_relations, f, ensure_ascii=False, indent=2)

# 7、元素/反应-触发-反应 关系
def get_trigger_reaction_relations():
    trigger_reaction_relations = []
    predicate = "trigger"
    evidence_filed = "reaction_element"
    e_r = []
    e_names=[]
    for d in elements:
        e_r.append(d["name"])
        e_names.append(d["name"])
    for d in reactions:
        e_r.append(d["name"])
    for r in reactions:
        for _ in e_r:
            if _ in r["reaction_element"]:
                relation = {
                    "subject_id": name2id.get(_),
                    "predicate": predicate,
                    "object_id": r["id"],
                    "evidence_side": "object",
                    "evidence_field": evidence_filed,
                    "evidence_value": r[evidence_filed],
                    "evidence_confidence": 1.0,
                    "evidence_rule": f"{evidence_filed}=>{predicate}",
                    "reasoning_hint": f"{'元素' if _ in e_names else '反应'} {_} 触发 {r['name']} 反应"
                }
                trigger_reaction_relations.append(relation)
    with open("data_preprocess/dataKG/relations/trigger_reaction_relation.json", "w", encoding="utf-8") as f:
        json.dump(trigger_reaction_relations, f, ensure_ascii=False, indent=2)

# 8、角色-关系-角色
def get_character2character_relations():
    character2character_relations=[]
    st=set()
    evidence_field="角色-语音文本推理"
    with open('data_preprocess/dataKG/LLM_extracted/character2character_LLM.json', 'r', encoding='utf-8') as f:
        c2c_data = json.load(f)
    for c2c in c2c_data:
        if not isinstance(c2c.get("llm_result", {}),dict):
            continue
        res = c2c.get("llm_result")
        if not res.get("relations", []):
            continue
        subject_name = res.get("subject", "")
        object_name = res.get("object", "")
        subject_id = name2id.get(subject_name, "")
        object_id = name2id.get(object_name, "")
        for r in res.get("relations", []):
            predicate = r.get("predicate", "")
            if predicate in NOISE_RELATIONS:
                continue
            if predicate in RELATION_REWRITE_MAP:
                predicate = RELATION_REWRITE_MAP[predicate]
            relation = {
                "subject_id": subject_id,
                "predicate": predicate,
                "object_id": object_id,
                "evidence_side": "subject" if r.get("direction", "")=="subject_to_object" else "object",
                "evidence_field": evidence_field,
                "evidence_value": r.get("evidence", ""),
                "evidence_confidence": r.get("confidence", 0.0),
                "evidence_rule": f"{evidence_field}=>{predicate}",
                "reasoning_hint": r.get("reasoning_hint", "")
            }
            character2character_relations.append(relation)
            st.add(predicate)
    with open("data_preprocess/dataKG/relations/character2character_relation.json", "w", encoding="utf-8") as f:
        json.dump(character2character_relations, f, ensure_ascii=False, indent=2)
    print(st)
    print(len(character2character_relations))
    print(len(st))


# 9、角色-属于-角色定位 关系
def get_character_belongs_role_tag_relations():
    character_belongs_role_tag_relations=[]
    predicate="belongs_role_tag"
    evidence_field = "角色-定位文本推理"
    with open('data_preprocess/dataKG/LLM_extracted/role_tag_LLM.json', 'r', encoding='utf-8') as f:
        role_tag_data = json.load(f)
    for rt in role_tag_data:
        character_name = rt.get("id", "")
        character_id = name2id.get(character_name, "")
        res=rt.get("llm_result", {}).get("items", [])
        if not res:
            continue
        res=res[0]
        for tag in res.get("role_tags", []):
            role_id = tag.get("role_id", "")
            relation = {
                "subject_id": character_id,
                "predicate": predicate,
                "object_id": role_id,
                "evidence_side": "subject",
                "evidence_field": evidence_field,
                "evidence_value": tag.get("evidence", ""),
                "evidence_confidence": tag.get("confidence", 0.0),
                "evidence_rule": f"{evidence_field}=>{predicate}",
                "reasoning_hint": character_name+": "+tag.get("reasoning_hint", "")
            }
            character_belongs_role_tag_relations.append(relation)
    with open("data_preprocess/dataKG/relations/character_belongs_role_tag_relation.json", "w", encoding="utf-8") as f:
        json.dump(character_belongs_role_tag_relations, f, ensure_ascii=False, indent=2)

# 10、角色-克制-怪物 关系（仅BOSS怪）
def get_character_restrains_monster_relations():
    character_restrains_monster_relations = []
    predicate = "restrains"
    evidence_field="怪物攻略文本推理"
    with open('data_preprocess/dataKG/LLM_extracted/character_monster_LLM.json', 'r', encoding='utf-8') as f:
        c_m_data = json.load(f)
    for cm in c_m_data:
        if not isinstance(cm.get("llm_result", {}),dict):
            continue
        res = cm.get("llm_result")
        if not res.get("subjects", []):
            continue
        object_name = cm.get("id", "")
        object_id = name2id.get(object_name, "")
        for subject_name in res.get("subjects", []):
            subject_id = name2id.get(subject_name, "")
            relation = {
                "subject_id": subject_id,
                "predicate": predicate,
                "object_id": object_id,
                "evidence_side": "object",
                "evidence_field": evidence_field,
                "evidence_value": res.get("evidence", ""),
                "evidence_confidence": res.get("confidence", 0.0),
                "evidence_rule": f"{evidence_field}=>{predicate}",
                "reasoning_hint": f"{subject_name} 克制 {object_name}: {res.get('reasoning_hint', '')}"
            }
            character_restrains_monster_relations.append(relation)
    with open("data_preprocess/dataKG/relations/character_restrains_monster_relation.json", "w", encoding="utf-8") as f:
        json.dump(character_restrains_monster_relations, f, ensure_ascii=False, indent=2)

if __name__=="__main__":
    pass
    # get_needs_material_relations()
    # get_drops_material_relations()
    # get_from_country_relations()
    # get_has_element_relations()
    # get_suits_artifact_relations()
    # get_suits_weapon_relations()
    # get_trigger_reaction_relations()
    get_character2character_relations()
    # get_character_belongs_role_tag_relations()
    # get_character_restrains_monster_relations()