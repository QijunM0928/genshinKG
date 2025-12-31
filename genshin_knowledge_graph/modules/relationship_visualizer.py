# modules/relationship_visualizer.py
import streamlit as st
from pyvis.network import Network
import tempfile
import os
import logging
import traceback
import json
from typing import List, Dict, Any, Tuple

# 设置日志
logger = logging.getLogger(__name__)

# 颜色映射 (保持不变)
country_colors = {
    "蒙德": "#FFC107", "璃月": "#FF8800", "稻妻": "#9C27B0",
    "须弥": "#8BC34A", "枫丹": "#288ADA", "纳塔": "#FF3C22",
    "至冬": "#00BCD4", "挪德卡莱": "#78192C", "其他": "#9E9E9E",
    None: "#9E9E9E"
}


# --- 辅助函数 ---

def safe_read_file(file_path: str) -> str:
    """安全读取文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except:
            return ""


def inject_custom_js(html_content: str) -> str:
    """注入交互脚本：悬停高亮，点击聚焦"""
    custom_js = """
    <script type="text/javascript">
    document.addEventListener("DOMContentLoaded", function() {
        var checkNetwork = setInterval(function() {
            if (typeof network !== 'undefined' && network.body && network.body.data) {
                clearInterval(checkNetwork);
                initInteraction();
            }
        }, 200);

        function initInteraction() {
            var allNodes = network.body.data.nodes.get();
            var originalColors = {};
            allNodes.forEach(n => originalColors[n.id] = n.color);

            network.on("hoverNode", function (params) {
                var nodeId = params.node;
                var connectedNodes = network.getConnectedNodes(nodeId);
                connectedNodes.push(nodeId); 
                var connectedEdges = network.getConnectedEdges(nodeId);

                var nodeUpdates = [];
                network.body.data.nodes.getIds().forEach(function(id) {
                    if (!connectedNodes.includes(id)) {
                        nodeUpdates.push({id: id, color: {background: 'rgba(200,200,200,0.1)', border: 'rgba(200,200,200,0.1)'}, opacity: 0.1, font: {color: 'rgba(0,0,0,0)'}});
                    }
                });
                network.body.data.nodes.update(nodeUpdates);

                var edgeUpdates = [];
                network.body.data.edges.getIds().forEach(function(id) {
                    if (!connectedEdges.includes(id)) {
                        edgeUpdates.push({id: id, color: {opacity: 0.05}, font: {size: 0}});
                    } else {
                        edgeUpdates.push({id: id, color: {opacity: 1}, width: 2});
                    }
                });
                network.body.data.edges.update(edgeUpdates);
            });

            network.on("blurNode", function (params) {
                var nodeUpdates = [];
                network.body.data.nodes.get().forEach(function(node) {
                    nodeUpdates.push({id: node.id, color: originalColors[node.id], opacity: 1, font: {color: 'black'}});
                });
                network.body.data.nodes.update(nodeUpdates);

                var edgeUpdates = [];
                network.body.data.edges.get().forEach(function(edge) {
                    edgeUpdates.push({id: edge.id, color: {opacity: 1}, font: {size: 12}, width: 1});
                });
                network.body.data.edges.update(edgeUpdates);
            });
        }
    });
    </script>
    """
    if '</body>' in html_content:
        return html_content.replace('</body>', custom_js + '\n</body>')
    return html_content + custom_js


def save_network_to_html(net: Network) -> str:
    """保存并注入JS"""
    try:
        fd, temp_path = tempfile.mkstemp(suffix='.html')
        os.close(fd)
        net.save_graph(temp_path)
        content = safe_read_file(temp_path)

        # 清理内容
        lines = [l for l in content.split('\n') if 'Genshin Impact' not in l and '原神' not in l]
        content = '\n'.join(lines)
        if '<head>' in content and '<meta charset=' not in content:
            content = content.replace('<head>', '<head>\n    <meta charset="UTF-8">')

        content = inject_custom_js(content)

        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return temp_path
    except Exception as e:
        logger.error(f"保存失败: {e}")
        return ""


def display_html_file(file_path: str, height: int = 800):
    if file_path and os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            st.components.v1.html(f.read(), height=height, scrolling=False)


def display_color_legend():
    """颜色图例"""
    cols = st.columns(5)
    for i, (country, color) in enumerate(country_colors.items()):
        with cols[i % 5]:
            st.markdown(f"<span style='color:{color}'>■</span> {country}", unsafe_allow_html=True)


# --- 核心数据逻辑 ---

@st.cache_data(ttl=3600)
def get_all_character_names(_kg) -> List[str]:
    """获取所有角色名单，用于搜索下拉框"""
    try:
        query = "MATCH (c:character) RETURN c.name as name ORDER BY c.name"
        result = _kg.execute_query(query)
        return [r['name'] for r in result]
    except:
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def get_graph_data(_kg, limit: int = 40, focus_character: str = None) -> Tuple[List[Dict], List[Dict]]:
    """
    智能数据获取 (去重聚合版)
    """
    try:
        if focus_character and focus_character != "全局概览":
            # --- 聚焦模式 ---
            nodes_query = """
            MATCH (center:character {name: $name})
            OPTIONAL MATCH (center)-[r]-(neighbor:character)
            WITH center, neighbor
            LIMIT $limit
            WITH center, collect(DISTINCT neighbor) as neighbors
            WITH neighbors + [center] as all_nodes
            UNWIND all_nodes as c
            RETURN DISTINCT c.name as name, c.country as country, c.rarity as rarity
            """
            params = {"name": focus_character, "limit": limit}

        else:
            # --- 全局模式 ---
            nodes_query = """
            MATCH (c:character)
            WITH c, COUNT { (c)--() } as degree
            ORDER BY degree DESC
            LIMIT $limit
            RETURN c.name as name, c.country as country, c.rarity as rarity
            """
            params = {"limit": limit}

        characters = _kg.execute_query(nodes_query, params)
        if not characters: return [], []

        char_names = [c['name'] for c in characters]

        # --- 👇 重点修改了这里 👇 ---
        # 原来的查询直接返回每条边，导致重复
        # 现在的查询：按(起点, 终点)分组，把所有关系类型收集起来去重，再拼成字符串
        rel_query = """
        MATCH (c1:character)-[r]->(c2:character)
        WHERE c1.name IN $names AND c2.name IN $names

        // 1. 获取基础信息
        WITH c1, c2, type(r) as r_type

        // 2. 聚合去重：如果c1->c2有两条'朋友'，这里变一条；如果有'朋友'和'队友'，变成列表
        WITH c1.name as source, c2.name as target, collect(DISTINCT r_type) as types

        // 3. 返回数据 (Python端就不需要处理了)
        RETURN source, target, types as relationship_type_list
        """

        relationships_raw = _kg.execute_query(rel_query, {"names": char_names})

        # Python端简单处理：把列表拼成字符串 "朋友 / 队友"
        relationships = []
        for r in relationships_raw:
            # 将列表 joined 为字符串，例如 ["朋友", "队友"] -> "朋友 / 队友"
            # 如果只有一个 ["朋友"] -> "朋友"
            combined_type = " / ".join(r['relationship_type_list'])

            relationships.append({
                'source': r['source'],
                'target': r['target'],
                'relationship_type': combined_type
            })

        return characters, relationships

    except Exception as e:
        logger.error(f"Data query error: {e}")
        st.error(f"查询出错: {str(e)}")
        return [], []


def create_network_graph(characters, relationships, config):
    """创建 PyVis 对象"""
    net = Network(height="700px", width="100%", notebook=False, directed=True, bgcolor="#ffffff", font_color="black")

    # 物理引擎配置
    options = {
        "physics": {
            "enabled": config.get('physics', True),
            "solver": "barnesHut",
            "barnesHut": {
                "gravitationalConstant": -3000, "centralGravity": 0.3, "springLength": 120, "avoidOverlap": 0.2
            },
            "stabilization": {"enabled": True, "iterations": 800}
        },
        "interaction": {
            "hover": True, "zoomView": True
        },
        "edges": {
            # 1. 【核心修改】解决重合问题
            # type: # dynamic会自动检测重合的边，并把它们弯曲分开
            "smooth": {
                "enabled": True,  # 必须开启
                "type": "dynamic",  # 动态类型，专治多重边重叠
                "roundness": 0.5  # 弯曲幅度
            },

            # 2. 箭头与粗细 (保留上次的优化)
            "arrows": {
                "to": {
                    "enabled": True,
                    "scaleFactor": 0.5  # 箭头大小
                }
            },
            "width": 1.5,  # 线条粗细

            "color": {
                "inherit": "to",
                "opacity": 0.7
            },

            "font": {
                "size": 10,
                "align": "middle",
                "background": "rgba(255,255,255,0.8)",
                "strokeWidth": 0
            }
        },
        "nodes": {
            "shape": "dot",
            "scaling": {"min": 15, "max": 35},
            "font": {"size": 14}
        }
    }
    net.set_options(json.dumps(options))

    # 添加节点
    for c in characters:
        name = c['name']
        is_focus = config.get('focus_char') == name

        # 如果是聚焦的主角，画大一点，特殊颜色
        size = 35 if is_focus else (25 if str(c.get('rarity')).startswith('5') else 18)
        border = 3 if is_focus else (2 if str(c.get('rarity')).startswith('5') else 1)

        net.add_node(
            n_id=name, label=name,
            color=country_colors.get(c.get('country'), "#9E9E9E"),
            size=size, borderWidth=border,
            title=f"{name}\n{c.get('country')}"
        )

    # 添加边
    for r in relationships:
        net.add_edge(source=r['source'], to=r['target'], label=r['relationship_type'])

    return net


# --- 主界面 ---

def display_character_relationship_visualization(kg):
    if not kg.is_connected:
        st.warning("请连接数据库")
        return

    # 1. 获取所有角色名单 (用于搜索)
    all_names = get_all_character_names(_kg=kg)

    # --- 侧边栏控制区 ---
    with st.container():  # 使用 container 让控制区紧凑
        c1, c2, c3 = st.columns([2, 1, 1])

        with c1:
            # 核心改进：搜索框
            # 默认选项是 "全局概览"，下面是所有角色名
            options = ["全局概览"] + all_names
            selected_view = st.selectbox(
                "🔍 搜索/选择中心角色",
                options,
                index=0,
                help="选择'全局概览'查看Top热点；选择具体角色查看其个人关系网"
            )

        with c2:
            # 节点数量控制，默认 40
            limit_num = st.number_input("节点数量限制", min_value=10, max_value=100, value=40, step=10)

        with c3:
            st.write("")  # Spacer
            force_refresh = st.button("🔄 刷新视图")

    # --- 缓存与状态管理 ---
    # 定义配置指纹
    current_config = {
        "view": selected_view,
        "limit": limit_num,
        "ts": 0  # 简单的版本控制
    }

    # 检查是否可以直接使用缓存HTML
    if (not force_refresh and
            st.session_state.get("last_graph_config") == current_config and
            os.path.exists(st.session_state.get("graph_html_path", ""))):

        # 显示缓存
        display_html_file(st.session_state.graph_html_path, height=700)

        # 显示当前模式的状态提示
        if selected_view == "全局概览":
            st.caption(f"当前模式：🔥 全局热点 Top {limit_num}")
        else:
            st.caption(f"当前模式：🎯 角色聚焦 - {selected_view} 及其邻居")

        with st.expander("🎨 颜色图例"):
            display_color_legend()
        return

    # --- 重新渲染 ---
    status = st.empty()
    progress = st.progress(0)

    try:
        # 1. 查询数据
        status.text("正在提取图谱数据...")
        progress.progress(20)

        chars, rels = get_graph_data(_kg=kg, limit=limit_num, focus_character=selected_view)

        if not chars:
            st.warning("未找到相关数据")
            progress.empty()
            return

        # 2. 构建图
        status.text(f"正在渲染 {len(chars)} 个节点, {len(rels)} 条关系...")
        progress.progress(60)

        graph_config = {
            "physics": True,
            "high_perf": True,
            "focus_char": selected_view  # 传入选中的角色名，用于高亮
        }
        net = create_network_graph(chars, rels, graph_config)

        # 3. 保存 HTML
        html_path = save_network_to_html(net)

        # 更新 Session
        st.session_state.graph_html_path = html_path
        st.session_state.last_graph_config = current_config

        progress.progress(100)
        status.empty()
        progress.empty()

        # 4. 显示
        display_html_file(html_path, height=700)

        # 底部信息
        if selected_view == "全局概览":
            st.info(f"🔥 全局视图：显示了连接数最多的 {len(chars)} 个角色。如需查看特定边缘角色，请在上方搜索框选择。")
        else:
            st.success(f"🎯 聚焦视图：中心角色 **{selected_view}**。显示了与其最相关的 {len(chars) - 1} 个邻居。")

        with st.expander("🎨 颜色图例"):
            display_color_legend()

    except Exception as e:
        st.error(f"渲染错误: {str(e)}")
        logger.error(traceback.format_exc())


def quick_visualization(kg, character_name: str = None):
    pass