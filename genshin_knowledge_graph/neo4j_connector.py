"""
Neo4j数据库连接和操作模块
"""
from neo4j import GraphDatabase, BoltDriver
from neo4j.exceptions import Neo4jError, ServiceUnavailable
import streamlit as st
from typing import Optional, List, Dict, Any, Tuple
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GenshinKnowledgeGraph:
    """
    原神知识图谱数据库连接器
    
    封装所有Neo4j数据库操作，提供安全连接和查询功能
    """
    
    def __init__(self):
        """初始化连接器，但不会立即连接数据库"""
        self.driver: Optional[BoltDriver] = None
        self.is_connected: bool = False
        self.stats: Dict[str, Any] = {}
    
    def connect(self, uri: str, user: str, password: str) -> bool:
        """
        连接到Neo4j数据库
        
        Args:
            uri: Neo4j数据库URI
            user: 用户名
            password: 密码
            
        Returns:
            连接是否成功
        """
        try:
            # 如果已有驱动，先关闭
            if self.driver:
                self.close()
            
            # 创建新驱动
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            
            # 验证连接
            self.driver.verify_connectivity()
            
            # 获取数据库信息
            with self.driver.session() as session:
                result = session.run("CALL db.info()")
                db_info = result.single()
                if db_info:
                    self.stats["db_name"] = db_info.get("name", "Unknown")
                    self.stats["db_version"] = db_info.get("version", "Unknown")
            
            self.is_connected = True
            logger.info(f"成功连接到Neo4j数据库: {uri}")
            return True
            
        except ServiceUnavailable as e:
            logger.error(f"无法连接到数据库: {e}")
            st.error(f"❌ 无法连接到数据库: {e}")
            return False
        except Exception as e:
            logger.error(f"连接数据库时发生错误: {e}")
            st.error(f"❌ 连接数据库时发生错误: {e}")
            return False
    
    @st.cache_resource
    def get_driver(_self, uri: str, user: str, password: str) -> Optional[BoltDriver]:
        """
        获取缓存的数据库驱动
        
        使用Streamlit的缓存机制，避免重复创建驱动
        注意：函数名前的下划线是Streamlit缓存装饰器的要求
        """
        try:
            driver = GraphDatabase.driver(uri, auth=(user, password))
            driver.verify_connectivity()
            return driver
        except Exception as e:
            logger.error(f"创建缓存驱动失败: {e}")
            return None
    
    def execute_query(self, query: str, parameters: Dict = None) -> List[Dict]:
        """
        执行Cypher查询并返回结果
        
        Args:
            query: Cypher查询语句
            parameters: 查询参数
            
        Returns:
            查询结果列表
        """
        if not self.driver or not self.is_connected:
            st.warning("⚠️ 数据库未连接，请先连接数据库")
            return []
        
        try:
            with self.driver.session() as session:
                result = session.run(query, parameters or {})
                
                # 将结果转换为字典列表
                records = []
                for record in result:
                    # 将Neo4j记录转换为Python字典
                    record_dict = {}
                    for key in record.keys():
                        value = record[key]
                        # 处理Neo4j的特殊类型
                        if hasattr(value, '__dict__'):
                            # 如果是节点
                            if hasattr(value, 'labels'):
                                record_dict[key] = {
                                    'id': element_id(value),
                                    'labels': list(value.labels),
                                    'properties': dict(value)
                                }
                            # 如果是关系
                            elif hasattr(value, 'type'):
                                record_dict[key] = {
                                    'type': value.type,
                                    'properties': dict(value)
                                }
                            else:
                                record_dict[key] = str(value)
                        else:
                            record_dict[key] = value
                    records.append(record_dict)
                
                logger.info(f"查询成功，返回 {len(records)} 条记录")
                return records
                
        except Neo4jError as e:
            logger.error(f"查询执行失败: {e}")
            st.error(f"❌ 查询执行失败: {e.code} - {e.message}")
            return []
        except Exception as e:
            logger.error(f"查询时发生未知错误: {e}")
            st.error(f"❌ 查询时发生未知错误: {e}")
            return []
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        获取数据库统计信息
        
        Returns:
            包含数据库统计信息的字典
        """
        if not self.is_connected:
            return {}
        
        try:
            stats = {}
            
            # 获取节点类型统计 - 使用直接计数
            node_query = """
            CALL db.labels() YIELD label
            WITH label
            CALL {
                WITH label
                MATCH (n) WHERE label IN labels(n)
                RETURN count(n) as count
            }
            RETURN label, count
            ORDER BY count DESC
            """
            node_result = self.execute_query(node_query)
            stats["node_types"] = node_result
            
            # 获取关系类型统计 - 使用直接计数
            rel_query = """
            CALL db.relationshipTypes() YIELD relationshipType as type
            WITH type
            CALL {
                WITH type
                MATCH ()-[r]->() WHERE type(r) = type
                RETURN count(r) as count
            }
            RETURN type, count
            ORDER BY count DESC
            """
            rel_result = self.execute_query(rel_query)
            stats["relationship_types"] = rel_result
            
            # 获取数据库基本信息
            info_query = "CALL db.info()"
            info_result = self.execute_query(info_query)
            if info_result:
                stats["database_info"] = info_result[0]
            
            # 获取总节点数和总关系数
            summary_query = """
            MATCH (n) RETURN count(n) as total_nodes;
            MATCH ()-[r]->() RETURN count(r) as total_relationships;
            """
            try:
                # 使用session.run执行多个语句
                with self.driver.session() as session:
                    total_nodes = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
                    total_rels = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
                    stats["total_nodes"] = total_nodes
                    stats["total_relationships"] = total_rels
            except:
                pass
            
            return stats
            
        except Exception as e:
            logger.warning(f"获取数据库统计信息失败: {e}")
            return {}

    
    def test_connection(self) -> Tuple[bool, str]:
        """
        测试数据库连接
        
        Returns:
            (是否成功, 消息)
        """
        if not self.driver:
            return False, "数据库驱动未初始化"
        
        try:
            with self.driver.session() as session:
                # 执行一个简单查询来测试连接
                result = session.run("RETURN 1 as test")
                if result.single()["test"] == 1:
                    return True, "✅ 数据库连接正常"
                else:
                    return False, "❌ 数据库连接测试失败"
        except Exception as e:
            return False, f"❌ 数据库连接失败: {e}"
    
    def close(self):
        """关闭数据库连接"""
        if self.driver:
            self.driver.close()
            self.driver = None
            self.is_connected = False
            logger.info("数据库连接已关闭")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口，确保连接关闭"""
        self.close()

    def get_character_basic_info(self, character_name: str) -> Dict[str, Any]:
        """
        获取角色基础信息
        
        Args:
            character_name: 角色名称
            
        Returns:
            包含角色基础信息的字典
        """
        if not self.driver or not self.is_connected:
            return {}
        
        query = """
        MATCH (c:character {name: $name})
        OPTIONAL MATCH (c)-[:has_element]->(e:element)
        OPTIONAL MATCH (c)-[:from_country]->(co:country)
        RETURN c.name as name, 
            labels(c) as labels,
            properties(c) as properties,
            e.name as element,
            co.name as country,
            c.gender as gender,
            c.weapon_type as weapon_type,
            c.birthday as birthday,
            c.img_src as img_src
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, {"name": character_name})
                record = result.single()
                
                if record:
                    # 构建返回数据
                    character_data = {
                        "name": record["name"],
                        "labels": record["labels"],
                        "properties": record["properties"],
                        "element": record["element"],
                        "country": record["country"],
                        "gender": record["gender"],
                        "weapon_type": record["weapon_type"],
                        "birthday": record["birthday"],
                        "img_src": record["img_src"]
                    }
                    return character_data
                else:
                    return {}
                    
        except Exception as e:
            logger.error(f"查询角色基础信息失败: {e}")
            return {}

    def get_character_weapons(self, character_name: str) -> List[Dict]:
        """
        获取角色适配的武器
        
        Args:
            character_name: 角色名称
            
        Returns:
            武器列表
        """
        if not self.driver or not self.is_connected:
            return []
        
        query = """
        MATCH (c:character {name: $name})-[:suits_weapon]->(w:weapon)
        RETURN w.name as name, 
            properties(w) as properties
        ORDER BY w.name
        LIMIT 20
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, {"name": character_name})
                weapons = []
                for record in result:
                    weapons.append({
                        "name": record["name"],
                        "properties": record["properties"]
                    })
                return weapons
        except Exception as e:
            logger.error(f"查询角色武器失败: {e}")
            return []

    def get_character_artifacts(self, character_name: str) -> List[Dict]:
        """
        获取角色适配的圣遗物
        
        Args:
            character_name: 角色名称
            
        Returns:
            圣遗物列表
        """
        if not self.driver or not self.is_connected:
            return []
        
        query = """
        MATCH (c:character {name: $name})-[:suits]->(a:artifact)
        RETURN a.name as name, 
            properties(a) as properties
        ORDER BY a.name
        LIMIT 10
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, {"name": character_name})
                artifacts = []
                for record in result:
                    artifacts.append({
                        "name": record["name"],
                        "properties": record["properties"]
                    })
                return artifacts
        except Exception as e:
            logger.error(f"查询角色圣遗物失败: {e}")
            return []

    def get_character_materials(self, character_name: str, limit: int = 10) -> List[Dict]:
        """
        获取角色需要的材料
        
        Args:
            character_name: 角色名称
            limit: 返回数量限制
            
        Returns:
            材料列表
        """
        if not self.driver or not self.is_connected:
            return []
        
        query = """
        MATCH (c:character {name: $name})-[r:needs_material]->(m:material)
        RETURN m.name as name, 
            properties(m) as properties,
            r.count as needed_count
        ORDER BY m.name
        LIMIT $limit
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, {"name": character_name, "limit": limit})
                materials = []
                for record in result:
                    materials.append({
                        "name": record["name"],
                        "properties": record["properties"],
                        "needed_count": record["needed_count"]
                    })
                return materials
        except Exception as e:
            logger.error(f"查询角色材料失败: {e}")
            return []

    def get_character_reactions(self, character_name: str) -> List[Dict]:
        """
        获取角色元素相关的反应
        
        Args:
            character_name: 角色名称
            
        Returns:
            反应列表
        """
        if not self.driver or not self.is_connected:
            return []
        
        query = """
        MATCH (c:character {name: $name})-[:has_element]->(e:element)
        OPTIONAL MATCH (e)-[r:trigger]-(other:element)
        OPTIONAL MATCH (e)-[:trigger]->(reaction:reaction)
        RETURN e.name as element,
            collect(DISTINCT other.name) as other_elements,
            collect(DISTINCT reaction.name) as reactions
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, {"name": character_name})
                reactions = []
                for record in result:
                    if record["element"]:
                        reactions.append({
                            "element": record["element"],
                            "other_elements": record["other_elements"] or [],
                            "reactions": record["reactions"] or []
                        })
                return reactions
        except Exception as e:
            logger.error(f"查询角色元素反应失败: {e}")
            return []

    def search_characters(self, keyword: str = "", limit: int = 20) -> List[str]:
        """
        搜索角色（用于自动补全）
        
        Args:
            keyword: 搜索关键词
            limit: 返回数量限制
            
        Returns:
            角色名称列表
        """
        if not self.driver or not self.is_connected:
            return []
        
        query = """
        MATCH (c:character)
        WHERE c.name CONTAINS $keyword
        RETURN c.name as name
        ORDER BY c.name
        LIMIT $limit
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, {"keyword": keyword, "limit": limit})
                characters = [record["name"] for record in result]
                return characters
        except Exception as e:
            logger.error(f"搜索角色失败: {e}")
            return []

    def get_weapon_basic_info(self, weapon_name: str) -> Dict[str, Any]:
        """
        获取武器基础信息
        
        Args:
            weapon_name: 武器名称
            
        Returns:
            包含武器基础信息的字典
        """
        if not self.driver or not self.is_connected:
            return {}
        
        query = """
        MATCH (w:weapon {name: $name})
        OPTIONAL MATCH (w)-[:belongs_to_type]->(wt:weapon_type)
        RETURN w.name as name,
            labels(w) as labels,
            properties(w) as properties,
            wt.name as weapon_type,
            w.rarity as rarity,
            w.max_attack as attack,
            w.sub_stat as sub_stat,
            w.ability_name as ability_name,
            w.img_src as img_src
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, {"name": weapon_name})
                record = result.single()
                
                if record:
                    weapon_data = {
                        "name": record["name"],
                        "labels": record["labels"],
                        "properties": record["properties"],
                        "weapon_type": record["weapon_type"],
                        "rarity": record["rarity"],
                        "attack": record["attack"],
                        "sub_stat": record["sub_stat"],
                        "ability_name": record["ability_name"],
                        "img_src": record["img_src"]
                    }
                    return weapon_data
                else:
                    return {}
                    
        except Exception as e:
            logger.error(f"查询武器基础信息失败: {e}")
            return {}

    def get_weapon_characters(self, weapon_name: str) -> List[Dict]:
        """
        获取适用该武器的角色
        
        Args:
            weapon_name: 武器名称
            
        Returns:
            角色列表
        """
        if not self.driver or not self.is_connected:
            return []
        
        query = """
        MATCH (w:weapon {name: $name})<-[:suits_weapon]-(c:character)
        RETURN c.name as name,
            properties(c) as properties,
            c.element as element,
            c.country as country
        ORDER BY c.name
        LIMIT 20
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, {"name": weapon_name})
                characters = []
                for record in result:
                    characters.append({
                        "name": record["name"],
                        "properties": record["properties"],
                        "element": record["element"],
                        "country": record["country"]
                    })
                return characters
        except Exception as e:
            logger.error(f"查询武器适用角色失败: {e}")
            return []

    def get_weapon_materials(self, weapon_name: str, limit: int = 10) -> List[Dict]:
        """
        获取武器突破所需材料
        
        Args:
            weapon_name: 武器名称
            limit: 返回数量限制
            
        Returns:
            材料列表
        """
        if not self.driver or not self.is_connected:
            return []
        
        query = """
        MATCH (w:weapon {name: $name})-[r:needs_material]->(m:material)
        RETURN m.name as name,
            properties(m) as properties,
            r.count as needed_count
        ORDER BY m.name
        LIMIT $limit
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, {"name": weapon_name, "limit": limit})
                materials = []
                for record in result:
                    materials.append({
                        "name": record["name"],
                        "properties": record["properties"],
                        "needed_count": record["needed_count"]
                    })
                return materials
        except Exception as e:
            logger.error(f"查询武器材料失败: {e}")
            return []

    def search_weapons(self, keyword: str = "", limit: int = 20) -> List[str]:
        """
        搜索武器（用于自动补全）
        
        Args:
            keyword: 搜索关键词
            limit: 返回数量限制
            
        Returns:
            武器名称列表
        """
        if not self.driver or not self.is_connected:
            return []
        
        query = """
        MATCH (w:weapon)
        WHERE w.name CONTAINS $keyword
        RETURN w.name as name
        ORDER BY w.name
        LIMIT $limit
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, {"keyword": keyword, "limit": limit})
                weapons = [record["name"] for record in result]
                return weapons
        except Exception as e:
            logger.error(f"搜索武器失败: {e}")
            return []

    def get_artifact_basic_info(self, artifact_name: str) -> Dict[str, Any]:
        """
        获取圣遗物基础信息
        
        Args:
            artifact_name: 圣遗物名称
            
        Returns:
            包含圣遗物基础信息的字典
        """
        if not self.driver or not self.is_connected:
            return {}
        
        query = """
        MATCH (a:artifact {name: $name})
        OPTIONAL MATCH (a)-[:belongs_to_set]->(s:artifact_set)
        RETURN a.name as name,
            labels(a) as labels,
            properties(a) as properties,
            s.name as set_name,
            a.rarity as rarity,
            a.type as type,
            a.main_stat as main_stat,
            a.img_src as img_src
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, {"name": artifact_name})
                record = result.single()
                
                if record:
                    artifact_data = {
                        "name": record["name"],
                        "labels": record["labels"],
                        "properties": record["properties"],
                        "set_name": record["set_name"],
                        "rarity": record["rarity"],
                        "type": record["type"],
                        "main_stat": record["main_stat"],
                        "img_src": record["img_src"]
                    }
                    return artifact_data
                else:
                    return {}
                    
        except Exception as e:
            logger.error(f"查询圣遗物基础信息失败: {e}")
            return {}

    def get_artifact_characters(self, artifact_name: str) -> List[Dict]:
        """
        获取适用该圣遗物的角色
        
        Args:
            artifact_name: 圣遗物名称
            
        Returns:
            角色列表
        """
        if not self.driver or not self.is_connected:
            return []
        
        query = """
        MATCH (a:artifact {name: $name})-[:suits]->(c:character)
        RETURN c.name as name,
            properties(c) as properties,
            c.element as element,
            c.weapon_type as weapon_type
        ORDER BY c.name
        LIMIT 20
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, {"name": artifact_name})
                characters = []
                for record in result:
                    characters.append({
                        "name": record["name"],
                        "properties": record["properties"],
                        "element": record["element"],
                        "weapon_type": record["weapon_type"]
                    })
                return characters
        except Exception as e:
            logger.error(f"查询圣遗物适用角色失败: {e}")
            return []

    def get_artifact_set_info(self, artifact_set_name: str) -> List[Dict]:
        """
        获取圣遗物套装信息
        
        Args:
            artifact_set_name: 圣遗物套装名称
            
        Returns:
            套装中的圣遗物列表
        """
        if not self.driver or not self.is_connected:
            return []
        
        query = """
        MATCH (as:artifact_set {name: $name})<-[:belongs_to_set]-(a:artifact)
        RETURN a.name as name,
            properties(a) as properties,
            a.type as type,
            a.rarity as rarity,
            a.main_stat as main_stat
        ORDER BY a.type
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, {"name": artifact_set_name})
                artifacts = []
                for record in result:
                    artifacts.append({
                        "name": record["name"],
                        "properties": record["properties"],
                        "type": record["type"],
                        "rarity": record["rarity"],
                        "main_stat": record["main_stat"]
                    })
                return artifacts
        except Exception as e:
            logger.error(f"查询圣遗物套装失败: {e}")
            return []

    def search_artifacts(self, keyword: str = "", limit: int = 20) -> List[str]:
        """
        搜索圣遗物（用于自动补全）
        
        Args:
            keyword: 搜索关键词
            limit: 返回数量限制
            
        Returns:
            圣遗物名称列表
        """
        if not self.driver or not self.is_connected:
            return []
        
        query = """
        MATCH (a:artifact)
        WHERE a.name CONTAINS $keyword
        RETURN a.name as name
        ORDER BY a.name
        LIMIT $limit
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, {"keyword": keyword, "limit": limit})
                artifacts = [record["name"] for record in result]
                return artifacts
        except Exception as e:
            logger.error(f"搜索圣遗物失败: {e}")
            return []


# 辅助函数：安全地获取元素ID
def element_id(element) -> str:
    """获取Neo4j元素的ID"""
    try:
        # 尝试不同的方式获取ID
        if hasattr(element, 'element_id'):
            return element.element_id
        elif hasattr(element, 'id'):
            return str(element.id)
        else:
            return str(id(element))
    except:
        return "unknown_id"


# 创建全局数据库连接实例
@st.cache_resource
def get_graph_connection() -> GenshinKnowledgeGraph:
    """
    获取缓存的数据库连接实例
    
    使用Streamlit缓存，确保整个应用只有一个连接实例
    """
    return GenshinKnowledgeGraph()