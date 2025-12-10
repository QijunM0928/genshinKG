import json
import csv
import os
from pathlib import Path

def json_to_csv(json_path):
    """单个 JSON 文件转换为 CSV（保留文件名），表头按 JSON 键顺序"""
    json_path = Path(json_path)
    csv_path = json_path.with_suffix(".csv")

    # 读取 JSON
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"{json_path} 必须是 JSON 数组，每个元素为字典")

    if len(data) == 0:
        print(f"{json_path} 是空文件，跳过")
        return

    # 使用第一条记录的键顺序作为表头顺序
    first_item = data[0]
    if not isinstance(first_item, dict):
        raise ValueError(f"{json_path} 的第一条记录不是字典")

    header = list(first_item.keys())

    # 写 CSV
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()

        for item in data:
            # 若后续字典缺少字段，字段自动补空
            writer.writerow({key: item.get(key, "") for key in header})

    print(f"转换完成：{csv_path}")


def batch_convert_json(directory):
    """转换目录下所有 JSON 文件"""
    directory = Path(directory)

    if not directory.exists():
        raise FileNotFoundError(f"路径不存在: {directory}")

    for file in directory.glob("*.json"):
        json_to_csv(file)


if __name__ == "__main__":
    target_dir = "data_preprocess/dataKG/entities"
    batch_convert_json(target_dir)
