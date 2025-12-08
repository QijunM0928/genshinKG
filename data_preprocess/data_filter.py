"""该脚本用于从指定目录加载最新爬取的源数据文件，并按 schema 定义的字段读取和清洗数据。"""

import os
import glob
import json

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

# 1、按schema定义的字段读取/清洗character数据
def get_character_full_info(characters, details):
    characters_merged = []
    for i, c in enumerate(characters):
        merged = {}
        name = c.get("名称", "")
        # 在 details 里找对应的详细信息，details中每个角色有三个字典
        detail1 = next((d for d in details if d.get("character", "") == name and d.get("section", "") == name), {})
        detail2 = next((d for d in details if d.get("character", "") == name and d.get("section", "") == "其他信息"), {})
        # 合并schema定义的图谱所需字段
        merged['id']= f"character{i+1}"
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
        merged["jp_CV"] = safe_get(detail2, "table", "日文CV")
        merged["img_src"] = detail1.get("artworks", "")[0].get("url", "") if detail1.get("artworks", "") else ""

        characters_merged.append(merged)
    return characters_merged


characters_data = get_character_full_info(load_latest_json("character_2"), load_latest_json("character_detail_"))
with open("data_preprocess/dataKG/character.json", "w", encoding="utf-8") as f:
    json.dump(characters_data, f, ensure_ascii=False, indent=2)


# 2、材料数据