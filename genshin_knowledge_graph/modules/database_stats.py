"""
数据库统计模块 - 显示数据库统计信息
"""
import streamlit as st
import pandas as pd

def display_database_stats(kg):
    """显示数据库统计信息"""
    st.subheader("📊 数据库统计信息")
    
    with st.spinner("正在获取数据库统计信息..."):
        stats = kg.get_database_stats()
        
        if not stats:
            st.warning("无法获取数据库统计信息")
            return
        
        # 显示节点类型统计
        if "node_types" in stats and stats["node_types"]:
            st.write("#### 节点类型分布")
            node_data = []
            for item in stats["node_types"]:
                if isinstance(item, dict) and "label" in item and "count" in item:
                    node_data.append({
                        "类型": item["label"],
                        "数量": item["count"]
                    })
            
            if node_data:
                node_df = pd.DataFrame(node_data)
                st.dataframe(node_df, use_container_width=True, hide_index=True)
        
        # 显示关系类型统计
        if "relationship_types" in stats and stats["relationship_types"]:
            st.write("#### 关系类型分布")
            rel_data = []
            for item in stats["relationship_types"]:
                if isinstance(item, dict) and "type" in item and "count" in item:
                    rel_data.append({
                        "关系类型": item["type"],
                        "数量": item["count"]
                    })
            
            if rel_data:
                rel_df = pd.DataFrame(rel_data)
                st.dataframe(rel_df, use_container_width=True, hide_index=True)