"""该脚本用于从指定目录加载最新爬取的源数据文件，并按 schema 定义的字段读取和清洗数据。同时抽取显性关系"""

import os
import re
import glob
import json

# 按材料类型配置 predicate 和解释模板
MATERIAL_REL_CONFIG = {
    # 通用 predicate
    "DEFAULT": {
        "predicate": "needs_material",
        "hint_template": "{subject_name} 需要材料 {material_name} 用于{usage}"
    }
}


""" --- part0 函数封装 --- """

def load_latest_json(prefix, base_dir="srccrawler/data"):
    """
    prefix: 文件名前缀，如 "character_" 或 "character_detail_"
    base_dir: 放 json 的目录
    """
    # 拼出搜索路径，比如 "srccrawler/data/character_*.json"
    pattern = os.path.join(base_dir, f"{prefix}*.json")
    files = glob.glob(pattern)

    if not files:
        raise FileNotFoundError(f"没有找到匹配 {pattern} 的文件")

    # 按修改时间找最新的一个
    latest_file = max(files, key=os.path.getmtime)
    print("读取文件:", latest_file)

    with open(latest_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def safe_get(data, *keys, default=""):
    """
    安全获取多层字典的值，不存在就返回 default
    """
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, default)
        else:
            return default
    return data


def extract_char_usage(text: str, keep_latest=False):
    """
    从原神数据字符串中抽取角色名与用途。

    参数:
        text (str): 输入字符串，例如:
                    "恰斯卡 （80级突破） 温迪 （80级突破） 法尔伽 法尔伽 （80级突破）"
        keep_latest (bool): 是否保留最新出现的用途。
                            False: 保留第一次出现的用途（默认）
                            True:  若后面出现用途，将覆盖之前的值

    返回:
        dict: { 角色名: 用途 }
    """

    # 兼容中文全角括号（），英文括号()
    pattern = re.compile(
        r"([\u4e00-\u9fa5]+)"  # 角色名：连续中文
        r"(?:\s*[（(]\s*([^）)]+?)\s*[）)])?"  # 用途：括号内内容，非贪婪匹配
    )

    result = {}

    for name, usage in pattern.findall(text):
        name = name.strip()
        usage = usage.strip() if usage else ""

        if keep_latest:
            # 覆盖用途
            result[name] = usage or result.get(name, "")
        else:
            # 保留第一次出现的用途
            if name not in result:
                result[name] = usage

    return result


def name_to_id(data):
    n2id = {}
    for d in data:
        d_name = d.get("name", "")
        if d_name:
            n2id[d_name] = d.get("id", "")
    return n2id



""" --- part1 实体数据清洗 --- """

# 1、按schema定义的字段读取/清洗character数据
def get_character_full(characters, details):
    characters_merged = []
    stories_merged = []
    for i, c in enumerate(characters):
        merged = {}
        stories = {}
        name = c.get("名称", "")
        # 在 details 里找对应的详细信息，details中每个角色有三个字典
        detail1 = next((d for d in details if d.get("character", "") == name and d.get("section", "") == name), {})
        detail2 = next((d for d in details if d.get("character", "") == name and d.get("section", "") == "其他信息"),
                       {})
        detail3 = next((d for d in details if d.get("character", "") == name and d.get("section", "") == "角色故事"),
                       {})
        # 合并schema定义的图谱所需字段
        merged['id'] = f"character{i + 1}"
        merged["name"] = name
        merged["nickname"] = [x.strip() for x in safe_get(detail2, "table", "昵称/外号").split('、') if x.strip()]
        merged["title"] = safe_get(detail1, "table", "称号")
        merged["gender"] = c.get("性别", "")
        merged["body_type"] = safe_get(detail2, "table", "体型")
        merged["rarity"] = c.get("稀有度", "")
        merged["element"] = c.get("元素属性", "")
        merged["primordial_force"] = safe_get(detail1, "table", "始基力")
        merged["weapon_type"] = c.get("武器类型", "")
        merged["region"] = safe_get(detail1, "table", "所属地区")
        merged["affiliation"] = safe_get(detail2, "table", "所属")
        merged["profession"] = safe_get(detail2, "table", "职业")
        merged["species"] = safe_get(detail1, "table", "种族")
        merged["constellation"] = safe_get(detail1, "table", "命之座")
        merged["special_dish"] = safe_get(detail1, "table", "特殊料理")
        merged["TAG"] = [x.strip() for x in c.get("TAG", "").split('、') if x.strip()]
        merged["description"] = safe_get(detail1, "table", "介绍")
        merged["birthday"] = safe_get(detail2, "table", "生日")
        merged["cn_CV"] = safe_get(detail2, "table", "中文CV")
        merged["img_src"] = detail1.get("artworks", "")[0].get("url", "") if detail1.get("artworks", "") else ""
        characters_merged.append(merged)

        stories["id"] = f"character_story{i + 1}"
        stories["name"] = name
        stories["stories"] = detail3.get("table", {})
        stories_merged.append(stories)
    return characters_merged, stories_merged


# 提取character, story数据
characters_data, stories_data = get_character_full(load_latest_json("character_2"),
                                                   load_latest_json("character_detail_"))
with open("data_preprocess/dataKG/entities/character.json", "w", encoding="utf-8") as f:
    json.dump(characters_data, f, ensure_ascii=False, indent=2)
with open("data_preprocess/dataExternal/character_story.json", "w", encoding="utf-8") as f:
    json.dump(stories_data, f, ensure_ascii=False, indent=2)


# 2、武器数据
def get_weapon_full(weapons):
    weapons_merged = []
    for i, w in enumerate(weapons):
        merged = {
            "id": f"weapon{i + 1}",
            "name": w.get("名称", ""),
            "type": w.get("类型", ""),
            "rarity": w.get("稀有度", "") + "星",
            "source": w.get("获取途径", ""),
            "min_attack": w.get("初始攻击力", ""),
            "max_attack": w.get("最高攻击力", ""),
            "min_subproperty": w.get("初始副属性", ""),
            "max_subproperty": w.get("最高副属性", ""),
            "effect": w.get("技能", ""),
            "img_src": w.get("图标", "")
        }
        weapons_merged.append(merged)
    return weapons_merged


weapons_data = get_weapon_full(load_latest_json("weapon_"))
with open("data_preprocess/dataKG/entities/weapon.json", "w", encoding="utf-8") as f:
    json.dump(weapons_data, f, ensure_ascii=False, indent=2)


# 3、材料数据
def get_material_full(materials):
    materials_merged = []
    for i, m in enumerate(materials):
        merged = {
            "id": f"material{i + 1}",
            "name": m.get("name", ""),
            "type": m.get("type", ""),
            "source": m.get("source", ""),
            "usage": extract_char_usage(m.get("usage", ""), keep_latest=True),
            "img_src": m.get("icon", "")
        }
        materials_merged.append(merged)
    return materials_merged


materials_data = get_material_full(load_latest_json("material_"))
for m in materials_data:
    if m.get("type") != "天赋培养素材":
        continue

    usage = m.get("usage")
    # 确保 usage 是 dict 且包含 "角色"
    if isinstance(usage, dict) and "角色" in usage:
        common_usage = usage.get("角色", "")

        # 给除 "角色" 外的所有角色补上用途
        for name in list(usage.keys()):
            if name == "角色":
                continue
            if not usage[name]:  # 只覆盖空值
                usage[name] = common_usage

        # 最后删除 "角色" 这个虚拟 key
        usage.pop("角色", None)
with open("data_preprocess/dataKG/entities/material.json", "w", encoding="utf-8") as f:
    json.dump(materials_data, f, ensure_ascii=False, indent=2)


# 4、语音数据
def get_voice_full(voices):
    voices_merged = []
    i = 0
    for voice in voices:
        name = voice.get("character", "")
        for v in voice.get("voices", []):
            if not isinstance(v, dict):
                continue
            i += 1
            merged = {
                "id": f"character_voice_{i}",
                "name": name,
                "title": v.get("title", ""),
                "cn_text": v.get("cn_text", ""),
                "cn_audio": v.get("cn_audio", "")
            }
            voices_merged.append(merged)
    return voices_merged


voices_data = get_voice_full(load_latest_json("character_voice_"))
with open("data_preprocess/dataKG/entities/character_voice.json", "w", encoding="utf-8") as f:
    json.dump(voices_data, f, ensure_ascii=False, indent=2)


# 5、怪物数据
def get_monster_full(monsters):
    monsters_merged = []
    for i, m in enumerate(monsters):
        merged = {
            "id": f"monster{i + 1}",
            "name": m.get("name", ""),
            "element": m.get("element", ""),
            "type": m.get("type", ""),
            "refresh_time": m.get("refresh time", ""),
            "region": re.split(r"[,\s、]+", m.get("location", "")),
            "TAG": re.split(r"[,\s、]+", m.get("TAG", "")),
            "drop": list(set(m.get("drop", ""))),
            "img_src": m.get("icon", "")
        }
        parts = []
        if m.get("recommend", []):
            parts.extend(m["recommend"])
        if m.get("info", ""):
            parts.append(m["info"])
        merged["strategy"] = "\n---\n".join(parts)

        monsters_merged.append(merged)
    return monsters_merged


monsters_data = get_monster_full(load_latest_json("monster_"))
with open("data_preprocess/dataKG/entities/monster.json", "w", encoding="utf-8") as f:
    json.dump(monsters_data, f, ensure_ascii=False, indent=2)


# 6、攻略数据（待补充）

def get_strategy_full(strategies):
    pass


""" --- part2 关系抽取 --- """

# 实体名称跟id的字典，方面查找
name2id = {}
for data in [characters_data, materials_data, weapons_data, monsters_data]:
    name2id.update(name_to_id(data))
all_entity_name_set = name2id.keys()

def build_material_relation(subject_name, material, usage_text):
    """
    subject_name: 可能是角色名、武器名等
    material: 一条材料 JSON（来自 materials_data）
    usage_text: usage[subject_name] 的值（一般是用途描述）
    """
    subject_id = name2id.get(subject_name)
    if not subject_id:
        return None  # 实体表里没有这个名字，直接丢弃

    material_id = material.get("id", "")
    material_name = material.get("name", "")
    material_type = material.get("type", "")

    # 选配置：优先使用具体 type，否则用 DEFAULT
    cfg = MATERIAL_REL_CONFIG.get(material_type, MATERIAL_REL_CONFIG["DEFAULT"])
    predicate = cfg["predicate"]

    evidence_field = "usage"  # 这里统一约定来自 usage 字段

    relation = {
        "subject_id": subject_id,
        "predicate": predicate,
        "object_id": material_id,

        "evidence_side": "object",                 # 证据在材料那边（材料的 usage）
        "evidence_field": evidence_field,          # usage
        "evidence_value": str(usage_text),         # usage 的原始值
        "evidence_confidence": 1.0,                # 结构化数据，置信度可以直接 1.0
        "evidence_rule": f"{evidence_field}=>{predicate}",

        "reasoning_hint": cfg["hint_template"].format(
            subject_name=subject_name,
            material_name=material_name,
            usage=usage_text
        )
    }
    return relation

# 1、实体-需要-材料 关系
relations = []

for m in materials_data:
    usage = m.get("usage", {})
    if not isinstance(usage, dict):
        continue

    # 所有 带usage 的材料都尝试处理
    for subject_name, use in usage.items():
        # 只处理实体表中存在的名字（角色、武器、材料等）
        if subject_name not in all_entity_name_set or not use:
            continue

        relation = build_material_relation(subject_name, m, use)
        if relation:
            relations.append(relation)

    if relations:
        with open("data_preprocess/dataKG/relations/needs_material_relation.json", "w", encoding="utf-8") as f:
            json.dump(relations, f, ensure_ascii=False, indent=2)

