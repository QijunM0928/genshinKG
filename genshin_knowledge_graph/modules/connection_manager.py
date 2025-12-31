"""
连接管理模块 - 处理数据库连接相关功能
"""
import streamlit as st
from openai import OpenAI

def setup_sidebar(kg) -> bool:
    """
    设置侧边栏并处理数据库连接
    
    Args:
        kg: 知识图谱连接器实例
        
    Returns:
        数据库是否已成功连接
    """
    with st.sidebar:
        st.title("🔧 控制面板")
        
        # 数据库连接部分
        st.subheader("数据库连接")
        
        # 从secrets读取配置
        try:
            neo4j_secrets = st.secrets["neo4j"]
            uri = neo4j_secrets["uri"]
            user = neo4j_secrets["user"]
            password = neo4j_secrets["password"]
            
            with st.expander("数据库配置", expanded=False):
                # 显示连接信息（隐藏密码）
                masked_password = password[:3] + "*" * (len(password) - 3)
                st.info(f"**URI:** `{uri}`\n\n**用户:** `{user}`\n\n**密码:** `{masked_password}`")
            
        except KeyError as e:
            st.error(f"❌ 缺少配置: {e}")
            st.info("请在 `.streamlit/secrets.toml` 文件中配置数据库连接信息")
            return False
        
        # 连接按钮
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔗 连接数据库", type="primary", use_container_width=True):
                with st.spinner("正在连接数据库..."):
                    if kg.connect(uri, user, password):
                        st.session_state.db_initialized = True
                        st.session_state.connection_status = "已连接"
                        st.success("✅ 数据库连接成功!")
                        st.rerun()
                    else:
                        st.session_state.db_initialized = False
                        st.session_state.connection_status = "连接失败"
        
        with col2:
            if st.button("🔌 断开连接", use_container_width=True, 
                        disabled=not kg.is_connected):
                kg.close()
                st.session_state.db_initialized = False
                st.session_state.connection_status = "未连接"
                st.info("数据库连接已断开")
                st.rerun()
        
        # 显示连接状态
        status_color = {
            "未连接": "🔴",
            "已连接": "🟢",
            "连接失败": "🟠"
        }.get(st.session_state.connection_status, "⚪")
        
        st.markdown(f"""
            <div style="border:1px solid #ddd; border-radius:5px; padding:10px; background-color:#f9f9f9;">
                <div style="font-size:0.9em; color:#666;">连接状态</div>
                <div style="font-size:1.2em; font-weight:bold; margin-top:5px;">
                    {status_color} {st.session_state.connection_status}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        if kg.is_connected:
            # 数据库信息
            st.divider()
            st.subheader("数据库信息")
            
            if st.session_state.get('db_info'):
                db_info = st.session_state.db_info
                st.text(f"名称: {db_info.get('db_name', 'Unknown')}")
                st.text(f"版本: {db_info.get('db_version', 'Unknown')}")
            
            # 测试连接按钮
            if st.button("🧪 测试连接", use_container_width=True):
                success, message = kg.test_connection()
                if success:
                    st.success(message)
                else:
                    st.error(message)
            
            # 显示统计信息按钮
            if st.button("📊 显示统计信息", use_container_width=True):
                with st.spinner("正在获取数据库统计信息..."):
                    # 获取统计信息
                    if not hasattr(st.session_state, 'database_stats'):
                        st.session_state.database_stats = get_database_statistics(kg)
                st.session_state.show_stats = not st.session_state.show_stats
                st.rerun()
        
        # LLM连接状态部分
        st.divider()
        st.subheader("🤖 LLM连接状态")

        # 初始化LLM连接状态
        if 'llm_status' not in st.session_state:
            st.session_state.llm_status = "未配置"

        # 显示LLM配置状态
        try:
            # 从Streamlit secrets获取LLM配置
            # 首先尝试从openai部分获取配置
            openai_secrets = st.secrets.get("openai", {})
            
            # 从openai部分或直接获取配置
            openai_api_key = openai_secrets.get("api_key", st.secrets.get("openai_api_key", ""))
            openai_api_base = openai_secrets.get("api_base", st.secrets.get("openai_api_base", "https://api.openai.com/v1"))
            model_id = openai_secrets.get("model_id", st.secrets.get("openai_model_id", "gpt-3.5-turbo"))
            
            if openai_api_key:
                # 显示配置摘要（隐藏密钥）- 改为可折叠
                masked_key = openai_api_key[:6] + "*" * (len(openai_api_key) - 6)
                with st.expander("📁 查看LLM配置", expanded=False):
                    st.info(f"""
                    **API端点:** `{openai_api_base}`\n
                    **模型:** `{model_id}`\n
                    **API密钥:** `{masked_key}`
                    """)
                
                # 只有在状态为"未配置"时才更新为"已配置"
                # 这样可以保留测试连接成功后设置的"已连接"状态
                if st.session_state.llm_status == "未配置":
                    st.session_state.llm_status = "已配置"
                
                # 将配置保存到会话状态，以便在其他地方使用
                st.session_state.llm_config = {
                    "api_key": openai_api_key,
                    "api_base": openai_api_base,
                    "model_id": model_id
                }
            else:
                st.warning("未配置OpenAI API密钥")
                st.session_state.llm_status = "未配置"
                
        except Exception as e:
            st.error(f"LLM配置读取失败: {e}")
            st.session_state.llm_status = "配置错误"
        
        # 显示LLM连接状态
        llm_status_colors = {
            "未配置": "🔴",
            "已配置": "🟡",
            "已连接": "🟢",
            "配置错误": "🔴",
            "连接失败": "🔴"
        }
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            status_icon = llm_status_colors.get(st.session_state.llm_status, "⚪")
            # 使用 st.markdown 替代 st.metric，避免文本截断
            st.markdown(f"""
            <div style="border:1px solid #ddd; border-radius:5px; padding:10px; background-color:#f9f9f9;">
                <div style="font-size:0.9em; color:#666;">LLM状态</div>
                <div style="font-size:1.2em; font-weight:bold; margin-top:5px;">
                    {status_icon} {st.session_state.llm_status}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # 测试LLM连接按钮
        with col2:
            if st.button("测试LLM连接", use_container_width=True,
                        disabled=st.session_state.llm_status == "未配置"):
                test_llm_connection()
        
        # 如果有配置但状态不是已连接，显示测试提示
        if st.session_state.llm_status == "已配置":
            st.caption("点击'测试LLM连接'按钮验证配置")
        
        # LLM配置说明
        with st.expander("📋 LLM配置说明"):
            st.markdown("""
            **在 `.streamlit/secrets.toml` 中添加以下配置：**
            
            方式一：使用 `[openai]` 部分（推荐）
            ```toml
            [openai]
            api_key = "你的OpenAI API密钥"
            api_base = "https://api.openai.com/v1"  # 可选，默认为OpenAI官方API
            model_id = "gpt-3.5-turbo"  # 可选，默认使用gpt-3.5-turbo
            ```
            
            方式二：直接配置（传统方式）
            ```toml
            openai_api_key = "你的OpenAI API密钥"
            openai_api_base = "https://api.openai.com/v1"  # 可选
            openai_model_id = "gpt-3.5-turbo"  # 可选
            ```
            
            **支持的模型：**
            - OpenAI官方模型: gpt-3.5-turbo, gpt-4, gpt-4-turbo等
            - 其他兼容OpenAI API的模型
            """)
        
        st.divider()
        st.caption("当前版本: 0.1.0")
        
        return kg.is_connected

def get_database_statistics(kg):
    """
    获取数据库统计信息，基于demo.ipynb中的查询
    返回包含统计信息的字典
    """
    stats = {
        "node_types": [],
        "relationship_types": [],
        "relationship_patterns": [],
        "node_properties": {},
        "relationship_properties": {}
    }
    
    try:
        # 查询1: 获取节点类型及数量
        node_query = """
        MATCH (n)
        UNWIND labels(n) AS label
        RETURN label AS node_label, count(*) AS count
        ORDER BY count DESC
        """
        node_result = kg.execute_query(node_query)
        stats["node_types"] = [f"{record['node_label']}: {record['count']}个" for record in node_result]
        
        # 查询2: 获取关系类型及数量
        rel_query = """
        MATCH (a)-[r]->(b)
        WHERE NOT ('character' IN labels(a) AND 'character' IN labels(b))
        RETURN type(r) as relation_label, count(r) as count
        ORDER BY count DESC
        """
        rel_result = kg.execute_query(rel_query)
        stats["relationship_types"] = [f"{record['relation_label']}: {record['count']}条" for record in rel_result]
        
        # 查询3: 获取关系模式
        pattern_query = """
        MATCH (a)-[r]->(b)
        WHERE NOT ('character' IN labels(a) AND 'character' IN labels(b))
        RETURN DISTINCT 
            [label in labels(a) | label] as source_labels, 
            type(r) as relationship_type, 
            [label in labels(b) | label] as target_labels
        ORDER BY relationship_type
        """
        pattern_result = kg.execute_query(pattern_query)
        
        # 添加character到character的关系模式
        stats["relationship_patterns"].append("character --[关系类型]--> character")
        for record in pattern_result:
            source = ', '.join(record['source_labels']) if record['source_labels'] else '未知'
            target = ', '.join(record['target_labels']) if record['target_labels'] else '未知'
            stats["relationship_patterns"].append(f"{source} --[{record['relationship_type']}]--> {target}")
        
        # 查询4: 获取每类节点的属性
        node_props_query = """
        MATCH (n)
        UNWIND labels(n) AS label
        WITH label, n
        UNWIND keys(n) AS prop
        RETURN label, collect(DISTINCT prop) as properties
        ORDER BY label
        """
        node_props_result = kg.execute_query(node_props_query)
        for record in node_props_result:
            label = record['label']
            properties = record['properties']
            stats["node_properties"][label] = properties
        
        # 查询5: 获取每类关系的属性
        rel_props_query = """
        MATCH (a)-[r]->(b)
        WHERE NOT ('character' IN labels(a) AND 'character' IN labels(b))
        WITH type(r) as rel_type, r
        UNWIND keys(r) AS prop
        RETURN rel_type, collect(DISTINCT prop) as properties
        ORDER BY rel_type
        """
        rel_props_result = kg.execute_query(rel_props_query)
        for record in rel_props_result:
            rel_type = record['rel_type']
            properties = record['properties']
            stats["relationship_properties"][rel_type] = properties
            
    except Exception as e:
        st.error(f"获取统计信息时出错: {e}")
    
    return stats

def display_database_statistics():
    """
    显示数据库统计信息到主页面
    """
    if st.session_state.get('show_stats') and st.session_state.get('database_stats'):
        stats = st.session_state.database_stats
        
        st.subheader("📊 数据库统计信息")
        
        # 节点类型及数量
        with st.expander("节点类型及数量"):
            if stats["node_types"]:
                for node_type in stats["node_types"]:
                    st.text(f"  {node_type}")
            else:
                st.info("未获取到节点信息")
        
        # 关系类型及数量
        with st.expander("关系类型及数量"):
            if stats["relationship_types"]:
                for rel_type in stats["relationship_types"]:
                    st.text(f"  {rel_type}")
            else:
                st.info("未获取到关系信息")
        
        # 关系模式
        with st.expander("关系模式"):
            if stats["relationship_patterns"]:
                for pattern in stats["relationship_patterns"]:
                    st.text(f"  {pattern}")
            else:
                st.info("未获取到关系模式信息")
        
        # 节点属性
        with st.expander("节点属性"):
            if stats["node_properties"]:
                for label, props in stats["node_properties"].items():
                    if props:
                        st.text(f"  {label}: {', '.join(props)}")
                    else:
                        st.text(f"  {label}: 无特定属性")
            else:
                st.info("未获取到节点属性信息")
        
        # 关系属性
        with st.expander("关系属性"):
            if stats["relationship_properties"]:
                for rel_type, props in stats["relationship_properties"].items():
                    if props:
                        st.text(f"  {rel_type}: {', '.join(props)}")
                    else:
                        st.text(f"  {rel_type}: 无特定属性")
            else:
                st.info("未获取到关系属性信息")

def test_llm_connection():
    """测试LLM连接"""
    try:
        # 从会话状态获取LLM配置
        llm_config = st.session_state.get("llm_config", {})
        
        # 如果没有保存的配置，尝试从secrets重新获取
        if not llm_config:
            # 首先尝试从openai部分获取配置
            openai_secrets = st.secrets.get("openai", {})
            openai_api_key = openai_secrets.get("api_key", st.secrets.get("openai_api_key", ""))
            openai_api_base = openai_secrets.get("api_base", st.secrets.get("openai_api_base", "https://api.openai.com/v1"))
            model_id = openai_secrets.get("model_id", st.secrets.get("openai_model_id", "gpt-3.5-turbo"))
            
            llm_config = {
                "api_key": openai_api_key,
                "api_base": openai_api_base,
                "model_id": model_id
            }
        
        if not llm_config.get("api_key"):
            st.session_state.llm_status = "未配置"
            st.error("未配置OpenAI API密钥")
            return
        
        with st.spinner("正在测试LLM连接..."):
            client = OpenAI(
                api_key=llm_config["api_key"],
                base_url=llm_config["api_base"]
            )
            
            # 尝试简单的测试请求
            response = client.chat.completions.create(
                model=llm_config["model_id"],
                messages=[{"role": "user", "content": "Hello, say 'test successful' if you can hear me."}],
                max_tokens=10
            )
            
            if response and response.choices:
                st.session_state.llm_status = "已连接"
                st.success("✅ LLM连接测试成功!")
                st.rerun()
            else:
                st.session_state.llm_status = "连接失败"
                st.error("❌ LLM连接测试失败: 无响应")
                
    except Exception as e:
        st.session_state.llm_status = "连接失败"
        st.error(f"❌ LLM连接测试失败: {str(e)}")
        st.info("请检查API密钥、API端点地址和网络连接")