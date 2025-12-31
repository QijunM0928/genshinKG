from neo4j import GraphDatabase
import pandas as pd
import os


AURA_URI = "neo4j+s://1e53c988.databases.neo4j.io"
AURA_USER = "neo4j"
AURA_PASSWORD = "ZS-rBIrq-tN6CCQj6KpUksdPby16HFje9Fn_rvH_fLc"
ENTITY_CSV_FOLDER = "dataKG/entities_csv"
BATCH_SIZE = 500

class SimpleAuraImporter:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        print("连接到Aura数据库")

    def close(self):
        self.driver.close()

    def import_all_entities(self, folder_path):
        """导入文件夹内所有CSV文件，使用文件名作为标签"""
        csv_files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]
        
        if not csv_files:
            print(" 没有找到CSV文件")
            return
        
        total_imported = 0
        
        for csv_file in csv_files:
            # 使用文件名作为标签
            label = csv_file.replace('.csv', '')
            file_path = os.path.join(folder_path, csv_file)
            
            success, count = self.import_single_file(file_path, label)
            if success:
                total_imported += count
        self.verify_import()

    def import_single_file(self, csv_path, label):
        """导入单个CSV文件"""
        try:
            df = pd.read_csv(csv_path, encoding='utf-8-sig')
            
            with self.driver.session() as session:
                # 动态导入：id列固定，其他列自动映射
                query = f"""
                UNWIND $rows AS row
                CREATE (n:{label} {{id: row.id}})
                SET n += apoc.map.removeKeys(row, ['id'])
                """
                
                # 分批导入
                for i in range(0, len(df), BATCH_SIZE):
                    batch = df.iloc[i:i+BATCH_SIZE].to_dict('records')
                    session.run(query, rows=batch)
                    
                    batch_num = i // BATCH_SIZE + 1
                    total_batches = (len(df) + BATCH_SIZE - 1) // BATCH_SIZE
                    if batch_num % 10 == 0 or batch_num == total_batches:
                        print(f"   进度: {min(i+BATCH_SIZE, len(df))}/{len(df)} 行")
            
            return True, len(df)
            
        except Exception as e:
            print(f"导入失败: {e}")
            return False, 0

    def verify_import(self):
        """验证导入结果"""
        try:
            with self.driver.session() as session:
                result = session.run("MATCH (n) RETURN count(n) as total")
                print(f"数据库总节点数: {result.single()['total']}")
                
                result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as label, count(*) as count
                ORDER BY label
                """)
                
                print("各标签节点数:")
                for record in result:
                    print(f"  {record['label']}: {record['count']}")
                    
        except Exception as e:
            print(f"验证时出错: {e}")



if __name__ == "__main__":
    importer = SimpleAuraImporter(AURA_URI, AURA_USER, AURA_PASSWORD)
    
    try:
        importer.import_all_entities(ENTITY_CSV_FOLDER)
    except Exception as e:
        print(f"\n 错误: {e}")
    finally:
        importer.close()
