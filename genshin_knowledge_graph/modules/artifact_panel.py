"""
圣遗物查询模块 - 处理和显示圣遗物相关信息
"""
import streamlit as st
import pandas as pd
import random
from typing import Dict, Any

def display_artifact_basic_info(artifact_info: Dict[str, Any]):
    """显示圣遗物基本信息"""
    
    col_left, col_right = st.columns([1, 2])
    
    with col_left:
        if artifact_info.get("img_src"):
            st.markdown(
                f"""
                <style>
                .artifact-img {{
                    border-radius: 10px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                    width: 100%;
                    max-width: 300px;
                }}
                </style>
                <img src="{artifact_info['img_src']}" class="artifact-img" alt="{artifact_info['name']}">
                """,
                unsafe_allow_html=True
            )
        else:
            st.image("https://via.placeholder.com/300x200/3a3a3a/ffffff?text=No+Image", 
                    caption="暂无圣遗物图片", use_column_width=True)
    
    with col_right:
        st.write("#### 基本信息")
        
        # 星级显示 - 使用min_rarity和max_rarity
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # 从properties中获取min_rarity和max_rarity
            properties = artifact_info.get("properties", {})
            try:
                min_rarity = properties.get("min/max_rarity")[0]
                max_rarity = properties.get("min/max_rarity")[2]
            except:
                min_rarity = None
                max_rarity = None
            
            if min_rarity and max_rarity:
                if min_rarity == max_rarity:
                    rarity_display = f"★{min_rarity}"
                else:
                    rarity_display = f"★{min_rarity}-{max_rarity}"
                st.metric("⭐ 星级", rarity_display)
            elif min_rarity:
                st.metric("⭐ 星级", f"★{min_rarity}")
            elif max_rarity:
                st.metric("⭐ 星级", f"★{max_rarity}")
            else:
                # 回退到原来的rarity字段
                value = artifact_info.get("rarity")
                if value:
                    if isinstance(value, int):
                        rarity_stars = "★" * value
                    else:
                        rarity_stars = str(value)
                    st.metric("⭐ 星级", rarity_stars)
                else:
                    alt_value = artifact_info.get("properties", {}).get("rarity")
                    if alt_value:
                        if isinstance(alt_value, int):
                            rarity_stars = "★" * alt_value
                        else:
                            rarity_stars = str(alt_value)
                        st.metric("⭐ 星级", rarity_stars)
                    else:
                        st.metric("⭐ 星级", "未知")
        
        # 显示两件套效果和四件套效果
        properties = artifact_info.get("properties", {})
        
        two_piece_effect = properties.get("2piece_effect") or properties.get("two_piece_effect")
        four_piece_effect = properties.get("4piece_effect") or properties.get("four_piece_effect")
        
        if two_piece_effect or four_piece_effect:
            st.write("#### 🎯 套装效果")
            
            if two_piece_effect:
                st.markdown(f"**2件套效果:** {two_piece_effect}")
            
            if four_piece_effect:
                st.markdown(f"**4件套效果:** {four_piece_effect}")


def display_artifact_samples(kg, sample_size=10):
    """显示圣遗物样本按钮（随机选择）"""

    # === 1. 定义回调函数 ===
    def on_sample_click(artifact_name):
        st.session_state["artifact_input"] = artifact_name
        st.session_state.artifact_input_session_state = artifact_name
        st.session_state.switch_to_artifact = True

        if "last_artifact" in st.session_state:
            del st.session_state.last_artifact
        if "random_artifact_samples" in st.session_state:
            del st.session_state.random_artifact_samples

    if "artifact_list" in st.session_state and st.session_state.artifact_list:
        # (保持原有的随机采样逻辑)
        all_artifacts = st.session_state.artifact_list
        if "random_artifact_samples" not in st.session_state:
            available_artifacts = all_artifacts.copy()
            if "last_artifact" in st.session_state and st.session_state.last_artifact in available_artifacts:
                available_artifacts.remove(st.session_state.last_artifact)
            sample_count = min(sample_size, len(available_artifacts))
            random_samples = random.sample(available_artifacts, sample_count) if sample_count > 0 else []
            if "last_artifact" in st.session_state and st.session_state.last_artifact and len(
                    random_samples) < sample_size:
                if st.session_state.last_artifact not in random_samples:
                    random_samples.append(st.session_state.last_artifact)
            st.session_state.random_artifact_samples = random_samples

        st.write("**快速选择圣遗物:**")
        sample_artifacts = st.session_state.random_artifact_samples

        cols = st.columns(5)
        for i, artifact in enumerate(sample_artifacts):
            with cols[i % 5]:
                # === 2. 使用 on_click 回调 ===
                st.button(
                    artifact,
                    use_container_width=True,
                    key=f"sample_artifact_{i}",
                    on_click=on_sample_click,
                    args=(artifact,)
                )


def display_artifact_panel(kg):
    """显示圣遗物查询面板"""
    st.header("🛡️ 圣遗物信息查询")

    col1, col2 = st.columns([2, 1])

    with col1:
        if "artifact_list" not in st.session_state:
            with st.spinner("正在加载圣遗物列表..."):
                st.session_state.artifact_list = kg.search_artifacts()

        if "artifact_input_session_state" not in st.session_state:
            st.session_state.artifact_input_session_state = ""

        artifact_name = st.text_input(
            "输入圣遗物名称",
            value=st.session_state.artifact_input_session_state,
            placeholder="例如：追忆之注连、绝缘之旗印",
            help="输入圣遗物名称进行查询",
            key="artifact_input"
        )
        if artifact_name != st.session_state.artifact_input_session_state:
            st.session_state.artifact_input_session_state = artifact_name

    with col2:
        st.write("")
        st.write("")
        search_button = st.button("🔍 查询圣遗物", type="primary", use_container_width=True, key="artifact_search")

    # 显示快速选择圣遗物按钮
    display_artifact_samples(kg, sample_size=10)

    # === 3. 优先检查切换标志 ===
    should_query = False

    if st.session_state.get("switch_to_artifact", False):
        should_query = True
        st.session_state.switch_to_artifact = False
    elif search_button:
        should_query = True
    elif artifact_name and "last_artifact" in st.session_state:
        if st.session_state.last_artifact != artifact_name:
            should_query = True
    elif artifact_name and "last_artifact" not in st.session_state:
        should_query = True

    # 执行查询
    if should_query and artifact_name:
        with st.spinner(f"正在查询圣遗物 {artifact_name} 的信息..."):
            artifact_info = kg.get_artifact_basic_info(artifact_name)

            if artifact_info:
                st.session_state.last_artifact = artifact_name
                st.session_state.artifact_info = artifact_info
                st.session_state.artifact_characters = kg.get_artifact_characters(artifact_name)

                # 如果有套装信息，获取套装详情
                if artifact_info.get("set_name"):
                    st.session_state.artifact_set = kg.get_artifact_set_info(artifact_info["set_name"])
                else:
                    st.session_state.artifact_set = []
                st.session_state.last_query_successful = True
            else:
                st.error(f"未找到圣遗物: {artifact_name}")
                for key in ["artifact_info", "artifact_characters", "artifact_set", "last_query_successful"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.session_state.last_artifact = artifact_name
                st.session_state.last_query_successful = False

    # 显示圣遗物信息
    if "artifact_info" in st.session_state and st.session_state.artifact_info:
        artifact_info = st.session_state.artifact_info

        st.subheader(f"📋 {artifact_info['name']} 的圣遗物信息")

        # 显示基本信息
        display_artifact_basic_info(artifact_info)

        # 显示其他属性
        if artifact_info.get("properties"):
            st.divider()
            st.write("#### 📊 详细属性")

            properties = artifact_info["properties"]

            # 排除已经显示的基本属性
            basic_props = ["name", "min/max_rarity", "img_src"]
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
        if "artifact_characters" in st.session_state and st.session_state.artifact_characters:
            st.divider()
            st.write("#### 👥 适用角色")

            characters = st.session_state.artifact_characters
            if characters:
                char_data = []
                for char in characters:
                    char_info = {
                        "角色名称": char["name"],
                        "元素": char["element"] or char["properties"].get("element", "未知"),
                        "武器类型": char["weapon_type"] or char["properties"].get("weapon_type", "未知")
                    }
                    char_data.append(char_info)

                char_df = pd.DataFrame(char_data)
                st.dataframe(char_df, use_container_width=True, hide_index=True)
            else:
                st.info("暂无适用角色信息")

        # 显示套装信息
        if "artifact_set" in st.session_state and st.session_state.artifact_set:
            st.divider()
            st.write(f"#### 🔄 {artifact_info.get('set_name', '套装')} 套装")

            artifact_set = st.session_state.artifact_set
            if artifact_set:
                set_data = []
                for artifact in artifact_set:
                    # 获取每个圣遗物的星级范围
                    artifact_properties = artifact.get("properties", {})
                    min_r = artifact_properties.get("min_rarity")
                    max_r = artifact_properties.get("max_rarity")

                    if min_r and max_r:
                        if min_r == max_r:
                            rarity_display = f"★{min_r}"
                        else:
                            rarity_display = f"★{min_r}-{max_r}"
                    elif min_r:
                        rarity_display = f"★{min_r}"
                    elif max_r:
                        rarity_display = f"★{max_r}"
                    else:
                        # 回退
                        rarity_display = "★" * artifact["rarity"] if isinstance(artifact.get("rarity"), int) else artifact.get("rarity", "未知")

                    artifact_info_row = {
                        "部位": artifact["type"],
                        "圣遗物名称": artifact["name"],
                        "主属性": artifact["main_stat"],
                        "星级": rarity_display
                    }
                    set_data.append(artifact_info_row)

                set_df = pd.DataFrame(set_data)
                st.dataframe(set_df, use_container_width=True, hide_index=True)

    elif "last_artifact" in st.session_state and st.session_state.get("last_query_successful", True):
        st.warning(f"未找到圣遗物 '{st.session_state.last_artifact}' 的信息")

    else:
        st.info("👆 请输入圣遗物名称并点击查询按钮，或从上方快速选择圣遗物")