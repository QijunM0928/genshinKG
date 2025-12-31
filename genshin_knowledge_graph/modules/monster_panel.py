"""
怪物查询模块 - 处理和显示怪物相关信息
"""
import streamlit as st
import pandas as pd
import random
from typing import Dict, Any, List


def display_monster_basic_info(monster_info: Dict[str, Any]):
    """显示怪物基本信息（修复深色模式显示问题）"""

    # 使用两列布局：左边图片，右边基本信息
    col_left, col_right = st.columns([1, 2])

    with col_left:
        # 显示怪物图片
        if monster_info.get("img_src"):
            st.markdown(
                f"""
                <style>
                .monster-img {{
                    border-radius: 10px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                    width: 100%;
                    max-width: 300px;
                }}
                </style>
                <img src="{monster_info['img_src']}" class="monster-img" alt="{monster_info['name']}">
                """,
                unsafe_allow_html=True
            )
        else:
            st.image("https://via.placeholder.com/300x400/3a3a3a/cccccc?text=No+Image",
                     caption="暂无怪物图片", use_column_width=True)

    with col_right:
        # 基本信息 - 使用多列布局
        st.write("#### 基本信息")

        # 定义深色模式的卡片样式
        # background-color: #262730 (深灰色背景)
        # border: 1px solid #464b5f (边框增加层次感)
        # label color: #b0b0b0 (浅灰色标签)
        # value color: #ffffff (纯白数值)
        card_style = """
        padding: 10px; 
        border-radius: 5px; 
        background-color: #262730; 
        border: 1px solid #3d3d3d;
        margin-bottom: 10px;
        """

        label_style = "font-size: 14px; color: #b0b0b0; margin-bottom: 5px;"
        value_style = "font-size: 16px; font-weight: bold; color: #ffffff; word-wrap: break-word;"

        # 第一行：元素、类型
        col1, col2 = st.columns(2)

        with col1:
            value = monster_info.get("element") or monster_info.get("properties", {}).get("element", "未知")
            st.markdown(f"""
            <div style="{card_style}">
                <div style="{label_style}">🎨 元素</div>
                <div style="{value_style}">{value}</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            value = monster_info.get("type") or monster_info.get("properties", {}).get("type", "未知")
            st.markdown(f"""
            <div style="{card_style}">
                <div style="{label_style}">🔍 类型</div>
                <div style="{value_style}">{value}</div>
            </div>
            """, unsafe_allow_html=True)

        # 第二行：地区、刷新时间
        col3, col4 = st.columns(2)

        with col3:
            value = monster_info.get("region") or monster_info.get("properties", {}).get("region", "未知")
            st.markdown(f"""
            <div style="{card_style}">
                <div style="{label_style}">🗺️ 地区</div>
                <div style="{value_style}">{value}</div>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            value = monster_info.get("refresh_time") or monster_info.get("properties", {}).get("refresh_time", "未知")
            st.markdown(f"""
            <div style="{card_style}">
                <div style="{label_style}">⏰ 刷新时间</div>
                <div style="{value_style}">{value}</div>
            </div>
            """, unsafe_allow_html=True)

def get_monster_basic_info(kg, monster_name: str) -> Dict[str, Any]:
    """
    获取怪物基础信息
    
    Args:
        kg: 知识图谱连接器
        monster_name: 怪物名称
        
    Returns:
        包含怪物基础信息的字典
    """
    query = """
    MATCH (m:monster {name: $name})
    RETURN m.name as name,
        labels(m) as labels,
        properties(m) as properties,
        m.element as element,
        m.type as type,
        m.region as region,
        m.drop as drop,
        m.refresh_time as refresh_time,
        m.strategy as strategy,
        m.img_src as img_src
    """
    
    try:
        result = kg.execute_query(query, {"name": monster_name})
        if result:
            record = result[0]
            monster_data = {
                "name": record.get("name"),
                "labels": record.get("labels", []),
                "properties": record.get("properties", {}),
                "element": record.get("element"),
                "type": record.get("type"),
                "region": record.get("region"),
                "drop": record.get("drop"),
                "refresh_time": record.get("refresh_time"),
                "strategy": record.get("strategy"),
                "img_src": record.get("img_src")
            }
            return monster_data
        else:
            return {}
    except Exception as e:
        st.error(f"查询怪物信息失败: {e}")
        return {}

def get_monster_restrained_by(kg, monster_name: str) -> List[Dict]:
    """
    获取克制该怪物的角色
    
    Args:
        kg: 知识图谱连接器
        monster_name: 怪物名称
        
    Returns:
        角色列表
    """
    query = """
    MATCH (c:character)-[r:restrains]->(m:monster {name: $name})
    RETURN c.name as name,
        properties(c) as properties,
        c.element as element,
        c.country as country,
        c.weapon_type as weapon_type
    ORDER BY c.name
    LIMIT 20
    """
    
    try:
        result = kg.execute_query(query, {"name": monster_name})
        characters = []
        for record in result:
            characters.append({
                "name": record.get("name"),
                "properties": record.get("properties", {}),
                "element": record.get("element"),
                "country": record.get("country"),
                "weapon_type": record.get("weapon_type")
            })
        return characters
    except Exception as e:
        st.error(f"查询克制角色失败: {e}")
        return []

def get_monster_drops_materials(kg, monster_name: str, limit: int = 10) -> List[Dict]:
    """
    获取怪物掉落的材料
    
    Args:
        kg: 知识图谱连接器
        monster_name: 怪物名称
        limit: 返回数量限制
        
    Returns:
        材料列表
    """
    query = """
    MATCH (m:monster {name: $name})-[r:drops_material]->(mat:material)
    RETURN mat.name as name,
        properties(mat) as properties,
        mat.type as type,
        mat.usage as usage
    ORDER BY mat.name
    LIMIT $limit
    """
    
    try:
        result = kg.execute_query(query, {"name": monster_name, "limit": limit})
        materials = []
        for record in result:
            materials.append({
                "name": record.get("name"),
                "properties": record.get("properties", {}),
                "type": record.get("type"),
                "usage": record.get("usage")
            })
        return materials
    except Exception as e:
        st.error(f"查询怪物掉落材料失败: {e}")
        return []

def search_monsters(kg, keyword: str = "", limit: int = 20) -> List[str]:
    """
    搜索怪物（用于自动补全）
    
    Args:
        kg: 知识图谱连接器
        keyword: 搜索关键词
        limit: 返回数量限制
        
    Returns:
        怪物名称列表
    """
    query = """
    MATCH (m:monster)
    WHERE m.name CONTAINS $keyword
    RETURN m.name as name
    ORDER BY m.name
    LIMIT $limit
    """
    
    try:
        result = kg.execute_query(query, {"keyword": keyword, "limit": limit})
        monsters = [record.get("name") for record in result if record.get("name")]
        return monsters
    except Exception as e:
        st.error(f"搜索怪物失败: {e}")
        return []


def display_monster_samples(kg, sample_size=10):
    """显示怪物样本按钮（随机选择）"""

    # === 1. 定义回调函数 ===
    def on_sample_click(monster_name):
        st.session_state["monster_input"] = monster_name
        st.session_state.monster_input_session_state = monster_name
        st.session_state.switch_to_monster = True

        if "last_monster" in st.session_state:
            del st.session_state.last_monster
        if "random_monster_samples" in st.session_state:
            del st.session_state.random_monster_samples

    if "monster_list" in st.session_state and st.session_state.monster_list:
        # (保持原有的随机采样逻辑)
        all_monsters = st.session_state.monster_list
        if "random_monster_samples" not in st.session_state:
            available_monsters = all_monsters.copy()
            if "last_monster" in st.session_state and st.session_state.last_monster in available_monsters:
                available_monsters.remove(st.session_state.last_monster)
            sample_count = min(sample_size, len(available_monsters))
            random_samples = random.sample(available_monsters, sample_count) if sample_count > 0 else []
            if "last_monster" in st.session_state and st.session_state.last_monster and len(
                    random_samples) < sample_size:
                if st.session_state.last_monster not in random_samples:
                    random_samples.append(st.session_state.last_monster)
            st.session_state.random_monster_samples = random_samples

        st.write("**快速选择怪物:**")
        sample_monsters = st.session_state.random_monster_samples

        cols = st.columns(5)
        for i, monster in enumerate(sample_monsters):
            with cols[i % 5]:
                # === 2. 使用 on_click 回调 ===
                st.button(
                    monster,
                    use_container_width=True,
                    key=f"sample_monster_{i}",
                    on_click=on_sample_click,
                    args=(monster,)
                )


def display_monster_panel(kg):
    """显示怪物查询面板"""
    st.header("🐉 怪物信息查询")

    col1, col2 = st.columns([2, 1])

    with col1:
        if "monster_list" not in st.session_state:
            with st.spinner("正在加载怪物列表..."):
                st.session_state.monster_list = search_monsters(kg, "", 100)

        if "monster_input_session_state" not in st.session_state:
            st.session_state.monster_input_session_state = ""

        monster_name = st.text_input(
            "输入怪物名称",
            value=st.session_state.monster_input_session_state,
            placeholder="例如：丘丘人、遗迹守卫",
            help="输入怪物名称进行查询",
            key="monster_input"
        )
        if monster_name != st.session_state.monster_input_session_state:
            st.session_state.monster_input_session_state = monster_name

    with col2:
        st.write("")
        st.write("")
        search_button = st.button("🔍 查询怪物", type="primary", use_container_width=True)

    # === 3. 优先检查切换标志 ===
    should_query = False

    if st.session_state.get("switch_to_monster", False):
        should_query = True
        st.session_state.switch_to_monster = False
    elif search_button:
        should_query = True
    elif monster_name and "last_monster" in st.session_state:
        if st.session_state.last_monster != monster_name:
            should_query = True
    elif monster_name and "last_monster" not in st.session_state:
        should_query = True
    
    # 执行查询
    if should_query and monster_name:
        with st.spinner(f"正在查询怪物 {monster_name} 的信息..."):
            monster_info = get_monster_basic_info(kg, monster_name)
            
            if monster_info:
                st.session_state.last_monster = monster_name
                st.session_state.monster_info = monster_info
                st.session_state.monster_restrained_by = get_monster_restrained_by(kg, monster_name)
                st.session_state.monster_drops_materials = get_monster_drops_materials(kg, monster_name)
                st.session_state.last_monster_query_successful = True
            else:
                st.error(f"未找到怪物: {monster_name}")
                # 清空缓存
                for key in ["monster_info", "monster_restrained_by", "monster_drops_materials", "last_monster_query_successful"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.session_state.last_monster = monster_name
                st.session_state.last_monster_query_successful = False
    
    # 显示快速选择怪物按钮（始终显示）
    display_monster_samples(kg, sample_size=10)
    
    # 如果有怪物信息，则显示
    if "monster_info" in st.session_state and st.session_state.monster_info:
        monster_info = st.session_state.monster_info
        
        # 创建怪物信息卡片
        st.subheader(f"📋 {monster_info['name']} 的怪物信息")
        
        # 显示基本信息（包括图片）
        display_monster_basic_info(monster_info)
        
        # 显示其他属性
        if monster_info.get("properties"):
            st.divider()
            st.write("#### 📊 详细属性")
            
            properties = monster_info["properties"]
            basic_props = ["name", "img_src", "element", "type", "region", "drop", "refresh_time", "strategy"]
            display_props = {k: v for k, v in properties.items() if k not in basic_props}
            
            if display_props:
                prop_df = pd.DataFrame(
                    [(key, str(value)) for key, value in display_props.items()],
                    columns=["属性", "值"]
                )
                st.dataframe(prop_df, use_container_width=True, hide_index=True)
            else:
                st.info("暂无其他属性信息")
        
        # 显示克制怪物的角色
        if "monster_restrained_by" in st.session_state and st.session_state.monster_restrained_by:
            st.divider()
            st.write("#### ⚔️ 克制该怪物的角色")
            
            characters = st.session_state.monster_restrained_by
            if characters:
                character_data = []
                for char in characters:
                    character_info = {
                        "角色名称": char["name"],
                        "元素": char.get("element", "未知"),
                        "国家": char.get("country", "未知"),
                        "武器类型": char.get("weapon_type", "未知")
                    }
                    character_data.append(character_info)
                
                character_df = pd.DataFrame(character_data)
                st.dataframe(character_df, use_container_width=True, hide_index=True)
                
                # 添加角色点击跳转功能
                st.write("**点击角色名称查看更多信息:**")
                cols = st.columns(5)
                for i, char in enumerate(characters[:5]):  # 只显示前5个
                    with cols[i % 5]:
                        if st.button(char["name"], use_container_width=True, key=f"monster_char_{i}"):
                            # 设置角色名称并触发查询，切换到角色面板
                            st.session_state.character_input_session_state = char["name"]
                            st.session_state.switch_to_character = True
                            st.rerun()
            else:
                st.info("暂无克制该怪物的角色信息")
        
        # 显示掉落材料
        if "monster_drops_materials" in st.session_state and st.session_state.monster_drops_materials:
            st.divider()
            st.write("#### 📦 掉落材料")
            
            materials = st.session_state.monster_drops_materials
            if materials:
                material_data = []
                for material in materials:
                    material_info = {
                        "材料名称": material["name"],
                        "类型": material.get("type", "未知"),
                        "用途": material.get("usage", "未知")
                    }
                    material_data.append(material_info)
                
                material_df = pd.DataFrame(material_data)
                st.dataframe(material_df, use_container_width=True, hide_index=True)
            else:
                st.info("暂无掉落材料信息")
        
        # 显示战斗策略
        if monster_info.get("strategy"):
            st.divider()
            st.write("#### 🛡️ 战斗策略")
            strategy_text = monster_info["strategy"]
            # 如果策略是列表，转换为字符串
            if isinstance(strategy_text, list):
                for item in strategy_text:
                    st.write(f"- {item}")
            else:
                st.write(strategy_text)
        
        # 显示标签信息
        if monster_info.get("labels"):
            st.divider()
            st.write("#### 🏷️ 节点标签")
            tags = " · ".join([f"`{label}`" for label in monster_info["labels"]])
            st.markdown(tags)
    
    elif "last_monster" in st.session_state and st.session_state.get("last_monster_query_successful", True):
        st.warning(f"未找到怪物 '{st.session_state.last_monster}' 的信息")
    
    else:
        # 初始状态，显示提示信息
        st.info("👆 请输入怪物名称并点击查询按钮，或从上方快速选择怪物")