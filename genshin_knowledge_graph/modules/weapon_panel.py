"""
武器查询模块 - 处理和显示武器相关信息
"""
import streamlit as st
import pandas as pd
import random
from typing import Dict, Any

def display_weapon_basic_info(weapon_info: Dict[str, Any]):
    """显示武器基本信息"""
    
    col_left, col_right = st.columns([1, 2])
    
    with col_left:
        if weapon_info.get("img_src"):
            st.markdown(
                f"""
                <style>
                .weapon-img {{
                    border-radius: 10px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                    width: 100%;
                    max-width: 300px;
                }}
                </style>
                <img src="{weapon_info['img_src']}" class="weapon-img" alt="{weapon_info['name']}">
                """,
                unsafe_allow_html=True
            )
        else:
            st.image("https://via.placeholder.com/300x200/3a3a3a/ffffff?text=No+Image", 
                    caption="暂无武器图片", use_column_width=True)
    
    with col_right:
        st.write("#### 基本信息")
        
        # 第一行：类型、星级、攻击力
        col1, col2, col3 = st.columns(3)
        
        with col1:
            value = weapon_info.get("weapon_type")
            if value:
                st.metric("🗡️ 武器类型", value)
            else:
                alt_value = weapon_info.get("properties", {}).get("type")
                if alt_value:
                    st.metric("🗡️ 武器类型", alt_value)
                else:
                    st.metric("🗡️ 武器类型", "未知")
        
        with col2:
            value = weapon_info.get("rarity")
            if value:
                if isinstance(value, int):
                    rarity_stars = "★" * value
                else:
                    rarity_stars = str(value)
                st.metric("⭐ 星级", rarity_stars)
            else:
                alt_value = weapon_info.get("properties", {}).get("rarity")
                if alt_value:
                    if isinstance(alt_value, int):
                        rarity_stars = "★" * alt_value
                    else:
                        rarity_stars = str(alt_value)
                    st.metric("⭐ 星级", rarity_stars)
                else:
                    st.metric("⭐ 星级", "未知")
        
        with col3:
            properties = weapon_info.get("properties", {})
            max_attack = properties.get("max_attack")
            if max_attack:
                st.metric("⚔️攻击力", max_attack)
            else:
                attack = weapon_info.get("attack") or properties.get("attack")
                if attack:
                    st.metric("⚔️ 攻击力", attack)
                else:
                    st.metric("⚔️ 攻击力", "未知")
        
        st.write("##### 📊 副属性")
        properties = weapon_info.get("properties", {})
        max_subproperty = properties.get("max_subproperty")
        if max_subproperty:
            st.info(f"**副属性**: {max_subproperty}")
        else:
            sub_stat = weapon_info.get("sub_stat") or properties.get("sub_stat")
            if sub_stat:
                st.info(f"**副属性**: {sub_stat}")
            else:
                st.info("**副属性**: 未知")


def display_weapon_samples(kg, sample_size=10):
    """显示武器样本按钮（随机选择）"""

    # === 1. 定义回调函数 ===
    def on_sample_click(weapon_name):
        st.session_state["weapon_input"] = weapon_name  # 强制更新输入框组件
        st.session_state.weapon_input_session_state = weapon_name
        st.session_state.switch_to_weapon = True

        if "last_weapon" in st.session_state:
            del st.session_state.last_weapon
        if "random_weapon_samples" in st.session_state:
            del st.session_state.random_weapon_samples

    if "weapon_list" in st.session_state and st.session_state.weapon_list:
        # (保持原有的随机采样逻辑不变)
        all_weapons = st.session_state.weapon_list
        if "random_weapon_samples" not in st.session_state:
            available_weapons = all_weapons.copy()
            if "last_weapon" in st.session_state and st.session_state.last_weapon in available_weapons:
                available_weapons.remove(st.session_state.last_weapon)
            sample_count = min(sample_size, len(available_weapons))
            random_samples = random.sample(available_weapons, sample_count) if sample_count > 0 else []
            if "last_weapon" in st.session_state and st.session_state.last_weapon and len(random_samples) < sample_size:
                if st.session_state.last_weapon not in random_samples:
                    random_samples.append(st.session_state.last_weapon)
            st.session_state.random_weapon_samples = random_samples

        st.write("**快速选择武器:**")
        sample_weapons = st.session_state.random_weapon_samples

        # 将样本分组显示
        cols = st.columns(5)
        for i, weapon in enumerate(sample_weapons):
            with cols[i % 5]:
                # === 2. 使用 on_click 回调 ===
                st.button(
                    weapon,
                    use_container_width=True,
                    key=f"sample_weapon_{i}",
                    on_click=on_sample_click,
                    args=(weapon,)
                )


def display_weapon_panel(kg):
    """显示武器查询面板"""
    st.header("🗡️ 武器信息查询")

    col1, col2 = st.columns([2, 1])

    with col1:
        if "weapon_list" not in st.session_state:
            with st.spinner("正在加载武器列表..."):
                st.session_state.weapon_list = kg.search_weapons()

        if "weapon_input_session_state" not in st.session_state:
            st.session_state.weapon_input_session_state = ""

        weapon_name = st.text_input(
            "输入武器名称",
            value=st.session_state.weapon_input_session_state,
            placeholder="例如：天空之刃、护摩之杖",
            help="输入武器名称进行查询",
            key="weapon_input"
        )
        # 简单的状态同步留着也没事，但主要靠回调
        if weapon_name != st.session_state.weapon_input_session_state:
            st.session_state.weapon_input_session_state = weapon_name

    with col2:
        st.write("")
        st.write("")
        search_button = st.button("🔍 查询武器", type="primary", use_container_width=True, key="weapon_search")

    # === 3. 优先检查切换标志 ===
    should_query = False

    if st.session_state.get("switch_to_weapon", False):
        should_query = True
        st.session_state.switch_to_weapon = False
    elif search_button:
        should_query = True
    elif weapon_name and "last_weapon" in st.session_state:
        if st.session_state.last_weapon != weapon_name:
            should_query = True
    elif weapon_name and "last_weapon" not in st.session_state:
        should_query = True

    # 显示快速选择武器按钮（始终显示）
    display_weapon_samples(kg, sample_size=10)

    # 执行查询
    if should_query and weapon_name:
        with st.spinner(f"正在查询武器 {weapon_name} 的信息..."):
            weapon_info = kg.get_weapon_basic_info(weapon_name)

            if weapon_info:
                st.session_state.last_weapon = weapon_name
                st.session_state.weapon_info = weapon_info
                st.session_state.weapon_characters = kg.get_weapon_characters(weapon_name)
                st.session_state.weapon_materials = kg.get_weapon_materials(weapon_name)
                st.session_state.last_query_successful = True
            else:
                st.error(f"未找到武器: {weapon_name}")
                for key in ["weapon_info", "weapon_characters", "weapon_materials", "last_query_successful"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.session_state.last_weapon = weapon_name
                st.session_state.last_query_successful = False

    # 显示武器信息
    if "weapon_info" in st.session_state and st.session_state.weapon_info:
        weapon_info = st.session_state.weapon_info

        st.subheader(f"📋 {weapon_info['name']} 的武器信息")

        # 显示基本信息
        display_weapon_basic_info(weapon_info)

        # 显示其他属性
        if weapon_info.get("properties"):
            st.divider()
            st.write("#### 📊 详细属性")

            properties = weapon_info["properties"]
            basic_props = ["name", "rarity", "type", "ability_name", "img_src"]
            display_props = {k: v for k, v in properties.items() if k not in basic_props}

            if display_props:
                prop_df = pd.DataFrame(
                    [(key, str(value)) for key, value in display_props.items()],
                    columns=["属性", "值"]
                )
                st.dataframe(prop_df, use_container_width=True, hide_index=True)
            else:
                st.info("暂无其他属性信息")

        # 显示适用角色
        if "weapon_characters" in st.session_state and st.session_state.weapon_characters:
            st.divider()
            st.write("#### 👥 适用角色")

            characters = st.session_state.weapon_characters
            if characters:
                char_data = []
                for char in characters:
                    char_info = {
                        "角色名称": char["name"],
                        "元素": char["element"] or char["properties"].get("element", "未知"),
                        "国家": char["country"] or char["properties"].get("country", "未知"),
                        "武器类型": char["properties"].get("weapon_type", "未知")
                    }
                    char_data.append(char_info)

                char_df = pd.DataFrame(char_data)
                st.dataframe(char_df, use_container_width=True, hide_index=True)
            else:
                st.info("暂无适用角色信息")

        # 显示突破材料
        if "weapon_materials" in st.session_state and st.session_state.weapon_materials:
            st.divider()
            st.write("#### 📦 突破材料")

            materials = st.session_state.weapon_materials
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

    elif "last_weapon" in st.session_state and st.session_state.get("last_query_successful", True):
        st.warning(f"未找到武器 '{st.session_state.last_weapon}' 的信息")

    else:
        st.info("👆 请输入武器名称并点击查询按钮，或从上方快速选择武器")