from neo4j import GraphDatabase
import pandas as pd
import os

AURA_URI = "neo4j+s://1e53c988.databases.neo4j.io"
AURA_USER = "neo4j"
AURA_PASSWORD = "ZS-rBIrq-tN6CCQj6KpUksdPby16HFje9Fn_rvH_fLc"
RELATION_CSV_FOLDER = "dataKG/relations_csv"
BATCH_SIZE = 500 

class RelationImporter:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        print("已连接到Aura数据库")

    def close(self):
        self.driver.close()

    def import_all_relations(self, folder_path):
        """导入文件夹内所有关系CSV文件"""
        csv_files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]
        
        if not csv_files:
            print("没有找到CSV文件")
            return
        
        total_imported = 0
        failed_files = []
        
        for csv_file in csv_files:
            file_path = os.path.join(folder_path, csv_file)
            success, count = self.import_single_relation_file(file_path)
            
            if success:
                total_imported += count
            else:
                failed_files.append(csv_file)
        
        if failed_files:
            print(f"\n 失败的文件:")
            for f in failed_files:
                print(f"  - {f}")
        
    
    def import_single_relation_file(self, csv_path):
        """导入单个关系CSV文件"""
        file_name = os.path.basename(csv_path)
        
        try:
            # 读取CSV文件
            df = pd.read_csv(csv_path, encoding='utf-8-sig')
            print(f"\n📤 处理文件: {file_name}")
            print(f"   总关系数: {len(df)}")
            
            required_cols = ['subject_id', 'predicate', 'object_id']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                print(f"缺少必要列: {missing_cols}")
                return False, 0
                   
            property_cols = [col for col in df.columns if col not in required_cols]         
            
            with self.driver.session() as session:
                # 查询结构：查找两个节点，创建关系，设置关系属性
                query = """
                UNWIND $rows AS row
                MATCH (source {id: row.subject_id})
                MATCH (target {id: row.object_id})
                CALL apoc.create.relationship(
                    source, 
                    row.predicate,
                    apoc.map.removeKeys(row, ['subject_id', 'predicate', 'object_id']),
                    target
                ) YIELD rel
                RETURN count(rel)
                """
                
                # 分批导入
                success_count = 0
                for i in range(0, len(df), BATCH_SIZE):
                    batch = df.iloc[i:i+BATCH_SIZE]
                    
                    # 转换批次为字典列表
                    rows = batch.to_dict('records')
                    
                    try:
                        result = session.run(query, rows=rows)

                        summary = result.consume()
                        success_count += len(batch)
                        
                        batch_num = i // BATCH_SIZE + 1
                        total_batches = (len(df) + BATCH_SIZE - 1) // BATCH_SIZE
                        
                        if batch_num % 5 == 0 or batch_num == total_batches:
                            print(f"   进度: {min(i+BATCH_SIZE, len(df))}/{len(df)} 行")
                    
                    except Exception as batch_error:
                        print(f"   批次 {batch_num} 失败: {batch_error}")
                        continue
                
                print(f" 成功导入: {success_count}/{len(df)} 条关系")
                return True, success_count
                
        except Exception as e:
            print(f"❌ 处理文件 {file_name} 失败: {e}")
            return False, 0
    
    
    def check_missing_nodes(self, csv_path):
        """检查关系CSV中引用了哪些不存在于数据库中的节点"""
        try:
            df = pd.read_csv(csv_path, encoding='utf-8-sig')
            subject_ids = df['subject_id'].unique()
            object_ids = df['object_id'].unique()
            all_referenced_ids = set(list(subject_ids) + list(object_ids))
            
            with self.driver.session() as session:
                # 查询数据库中实际存在的节点ID
                result = session.run("MATCH (n) RETURN n.id as node_id")
                existing_ids = set([record["node_id"] for record in result if record["node_id"]])
                
                # 找出缺失的ID
                missing_ids = all_referenced_ids - existing_ids
                
                if missing_ids:
                    print(f"\n 发现 {len(missing_ids)} 个未找到的节点ID")
                    print(f"示例缺失ID: {list(missing_ids)[:10]}")
                    return False, missing_ids
                else:
                    print("所有引用的节点ID在数据库中都存在")
                    return True, set()
                    
        except Exception as e:
            print(f"检查缺失节点时出错: {e}")
            return False, set()

if __name__ == "__main__":
    importer = RelationImporter(AURA_URI, AURA_USER, AURA_PASSWORD)
    
    try:
        importer.import_all_relations(RELATION_CSV_FOLDER) 
    except Exception as e:
        print(f"\n 导入过程发生错误: {e}")

    finally:
        importer.close()