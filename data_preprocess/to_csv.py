import json
import pandas as pd
import os
from pathlib import Path

def entity_to_csv():
    entities_folder = "dataKG/entities"
    output_folder = "dataKG/entities_csv"

    os.makedirs(output_folder, exist_ok=True)

    json_files = [f for f in os.listdir(entities_folder) if f.endswith('.json')]

    for json_file in json_files:
        input_path = os.path.join(entities_folder, json_file)
        output_name = json_file.replace('.json', '.csv')
        output_path = os.path.join(output_folder, output_name)
        
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                # 如果是列表，直接转换
                df = pd.DataFrame(data)
                df.to_csv(output_path, index=False, encoding='utf-8-sig')
            elif isinstance(data, dict):
                # 如果是字典，包装成列表
                for name, d in data.item():
                    df = pd.DataFrame([d])
                    df.to_csv(output_path, index=False, encoding='utf-8-sig')
            else:
                print(f"⚠️  {json_file}: 未知格式，跳过")
                continue
            
            print(f"✅  {json_file} → {output_name} ({len(df)}行)")
            
        except Exception as e:
            print(f"❌  {json_file}: 转换失败 - {e}")



def relation_to_csv():
    entities_folder = "dataKG/relations"
    output_folder = "dataKG/relations_csv" 

    os.makedirs(output_folder, exist_ok=True)

    json_files = [f for f in os.listdir(entities_folder) if f.endswith('.json')]

    for json_file in json_files:
        input_path = os.path.join(entities_folder, json_file)
        output_name = json_file.replace('.json', '.csv')
        output_path = os.path.join(output_folder, output_name)
        
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                # 如果是列表，直接转换
                df = pd.DataFrame(data)
                df.to_csv(output_path, index=False, encoding='utf-8-sig')
            elif isinstance(data, dict):
                # 如果是字典，包装成列表
                for name, d in data.items():
                    df = pd.DataFrame(d)
                    output_path = os.path.join(output_folder, f"{name}.csv")
                    df.to_csv(output_path, index=False, encoding='utf-8-sig')
            else:
                print(f"⚠️  {json_file}: 未知格式，跳过")
                continue
            
        except Exception as e:
            print(f"❌  {json_file}: 转换失败 - {e}")

if __name__ == "__main__":
    entity_to_csv()
    relation_to_csv()