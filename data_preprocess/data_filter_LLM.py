# -*- coding: utf-8 -*-
import json
import os
import time
from openai import OpenAI
from dotenv import load_dotenv
from data_preprocess.data_filter import load_latest_json
from pathlib import Path
from datetime import datetime
from data_preprocess.prompts import ROLE_TAG_PROMPT_V2, MONSTER_PROMPT_V3

load_dotenv()

client = OpenAI(
    api_key=os.getenv("sf_key"),
    base_url="https://api.siliconflow.cn/v1"
)


# ================= LLM抽取函数 =================
def extract_with_llm(system_prompt, text: str):
    """
    使用大模型从攻略文本中抽取角色 RoleTag
    """
    try:
        time.sleep(6)
        response = client.chat.completions.create(
            model="Qwen/Qwen3-8B",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.1,  # 保证稳定
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        print(f"[RoleTag 抽取成功]")
        return json.loads(content)

    except Exception as e:
        print(f"[RoleTag 抽取失败] {e}")
        return None


def run_llm_and_save(
        data_list,
        prompt,
        build_text_fn,
        extract_fn,
        output_file,
        id_key="id"
):
    """
    data_list      : 要处理的数据列表
    prompt         : LLM 用的提示词
    build_text_fn  : 从一条数据中生成喂给 LLM 的文本
    extract_fn     : 调用 LLM 的函数
    output_file    : 输出 json 文件路径
    id_key         : 每条数据的唯一 id 字段名
    """

    output_path = Path(output_file)

    # 已有结果（用于断点续跑）
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            results = json.load(f)
    else:
        results = []

    done_ids = {r[id_key] for r in results}

    for item in data_list:
        item_id = item.get(id_key)
        if not item_id or item_id in done_ids:
            continue

        text = build_text_fn(item)
        if not text.strip():
            continue

        response = extract_fn(prompt, text)

        record = {
            "id": item_id,
            "input_text": text,
            "llm_result": response,
            "time": datetime.now().isoformat()
        }

        results.append(record)
        done_ids.add(item_id)

        # ✅ 每次都写文件（安全）
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"已处理: {item_id}")

    print("全部完成")

if __name__ == "__main__":
    # 1、LLM抽取角色定位
    # strategy_data = load_latest_json("character_strategy_")
    # run_llm_and_save(
    #     data_list=strategy_data,
    #     prompt=ROLE_TAG_PROMPT_V2,
    #     build_text_fn=lambda s: "\n".join(s.get("role_paragraphs", [])),
    #     extract_fn=extract_with_llm,
    #     output_file="data_preprocess/role_tag_LLM.json",
    #     id_key="character"
    # )

    # 2、LLM抽取角色-怪物攻略关系
    with open("data_preprocess/dataKG/entities/monster.json", "r", encoding="utf-8") as f:
        monsters_data = json.load(f)
    monsters_data = [m for m in monsters_data if m.get("strategy")!=""]
    run_llm_and_save(
        data_list=monsters_data,
        prompt=MONSTER_PROMPT_V3,
        build_text_fn=lambda m: f"monster:{m.get('name','')}, strategy:"+m.get("strategy", ""),
        extract_fn=extract_with_llm,
        output_file="data_preprocess/character_monster_LLM1.json",
        id_key="name"
    )