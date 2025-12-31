"""
角色查询模块 - 处理和显示角色相关信息
"""
import streamlit as st
import pandas as pd
import random
from typing import Dict, Any

def display_character_basic_info(character_info: Dict[str, Any]):
    """显示角色基本信息（优化版）"""
    
    # 使用两列布局：左边图片，右边基本信息
    col_left, col_right = st.columns([1, 2])
    
    with col_left:
        # 显示角色图片
        if character_info.get("img_src"):
            st.markdown(
                f"""
                <style>
                .character-img {{
                    border-radius: 10px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                    width: 100%;
                    max-width: 300px;
                }}
                </style>
                <img src="{character_info['img_src']}" class="character-img" alt="{character_info['name']}">
                """,
                unsafe_allow_html=True
            )
        else:
            st.image("https://via.placeholder.com/300x400/3a3a3a/ffffff?text=No+Image", 
                    caption="暂无角色图片", use_column_width=True)
    
    with col_right:
        # 基本信息 - 使用多列布局
        st.write("#### 基本信息")
        
        # 第一行：元素、国家、性别
        col1, col2, col3 = st.columns(3)
        
        with col1:
            value = character_info.get("element")
            if value:
                st.metric("🎨 元素", value)
            else:
                alt_value = character_info.get("properties", {}).get("element")
                if alt_value:
                    st.metric("🎨 元素", alt_value)
                else:
                    st.metric("🎨 元素", "未知")
        
        with col2:
            value = character_info.get("country")
            if value:
                st.metric("🗺️ 国家", value)
            else:
                alt_value = character_info.get("properties", {}).get("country")
                if alt_value:
                    st.metric("🗺️ 国家", alt_value)
                else:
                    st.metric("🗺️ 国家", "未知")
        
        with col3:
            value = character_info.get("gender")
            if value:
                st.metric("👤 性别", value)
            else:
                alt_value = character_info.get("properties", {}).get("gender")
                if alt_value:
                    st.metric("👤 性别", alt_value)
                else:
                    st.metric("👤 性别", "未知")
        
        # 第二行：武器类型、星级
        col4, col5, col6 = st.columns(3)
        
        with col4:
            value = character_info.get("weapon_type")
            if value:
                st.metric("⚔️ 武器类型", value)
            else:
                alt_value = character_info.get("properties", {}).get("weapon_type")
                if alt_value:
                    st.metric("⚔️ 武器类型", alt_value)
                else:
                    st.metric("⚔️ 武器类型", "未知")
        
        with col5:
            # 尝试多种方式获取星级
            rarity = None
            properties = character_info.get("properties", {})
            
            if "rarity" in properties:
                rarity = properties["rarity"]
            elif "star" in properties:
                rarity = properties["star"]
            elif "rarity" in character_info:
                rarity = character_info["rarity"]
            elif "star" in character_info:
                rarity = character_info["star"]
            
            if rarity:
                if isinstance(rarity, int):
                    rarity_stars = "★" * rarity
                else:
                    rarity_stars = str(rarity)
                st.metric("⭐ 星级", rarity_stars)
            else:
                st.metric("⭐ 星级", "未知")


def display_character_samples(kg, sample_size=10):
    """显示角色样本按钮（随机选择）"""

    # === 1. 定义回调函数 ===
    def on_sample_click(char_name):
        """点击样本按钮时的回调"""
        # 在回调中修改 input 的 key 是安全的，因为它发生在页面重绘之前
        st.session_state["character_input"] = char_name
        st.session_state.character_input_session_state = char_name
        st.session_state.switch_to_character = True

        # 清理旧状态
        if "last_character" in st.session_state:
            del st.session_state.last_character
        if "random_character_samples" in st.session_state:
            del st.session_state.random_character_samples

    if "character_list" in st.session_state and st.session_state.character_list:
        # 获取随机样本 (保持原有逻辑不变)
        all_characters = st.session_state.character_list

        if "random_character_samples" not in st.session_state:
            available_chars = all_characters.copy()
            if "last_character" in st.session_state and st.session_state.last_character in available_chars:
                available_chars.remove(st.session_state.last_character)

            sample_count = min(sample_size, len(available_chars))
            random_samples = random.sample(available_chars, sample_count) if sample_count > 0 else []

            if "last_character" in st.session_state and st.session_state.last_character and len(
                    random_samples) < sample_size:
                if st.session_state.last_character not in random_samples:
                    random_samples.append(st.session_state.last_character)

            st.session_state.random_character_samples = random_samples

        st.write("**快速选择角色:**")
        sample_chars = st.session_state.random_character_samples

        # 将样本分组显示
        cols = st.columns(5)
        for i, char in enumerate(sample_chars):
            with cols[i % 5]:
                # === 2. 修改按钮逻辑 ===
                # 使用 on_click 参数，而不是在 if st.button 块内部处理
                st.button(
                    char,
                    use_container_width=True,
                    key=f"sample_char_{i}",
                    on_click=on_sample_click,  # 绑定回调
                    args=(char,)  # 传递参数
                )

def display_character_panel(kg):
    """显示角色查询面板"""
    st.header("🔍 角色信息查询")
    
    # 角色搜索部分
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # 获取所有角色列表用于自动补全
        if "character_list" not in st.session_state:
            with st.spinner("正在加载角色列表..."):
                st.session_state.character_list = kg.search_characters()
        
        # 初始化character_input_session_state为空字符串
        if "character_input_session_state" not in st.session_state:
            st.session_state.character_input_session_state = ""

        # 角色输入框
        character_name = st.text_input(
            "输入角色名称",
            value=st.session_state.character_input_session_state,
            placeholder="例如：七七、钟离、雷电将军",
            help="输入角色名称进行查询",
            key="character_input"
        )
        
        # 更新session_state中的值
        if character_name != st.session_state.character_input_session_state:
            st.session_state.character_input_session_state = character_name
    
    with col2:
        st.write("")
        st.write("")
        search_button = st.button("🔍 查询角色", type="primary", use_container_width=True)

    # 判断是否需要查询
    should_query = False

    # [关键修复] 优先检查是否是从快速选择按钮切换过来的
    if st.session_state.get("switch_to_character", False):
        should_query = True
        # 消费掉这个标志，防止无限循环（虽然通常rerun会重置，但保险起见）
        st.session_state.switch_to_character = False

    elif search_button:
        should_query = True
    elif character_name and "last_character" in st.session_state:
        if st.session_state.last_character != character_name:
            should_query = True
    elif character_name and "last_character" not in st.session_state:
        should_query = True
    
    # 执行查询
    if should_query and character_name:
        with st.spinner(f"正在查询角色 {character_name} 的信息..."):
            character_info = kg.get_character_basic_info(character_name)
            
            if character_info:
                st.session_state.last_character = character_name
                st.session_state.character_info = character_info
                st.session_state.character_weapons = kg.get_character_weapons(character_name)
                st.session_state.character_artifacts = kg.get_character_artifacts(character_name)
                st.session_state.character_materials = kg.get_character_materials(character_name)
                st.session_state.character_reactions = kg.get_character_reactions(character_name)
                st.session_state.last_query_successful = True
            else:
                st.error(f"未找到角色: {character_name}")
                # 清空缓存
                for key in ["character_info", "character_weapons", "character_artifacts", 
                          "character_materials", "character_reactions", "last_query_successful"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.session_state.last_character = character_name
                st.session_state.last_query_successful = False
    
    # 显示快速选择角色按钮（始终显示）
    display_character_samples(kg, sample_size=10)
    
    # 如果有角色信息，则显示
    if "character_info" in st.session_state and st.session_state.character_info:
        character_info = st.session_state.character_info
        
        # 创建角色信息卡片
        st.subheader(f"📋 {character_info['name']} 的角色信息")
        
        # 显示基本信息（包括图片）
        display_character_basic_info(character_info)
        
        # 显示其他属性
        if character_info.get("properties"):
            st.divider()
            st.write("#### 📊 详细属性")
            
            properties = character_info["properties"]
            basic_props = ["name", "rarity", "star", "gender", "weapon_type", "img_src"]
            display_props = {k: v for k, v in properties.items() if k not in basic_props}
            
            if display_props:
                prop_df = pd.DataFrame(
                    [(key, str(value)) for key, value in display_props.items()],
                    columns=["属性", "值"]
                )
                st.dataframe(prop_df, use_container_width=True, hide_index=True)
            else:
                st.info("暂无其他属性信息")
        
        # 显示适配武器
        if "character_weapons" in st.session_state and st.session_state.character_weapons:
            st.divider()
            st.write("#### ⚔️ 适配武器")
            
            weapons = st.session_state.character_weapons
            if weapons:
                weapon_data = []
                for weapon in weapons:
                    weapon_info = {
                        "武器名称": weapon["name"],
                        "类型": weapon["properties"].get("type", "未知"),
                        "攻击力": weapon["properties"].get("max_attack", "未知"),
                        "星级": "★" * weapon["properties"].get("rarity", 0) if isinstance(weapon["properties"].get("rarity", 0), int) else weapon["properties"].get("rarity", "未知")
                    }
                    weapon_data.append(weapon_info)
                
                weapon_df = pd.DataFrame(weapon_data)
                st.dataframe(weapon_df, use_container_width=True, hide_index=True)
            else:
                st.info("暂无适配武器信息")
        
        # 显示适配圣遗物
        if "character_artifacts" in st.session_state and st.session_state.character_artifacts:
            st.divider()
            st.write("#### 🛡️ 适配圣遗物")
            
            artifacts = st.session_state.character_artifacts
            if artifacts:
                for artifact in artifacts:
                    with st.expander(f"{artifact['name']}", expanded=False):
                        st.write(f"**2件套效果:** {artifact['properties'].get('2piece_effect', '无')}")
                        st.write(f"**4件套效果:** {artifact['properties'].get('4piece_effect', '无')}")
            else:
                st.info("暂无适配圣遗物信息")
        
        # 显示所需材料
        if "character_materials" in st.session_state and st.session_state.character_materials:
            st.divider()
            st.write("#### 📦 突破材料")
            
            materials = st.session_state.character_materials
            if materials:
                material_data = []
                for material in materials:
                    material_info = {
                        "材料名称": material["name"],
                        "类型": material["properties"].get("type", "未知"),
                        "来源": material["properties"].get("source", "未知"),
                    }
                    material_data.append(material_info)
                
                material_df = pd.DataFrame(material_data)
                st.dataframe(material_df, use_container_width=True, hide_index=True)
            else:
                st.info("暂无材料需求信息")
        
        # 显示元素反应
        if "character_reactions" in st.session_state and st.session_state.character_reactions:
            st.divider()
            st.write("#### ⚡ 元素反应")
            
            reactions = st.session_state.character_reactions
            for reaction_info in reactions:
                element = reaction_info["element"]
                other_elements = reaction_info["other_elements"]
                reactions_list = reaction_info["reactions"]
                
                if reactions_list:
                    st.write(f"**可触发的反应:**")
                    for reaction in reactions_list:
                        st.write(f"- {reaction}")
        
        # 显示标签信息
        if character_info.get("labels"):
            st.divider()
            st.write("#### 🏷️ 节点标签")
            tags = " · ".join([f"`{label}`" for label in character_info["labels"]])
            st.markdown(tags)
    
    elif "last_character" in st.session_state and st.session_state.get("last_query_successful", True):
        st.warning(f"未找到角色 '{st.session_state.last_character}' 的信息")
    
    else:
        # 初始状态，显示提示信息
        st.info("👆 请输入角色名称并点击查询按钮，或从上方快速选择角色")