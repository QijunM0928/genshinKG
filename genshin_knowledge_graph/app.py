"""
原神知识图谱浏览器 - 主应用

重构版：模块化结构，主文件只负责路由和协调
"""
import streamlit as st
import sys
import os

# 添加项目根目录到Python路径，确保可以导入本地模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from neo4j_connector import get_graph_connection, GenshinKnowledgeGraph
from modules.connection_manager import setup_sidebar
from modules.connection_manager import display_database_statistics
from modules.qa_panel import display_qa_panel
from modules.character_panel import display_character_panel
from modules.weapon_panel import display_weapon_panel
from modules.artifact_panel import display_artifact_panel
from modules.monster_panel import display_monster_panel
from modules.relationship_visualizer import \
    display_character_relationship_visualization

# 页面配置（必须放在最前面）
st.set_page_config(
    page_title="原神知识图谱浏览器",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded"
)

def init_session_state():
    """初始化会话状态"""
    if 'db_initialized' not in st.session_state:
        st.session_state.db_initialized = False
    if 'connection_status' not in st.session_state:
        st.session_state.connection_status = "未连接"
    if 'show_stats' not in st.session_state:
        st.session_state.show_stats = False
    # 添加查询状态标志
    if 'last_query_successful' not in st.session_state:
        st.session_state.last_query_successful = None
    # 添加当前选中的标签页
    if 'current_tab' not in st.session_state:
        st.session_state.current_tab = 0  # 默认第一个标签页
    # 初始化问答历史
    if 'qa_history' not in st.session_state:
        st.session_state.qa_history = []

def main():
    """主函数"""
    # 初始化
    init_session_state()
    
    # 获取数据库连接实例
    kg = get_graph_connection()
    
    # 设置侧边栏并检查连接状态
    is_connected = setup_sidebar(kg)
    
    # 主页面内容
    st.title("🎮 原神知识图谱浏览器")
    st.markdown("""
    ### 欢迎使用原神知识图谱交互式浏览器
    
    这是一个基于 **Neo4j 图数据库** 和 **Streamlit** 构建的原神游戏知识探索工具。
    通过这个工具，你可以：
    
    - 🤖 **智能问答**使用自然语言查询原神的相关信息
    - 🔍 **探索**原神游戏中的角色、武器、圣遗物、怪物等实体关系
    - 🎯 **查询**具体的游戏数据信息
    - 📊 **可视化**复杂的关联网络
    
    ---
    """)
    
    # 根据连接状态显示不同内容
    if not is_connected:
        st.info("👈 请先在左侧侧边栏连接数据库以开始探索")
        
        # 显示使用说明
        with st.expander("📖 使用说明", expanded=True):
            st.markdown("""
            0. 确保`.streamlit/secrets.toml`文件已配置正确的数据库、LLM的连接信息。
            1. 在左侧侧边栏点击"连接数据库"按钮
            2. 连接成功后，可以查看数据库统计信息，或使用各项功能。
            
            **注意**: 请谨慎处理`secrets.toml`文件，避免泄露密钥信息。
            """)
        
        # 显示项目结构
        with st.expander("🗂️ 项目结构"):
            st.code("""
            genshin_knowledge_graph/
            ├── .streamlit/
            │   └── secrets.toml          # 存储数据库密码
            ├── app.py                    # 主应用文件
            ├── neo4j_connector.py        # Neo4j连接和查询模块
            ├── modules/
            │   ├── __init__.py
            │   ├── connection_manager.py # 数据库连接模块
            │   ├── database_stats.py     # 数据库统计模块
            │   ├── qa_panel.py           # 智能问答模块
            │   ├── character_panel.py    # 角色查询模块
            │   ├── weapon_panel.py       # 武器查询模块
            │   ├── artifact_panel.py     # 圣遗物查询模块
            │   └── relationship_visualizer.py  # 角色关系可视化模块
            └── requirements.txt          # 依赖包列表
            """)
    else:
        # 显示连接成功的信息
        st.success(f"✅ 已成功连接到数据库")
        
        # 显示数据库基本信息
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("连接状态", "🟢 正常")
        with col2:
            st.metric("数据库", kg.stats.get("db_name", "Unknown"))
        with col3:
            st.metric("版本", kg.stats.get("db_version", "Unknown"))
        
        # 显示统计信息（如果用户点击了显示按钮）
        if st.session_state.show_stats:
            display_database_statistics()
        
        # 功能占位符
        st.divider()
        st.subheader("🎮 功能面板")
        
        # 创建标签页，问答系统放在第一个
        tab_labels = ["智能问答", "角色查询", "武器查询", "圣遗物查询", "怪物查询", "关系可视化"]
        tabs = st.tabs(tab_labels)
        
        # 获取当前选中的标签页
        current_tab = st.session_state.get('current_tab', 0)
        
        # 更新各个标签页的内容：
        with tabs[0]:
            display_qa_panel(kg)
            
        with tabs[1]:
            # 如果用户点击了角色样本按钮，确保停留在这个标签页
            if st.session_state.get('switch_to_character', False):
                st.session_state.switch_to_character = False
            display_character_panel(kg)
            
        with tabs[2]:
            # 如果用户点击了武器样本按钮，确保停留在这个标签页
            if st.session_state.get('switch_to_weapon', False):
                st.session_state.switch_to_weapon = False
            display_weapon_panel(kg)
            
        with tabs[3]:
            # 如果用户点击了圣遗物样本按钮，确保停留在这个标签页
            if st.session_state.get('switch_to_artifact', False):
                st.session_state.switch_to_artifact = False
            display_artifact_panel(kg)
        
        with tabs[4]:
            # 如果用户点击了怪物样本按钮，确保停留在这个标签页
            if st.session_state.get('switch_to_monster', False):
                st.session_state.switch_to_monster = False
            display_monster_panel(kg)

        with tabs[5]:
            display_character_relationship_visualization(kg)
        
        # 快速操作
        st.divider()
        st.subheader("⚡ 快速操作")
        
        quick_col1, quick_col2, quick_col3 = st.columns(3)
        
        with quick_col1:
            if st.button("🔄 刷新数据", use_container_width=True):
                st.rerun()
        
        with quick_col2:
            if st.button("📋 复制连接信息", use_container_width=True):
                # 这里可以添加复制功能
                st.info("复制功能将在后续版本中添加")
        
        with quick_col3:
            if st.button("❓ 获取帮助", use_container_width=True):
                st.info("帮助文档将在后续版本中添加")

if __name__ == "__main__":
    main()
