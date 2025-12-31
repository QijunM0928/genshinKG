"""
智能问答模块 - 基于LLM的Cypher查询生成和自然语言问答
"""
import streamlit as st
from neo4j import GraphDatabase
from openai import OpenAI
import os
from datetime import datetime
import re
import json
from collections import defaultdict


def is_team_question(q: str) -> bool:
    q = q or ""
    # 覆盖“配队/组队/队友/阵容/搭配/配什么”等自然语言问法
    return any(k in q for k in ["配队", "组队", "队伍", "队友", "阵容", "模板", "候选", "slot", "搭配", "配什么", "怎么配", "和谁", "推荐队友"])


def extract_core_name(q: str) -> str:
    q = (q or "").strip()
    m = re.search(r"^(.*?)(适合|怎么|如何|配队|组队|队伍|队友)", q)
    if m:
        name = m.group(1).strip(" ？?，,。.")
        return name or None
    return q if len(q) <= 6 else None


def is_substitute_question(q: str) -> bool:
    """判断是否是“替代/平替/下位替代/上位替代”类型问题"""
    q = (q or "").strip()
    return any(k in q for k in ["下位替代", "上位替代", "平替", "替代", "代替", "替换", "替换成", "换成"])

def extract_subject_name_for_substitute(q: str) -> str:
    """
    从“X的下位替代是谁 / X平替 / 用谁代替X”这类问法中抽取主体角色名 X
    返回 None 表示未能抽取
    """
    q = (q or "").strip()

    # 1) “X的下位替代/平替/替代...”
    m = re.search(r"^(.*?)(的)?(下位替代|上位替代|平替|替代|代替|替换)", q)
    if m:
        name = (m.group(1) or "").strip(" ？?，,。.")
        if name:
            return name

    # 2) “用谁代替X / 谁能替代X / 谁可以替换X”
    m2 = re.search(r"(用谁|谁能|谁可以|哪个角色).*(代替|替代|替换).*(.*)$", q)
    if m2:
        tail = (m2.group(3) or "").strip(" ？?，,。.")
        # tail 可能是“夜兰”或“夜兰？”或“夜兰这个位置”
        # 只取前 6 个字符做个简单兜底（大多角色名 <= 6）
        return tail[:6] if tail else None

    return None

def is_team_recommend_question(q: str) -> bool:
    """判断是否是“推荐队友/和谁配队”类型问题"""
    q = (q or "").strip()
    # 典型：X适合和谁配队 / X和哪些角色组队 / 推荐X队友
    if re.search(r"(适合|推荐).*(和|跟|与).*(谁|哪些|什么).*(配队|组队|队友|阵容)", q):
        return True
    if re.search(r"(配队|组队|队友|阵容).*(推荐|适合|搭配).*(谁|哪些|什么)", q):
        return True
    # 兜底：包含“适合”和“配队/队友”等关键字
    if ("适合" in q) and any(k in q for k in ["配队", "组队", "队友", "阵容", "搭配"]):
        return True
    return False


def extract_team_template_id(q: str) -> str:
    """从问题里抽取 TeamTemplate 的 id，例如 TT:胡桃:双水蒸发"""
    q = (q or "").strip()
    m = re.search(r"(TT:[^\s，,。?？]+)", q)
    return m.group(1) if m else None


# ---------------------------
# Cypher 生成安全层（防止 LLM 输出非 Cypher / 参数缺失）
# ---------------------------
_VALID_CYPHER_START = re.compile(r"^\s*(MATCH|OPTIONAL\s+MATCH|CALL|WITH|UNWIND|MERGE|CREATE|RETURN|SHOW|PROFILE|EXPLAIN)\b", re.I)

def _sanitize_cypher_output(raw: str):
    """
    1) 去掉 ```cypher 代码块
    2) 尝试从输出中截取第一段合法 Cypher（从关键字开始）
    3) 修正常见前缀错误：'MAT ' -> 'MATCH '
    """
    if raw is None:
        return None, "LLM返回为空"
    s = str(raw).strip()
    s = s.replace("```cypher", "").replace("```", "").strip()

    # 常见错误：开头少了 CH
    if re.match(r"^\s*MAT\b", s, flags=re.I):
        s = re.sub(r"^\s*MAT\b", "MATCH", s, flags=re.I).strip()

    # 从输出中截取第一段可执行 Cypher
    m = re.search(r"\b(OPTIONAL\s+MATCH|MATCH|CALL|WITH|UNWIND|MERGE|CREATE|RETURN|SHOW|PROFILE|EXPLAIN)\b", s, flags=re.I)
    if m and m.start() > 0:
        s = s[m.start():].strip()

    if not _VALID_CYPHER_START.search(s):
        return None, f"LLM未返回可执行的Cypher：{raw}"

    return s, None


def is_country_count_question(q: str) -> bool:
    q = q or ""
    return ("国家" in q) and ("角色" in q) and any(k in q for k in ["多少", "数量", "有多少", "几个", "统计", "分别"])


COUNTRY_CHARACTER_COUNT = """
MATCH (c:character)
WHERE c.country IS NOT NULL
WITH c.country AS country, count(DISTINCT c) AS character_count
RETURN country, character_count
ORDER BY character_count DESC
LIMIT 50
""".strip()


TEAM_TEMPLATE_LIST = """
MATCH (tt)
WHERE tt.label = 'TeamTemplate' AND tt.core_character = $core_name
RETURN tt.id AS team_template_id, tt.archetype_name AS archetype, tt.focus AS focus,
       tt.core_role AS core_role, tt.core_evidence AS core_evidence,
       tt.example_team_members AS example_members, tt.example_team_evidence AS example_evidence
ORDER BY focus DESC, archetype
LIMIT 50
""".strip()

TEAM_TEMPLATE_EXPAND = """
MATCH (tt)
WHERE tt.label='TeamTemplate' AND tt.id = $team_template_id
MATCH (tt)-[:HAS_SLOT_GROUP]->(sg)
MATCH (sg)-[:HAS_SLOT]->(st)
OPTIONAL MATCH (st)-[cand:CANDIDATE]->(ch)
RETURN tt.id AS team_template_id, tt.archetype_name AS archetype,
       sg.name AS slot_group, sg.min_select AS sg_min, sg.max_select AS sg_max, sg.mutual_exclusive AS sg_mutex,
       st.slot AS slot, st.must AS must, st.need AS need,
       ch.id AS candidate_id, ch.name AS candidate_name,
       cand.fit AS fit, cand.evidence_confidence AS confidence, cand.reasoning_hint AS hint
ORDER BY must DESC, confidence DESC
LIMIT 300
""".strip()

# ---------------------------
# “替代/平替/下位替代”问题：规则化查询
# 解释策略：
# - 优先使用 SlotTemplate 的 CANDIDATE 候选集来定义“替代”：同一个 slot 的其它候选，按 evidence_confidence/fit 等信息排序
# - 若未命中（例如该角色在你的图谱里没有 slot 候选记录），再用 role_tag 做一个“功能相近”的兜底候选
# ---------------------------

SUBSTITUTE_BY_SLOT = """
MATCH (st:SlotTemplate)-[cand:CANDIDATE]->(c:character)
WHERE c.name CONTAINS $core_name
WITH st, c, cand, coalesce(cand.evidence_confidence, 0) AS core_conf
MATCH (st)-[cand2:CANDIDATE]->(alt:character)
WHERE alt <> c
WITH st, core_conf, alt, cand2
ORDER BY core_conf DESC, coalesce(cand2.evidence_confidence, 0) DESC
WITH st, core_conf,
     collect({
       name: alt.name,
       fit: cand2.fit,
       confidence: cand2.evidence_confidence,
       hint: cand2.reasoning_hint
     })[0..6] AS substitutes
RETURN
  st.team_template_id AS team_template_id,
  st.slot AS slot,
  core_conf AS core_confidence,
  substitutes
LIMIT 50
""".strip()


SUBSTITUTE_BY_ROLE_TAG = """
MATCH (c:character)-[:belongs_role_tag]->(rt:role_tag)
WHERE c.name CONTAINS $core_name
MATCH (alt:character)-[:belongs_role_tag]->(rt)
WHERE alt <> c
WITH rt, collect(DISTINCT alt.name) AS names
RETURN
  rt.name AS shared_role_tag,
  names[0..20] AS candidates
LIMIT 30
""".strip()



TEAM_RECOMMEND = """
MATCH (tt)
WHERE tt.label='TeamTemplate' AND tt.core_character = $core_name
WITH tt
ORDER BY tt.focus DESC, tt.archetype_name
LIMIT $k
MATCH (tt)-[:HAS_SLOT_GROUP]->(sg)-[:HAS_SLOT]->(st)
OPTIONAL MATCH (st)-[cand:CANDIDATE]->(ch)
WITH tt, sg, st, cand, ch
ORDER BY tt.id, sg.name, st.slot, st.must DESC, cand.evidence_confidence DESC
WITH tt, sg, st,
     collect(DISTINCT {
        candidate_id: ch.id,
        candidate_name: ch.name,
        fit: cand.fit,
        confidence: cand.evidence_confidence,
        hint: cand.reasoning_hint
     })[0..$topn] AS top_candidates
RETURN
  tt.id AS team_template_id,
  tt.archetype_name AS archetype,
  tt.focus AS focus,
  sg.name AS slot_group,
  sg.min_select AS sg_min,
  sg.max_select AS sg_max,
  sg.mutual_exclusive AS sg_mutex,
  st.slot AS slot,
  st.must AS must,
  st.need AS need,
  top_candidates AS candidates,
  tt.example_team_members AS example_members,
  tt.example_team_evidence AS example_evidence
ORDER BY focus DESC, archetype, must DESC, slot
LIMIT 400
""".strip()



class KGQA_System:
    """知识图谱问答系统"""

    def __init__(self, kg_connector):
        """
        初始化问答系统
        Args:
            kg_connector: Neo4j连接器对象
        """
        self.kg = kg_connector
        self.driver = kg_connector.driver
        self.client = None
        self.model_id = None
        self.temperature = 0.3
        self.max_tokens = 1000

        # 1. 先给一个默认的安全提示词，防止后续逻辑崩坏
        self.system_prompt = self._get_fallback_prompt()

        # 初始化LLM客户端
        self._init_llm_client()

        # 动态获取知识图谱结构并构建系统提示词
        if st.session_state.get("llm_status") == "已连接":
            dynamic_prompt = self._build_system_prompt()
            # 只有成功获取到动态prompt才覆盖默认值
            if dynamic_prompt:
                self.system_prompt = dynamic_prompt


    def _manual_schema_constraints(self):
        """手工写死的Schema约束（优先级高于动态schema），用于防止LLM臆造标签/关系/节点。"""
        return """【强制Schema约束（最高优先级）】
你只能使用以下节点标签（label）与关系类型（relationship type）。禁止创造任何未列出的标签/关系名。

一、关系模式（只允许这些关系类型）
character --[关系类型]--> character
SlotTemplate --[CANDIDATE]--> character
TeamTemplate --[CORE]--> character
TeamTemplate --[EXAMPLE_MEMBER]--> character
SlotGroup --[HAS_SLOT]--> SlotTemplate
TeamTemplate --[HAS_SLOT_GROUP]--> SlotGroup
SlotTemplate --[REQUIRES_ROLE_TAG]--> role_tag
character --[belongs_role_tag]--> role_tag
monster --[drops_material]--> artifact
monster --[drops_material]--> material
monster --[drops_material]--> monster
character --[from_country]--> country
character --[has_element]--> element
character --[needs_material]--> material
material --[needs_material]--> material
weapon --[needs_material]--> material
character --[restrains]--> monster
character --[suits]--> artifact
character --[suits_weapon]--> weapon
element --[trigger]--> reaction
reaction --[trigger]--> reaction

二、节点属性（只允许访问这些属性；不要假设别的属性存在）
- SlotGroup: id, name, description, slot_template_ids, label, group_type, mutual_exclusive, min_select, max_select, team_template_id
- SlotTemplate: id, evidence, need, label, slot, slot_group_id, must, team_template_id
- TeamTemplate: id, archetype_name, focus, label, core_evidence, core_character, example_team_members, example_team_evidence, core_role
- artifact: id, min/max_rarity, 4piece_effect, name, source, 2piece_effect, img_src, suits_roles, recommended_roles
- character: id, name, img_src, profession, birthday, country, cn_CV, gender, weapon_type, description, title, primordial_force, constellation, affiliation, species, nickname, body_type, special_dish, TAG, rarity, element
- country: id, name, description, army, en_name
- element: id, name
- material: id, name, source, img_src, type, usage
- monster: id, name, img_src, TAG, element, type, drop, region, strategy, refresh_time
- reaction: id, name, reaction_element
- role_tag: id, name, description, aliases
- weapon: id, name, source, img_src, rarity, type, max_subproperty, min_subproperty, min_attack, effect, max_attack

三、关键说明（非常重要，避免生成错误Cypher）
- cn_CV 是 character 节点的【属性】（character.cn_CV），不是节点，也不是关系类型。禁止生成 (:cv) 节点或 [:cn_CV] 关系。
- 同配音/同国家/同元素 这类问题优先用属性分组：
  WITH x, collect(DISTINCT name) AS list
  WHERE size(list) > 1
  RETURN x, list
  LIMIT 20
- RETURN 时优先返回可读的标量属性：例如 c.name, m.name, country.name；避免直接 RETURN 整个节点变量（例如 RETURN cv）。
"""


    def _get_fallback_prompt(self):
        """返回默认的、不依赖数据库查询的提示词（基于手工Schema约束）"""
        schema = self._manual_schema_constraints()
        return f"""你是一个原神知识图谱的 Cypher 查询专家。请根据用户的问题，生成可执行的 Neo4j Cypher 查询语句。

{schema}

【生成要求】
1) 只输出 Cypher 查询语句，不要解释，不要 Markdown 代码块。
2) 只能使用上面列出的标签/关系/属性；不要创造任何不存在的关系或节点（尤其禁止 cv 节点、禁止 cn_CV 关系）。
3) 尽量使用模糊查询：对 name 字段用 `CONTAINS`（例如 `WHERE c.name CONTAINS '胡桃'`）。
4) 输出要“可读”：RETURN 时用 `AS` 给字段起清晰名字（例如 `c.name AS character`），避免 RETURN 整个节点变量。
5) 默认加 `LIMIT 20`。

【常见模式示例（仅作参考，可按问题调整）】
- 角色信息：MATCH (c:character) WHERE c.name CONTAINS '钟离' RETURN c.name AS name, c.description AS description, c.rarity AS rarity LIMIT 20
- 角色突破材料：MATCH (c:character)-[:needs_material]->(m:material) WHERE c.name CONTAINS '钟离' RETURN c.name AS character, collect(DISTINCT m.name) AS materials LIMIT 20
- 怪物掉落：MATCH (mon:monster)-[:drops_material]->(m) WHERE mon.name CONTAINS '丘丘' RETURN mon.name AS monster, collect(DISTINCT m.name) AS drops LIMIT 20
- 武器适合角色：MATCH (w:weapon)<-[:suits_weapon]-(c:character) WHERE w.name CONTAINS '护摩' RETURN w.name AS weapon, collect(DISTINCT c.name) AS characters LIMIT 20
- 相同中文配音：MATCH (c:character) WHERE c.cn_CV IS NOT NULL AND c.cn_CV <> '' WITH c.cn_CV AS cn_CV, collect(DISTINCT c.name) AS characters WHERE size(characters) > 1 RETURN cn_CV, characters LIMIT 20

用户问题：{{question}}
请生成 Cypher 查询语句：
"""
    def _build_system_prompt(self, print_info=False):
            """动态构建系统提示词，从Neo4j查询知识图谱结构"""
            try:
                # 执行查询语句来获取知识图谱结构
                with self.driver.session() as session:
                    # 查询1: 获取节点类型及数量
                    node_query = """
                    MATCH (n)
                    UNWIND labels(n) AS label
                    RETURN label AS node_label, count(*) AS count
                    ORDER BY count DESC
                    """
                    node_result = session.run(node_query)
                    node_info = []
                    for record in node_result:
                        node_info.append(f"- {record['node_label']}: {record['count']}个")

                    # 查询2: 获取关系类型及数量
                    rel_query = """
                    MATCH ()-[r]->()
                    RETURN type(r) as relation_label, count(r) as count
                    ORDER BY count DESC
                    """
                    rel_result = session.run(rel_query)
                    rel_info = []
                    for record in rel_result:
                        rel_info.append(f"- {record['relation_label']}: {record['count']}条")

                    # 查询3: 获取关系模式
                    pattern_query = """
                    MATCH (a)-[r]->(b)
                    RETURN DISTINCT 
                      [label in labels(a) | label] as source_labels, 
                      type(r) as relationship_type, 
                      [label in labels(b) | label] as target_labels
                    ORDER BY relationship_type
                    """
                    pattern_result = session.run(pattern_query)
                    pattern_info = []
                    for record in pattern_result:
                        source = ', '.join(record['source_labels']) if record['source_labels'] else '未知'
                        target = ', '.join(record['target_labels']) if record['target_labels'] else '未知'
                        pattern_info.append(f"- {source} --[{record['relationship_type']}]--> {target}")

                    # 查询4: 获取每类节点的属性
                    node_props_query = """
                    MATCH (n)
                    UNWIND labels(n) AS label
                    WITH label, n
                    LIMIT 100
                    UNWIND keys(n) AS prop
                    RETURN label, collect(DISTINCT prop) as properties
                    ORDER BY label
                    """
                    node_props_result = session.run(node_props_query)
                    node_props_info = {}
                    for record in node_props_result:
                        label = record['label']
                        properties = record['properties']
                        node_props_info[label] = properties

                    # 查询5: 获取每类关系的属性
                    rel_props_query = """
                    MATCH ()-[r]->()
                    WITH type(r) as rel_type, r
                    LIMIT 100
                    UNWIND keys(r) AS prop
                    RETURN rel_type, collect(DISTINCT prop) as properties
                    ORDER BY rel_type
                    """
                    rel_props_result = session.run(rel_props_query)
                    rel_props_info = {}
                    for record in rel_props_result:
                        rel_type = record['rel_type']
                        properties = record['properties']
                        rel_props_info[rel_type] = properties

                    # 构建文本块
                    node_section = "\n".join(node_info) if node_info else "未获取到节点信息"
                    rel_section = "\n".join(rel_info) if rel_info else "未获取到关系信息"
                    pattern_section = "\n".join(pattern_info) if pattern_info else "未获取到关系模式信息"

                    # 构建节点属性部分
                    node_props_section = ""
                    for label, props in node_props_info.items():
                        props_str = ', '.join([p for p in props if p not in ['embedding']]) # 过滤掉embedding等长属性
                        if props_str:
                            node_props_section += f"- {label}: {props_str}\n"
                        else:
                            node_props_section += f"- {label}: 无特定属性\n"

                    if not node_props_section:
                        node_props_section = "未获取到节点属性信息"

                    # 构建关系属性部分
                    rel_props_section = ""
                    for rel_type, props in rel_props_info.items():
                        props_str = ', '.join(props)
                        if props_str:
                            rel_props_section += f"- {rel_type}: {props_str}\n"
                        else:
                            rel_props_section += f"- {rel_type}: 无特定属性\n"

                    if not rel_props_section:
                        rel_props_section = "未获取到关系属性信息"

                # === [关键修复]：这里必须拼接并返回最终的 Prompt 字符串 ===
                manual_constraints = self._manual_schema_constraints()

                final_prompt = f"""
    你是一个原神知识图谱的Cypher查询专家。请根据用户的问题，生成相应的Neo4j查询语句。

    ## 1. 知识图谱 Schema 信息
    以下是当前数据库的实时结构，请严格基于此 Schema 生成查询：

    ### (0) 强制Schema约束（最高优先级，覆盖动态schema）
    {manual_constraints}

    ### (1) 节点类型 (Labels)
    {node_section}

    ### (2) 关系类型 (Relationships)
    {rel_section}

    ### (3) 合法的关系链路 (Patterns)
    {pattern_section}

    ### (4) 节点属性详情
    {node_props_section}

    ### (5) 关系属性详情
    {rel_props_section}

    ## 2. 生成规则
    0. **强制约束**：只能使用 (0) 手工Schema约束里列出的标签/关系/属性；禁止创造未列出的标签/关系；cn_CV 是 character 的属性，不是节点/关系；RETURN 优先返回标量属性，不要 RETURN 整个节点变量。

    1. **只生成 Cypher 语句**：不要包含 Markdown 标记（如 ```cypher），不要包含解释。
    2. **属性匹配**：尽量使用 `CONTAINS` 进行模糊匹配，例如 `WHERE n.name CONTAINS '胡桃'`，因为用户输入可能不精确。
    3. **关系方向**：请注意 `pattern_section` 中的方向，虽然 Cypher 可以忽略方向，但建议根据 Schema 指定正确方向或使用无向查询 `()-[]-()`。
    4. **多跳查询**：如果问题涉及复杂的逻辑（如“胡桃的突破材料在哪里刷”），请生成多跳查询。
    5. **限制返回**：请始终加上 `LIMIT 20` 防止返回过多数据。
    6. **无结果处理**：不需要在 Cypher 里处理，由后续程序处理。

    ## 3. 用户输入
    用户问题：{{question}}

    请生成 Cypher 查询语句：
    """
                return final_prompt

            except Exception as e:
                st.error(f"获取知识图谱结构失败: {str(e)}")
                # 返回默认的系统提示词
                return self._get_fallback_prompt()

    def _init_llm_client(self):
        """初始化LLM客户端"""
        try:
            # 首先尝试从会话状态获取已测试成功的LLM配置
            if 'llm_config' in st.session_state and st.session_state.llm_config:
                llm_config = st.session_state.llm_config
                openai_api_key = llm_config.get("api_key", "")
                openai_api_base = llm_config.get("api_base", "[https://api.openai.com/v1](https://api.openai.com/v1)")
                self.model_id = llm_config.get("model_id", "gpt-3.5-turbo")
                st.info(f"✅ 从会话状态获取LLM配置: {self.model_id}")
            else:
                # 如果会话状态中没有，再从Streamlit secrets获取API配置
                openai_secrets = st.secrets.get("openai", {})
                openai_api_key = openai_secrets.get("api_key", st.secrets.get("openai_api_key", ""))
                openai_api_base = openai_secrets.get("api_base",
                                                     st.secrets.get("openai_api_base", "[https://api.openai.com/v1](https://api.openai.com/v1)"))
                self.model_id = openai_secrets.get("model_id", st.secrets.get("openai_model_id", "gpt-3.5-turbo"))
                st.info(f"ℹ️ 从secrets获取LLM配置: {self.model_id}")

            if not openai_api_key:
                st.warning("❌ 未配置OpenAI API密钥，问答功能将受限")
                if 'llm_status' in st.session_state:
                    st.session_state.llm_status = "未配置"
                return

            self.client = OpenAI(
                api_key=openai_api_key,
                base_url=openai_api_base
            )

            # 测试连接（简化版）
            try:
                self.client.chat.completions.create(
                    model=self.model_id,
                    messages=[{"role": "user", "content": "Hello"}],
                    max_tokens=5
                )
                st.success("✅ LLM客户端初始化成功")
                if 'llm_status' in st.session_state:
                    st.session_state.llm_status = "已连接"
            except Exception as test_error:
                st.warning(f"⚠️ LLM客户端已创建但连接测试失败: {str(test_error)}")
                if 'llm_status' in st.session_state:
                    st.session_state.llm_status = "连接测试失败"

        except Exception as e:
            st.error(f"❌ 初始化LLM客户端失败: {str(e)}")
            self.client = None
            if 'llm_status' in st.session_state:
                st.session_state.llm_status = "初始化失败"

    def generate_cypher(self, question):
        """将自然语言问题映射为 (cypher, params, error)"""
        question = (question or "").strip()

        # 0) “替代/平替/下位替代”类问题：走规则映射（把语义落到现有图谱可查询的结构上）
        if is_substitute_question(question):
            core = extract_subject_name_for_substitute(question) or extract_core_name(question)
            if not core:
                return None, None, "没从问题中识别出要被替代的核心角色名（例如：夜兰/行秋）"
            # 先按 slot 候选查“可替代角色”（同 slot 的其它候选）
            return SUBSTITUTE_BY_SLOT, {"core_name": core}, None


        # 0) 配队类问题：走规则映射（避免 LLM 乱生成剧情关系）
        if is_team_question(question):
            tt_id = extract_team_template_id(question)
            if tt_id:
                return TEAM_TEMPLATE_EXPAND, {"team_template_id": tt_id}, None

            core = extract_core_name(question)
            if not core:
                return None, None, "没从问题中识别出核心角色名（例如：胡桃/诺艾尔/神里绫华）"

            # “X适合和谁配队/推荐队友” → 直接返回候选结构
            if is_team_recommend_question(question):
                return TEAM_RECOMMEND, {"core_name": core, "k": 5, "topn": 6}, None

            # 其它配队相关（例如“有哪些配队模板”）→ 先列出模板
            return TEAM_TEMPLATE_LIST, {"core_name": core}, None

        # 0.1) 常见统计类问题：规则直连（避免LLM输出解释文字导致Cypher不可执行）
        if is_country_count_question(question):
            return COUNTRY_CHARACTER_COUNT, {}, None

        # 1) 非配队问题：走LLM生成Cypher
        if not self.client:
            return None, None, "LLM客户端未初始化，请检查API配置"

        try:
            if not self.system_prompt:
                self.system_prompt = self._get_fallback_prompt()

            prompt = self.system_prompt.replace("{question}", question)

            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": "你是一个专业的知识图谱查询生成助手。只输出可执行Cypher，不要解释。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            raw = response.choices[0].message.content
            cypher, sanitize_err = _sanitize_cypher_output(raw)
            if sanitize_err:
                return None, None, sanitize_err

            return cypher, {}, None

        except Exception as e:
            return None, None, f"生成Cypher查询失败: {str(e)}"

    def execute_query(self, cypher, params=None):
        """执行Cypher查询"""
        try:
            with self.driver.session() as session:
                result = session.run(cypher, params or {})
                records = []
                for record in result:
                    records.append(dict(record))
                return records, None
        except Exception as e:
            return None, f"执行查询失败: {str(e)}"

    def _freeze_for_dedup(self, x):
        """把 dict/list 递归变成可 hash 的结构，用于去重"""
        if isinstance(x, dict):
            return tuple(sorted((k, self._freeze_for_dedup(v)) for k, v in x.items()))
        if isinstance(x, list):
            return tuple(self._freeze_for_dedup(v) for v in x)
        return x

    def _clean_results(self, query_results, max_rows=120):
        """1) 精确去重 2) 截断超长字符串 3) 限制行数，减少LLM跑偏"""
        if not isinstance(query_results, list):
            return query_results

        seen = set()
        cleaned = []
        for r in query_results:
            if not isinstance(r, dict):
                continue
            r2 = {}
            for k, v in r.items():
                if isinstance(v, str) and len(v) > 300:
                    r2[k] = v[:300] + "…"
                else:
                    r2[k] = v

            key = self._freeze_for_dedup(r2)
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(r2)

            if len(cleaned) >= max_rows:
                break
        return cleaned

    def _format_facts_block(self, query_results):
        """把查询结果格式化为【不可改写】的事实清单（逐行锁死），确保数值不会被LLM改动"""
        if isinstance(query_results, dict):
            rows = [query_results]
        elif isinstance(query_results, list):
            rows = query_results
        else:
            return f"- value: {query_results}"

        lines = []
        for row in rows:
            if not isinstance(row, dict):
                lines.append(f"- value: {row}")
                continue

            parts = []
            for k in sorted(row.keys()):
                v = row.get(k)
                if isinstance(v, (dict, list)):
                    v_str = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
                else:
                    v_str = "null" if v is None else str(v)
                parts.append(f"{k}: {v_str}")
            lines.append("- " + "；".join(parts))

        return "\n".join(lines).strip()

    # ---------------------------
    # 通用结果渲染（非配队问题）：结构化结果 -> 易读自然语言
    # ---------------------------
    def _collect_number_atoms(self, rows):
        nums = set()
        if not isinstance(rows, list):
            return nums
        for r in rows:
            if not isinstance(r, dict):
                continue
            for v in r.values():
                if isinstance(v, (int, float)):
                    nums.add(str(v))
                elif isinstance(v, str):
                    for m in re.findall(r"\d+(?:\.\d+)?", v):
                        nums.add(m)
        return nums

    def _numbers_outside_whitelist(self, text, whitelist):
        found = set(re.findall(r"\d+(?:\.\d+)?", text or ""))
        return sorted(found - set(whitelist or []))

    def _render_by_cn_cv(self, rows):
        '''针对“相同中文配音”的两类结果：
        A) rows: [{cn_CV: 'xxx', characters: ['A','B',...]}]
        B) rows: [{character1:'A', character2:'B', cn_CV:'xxx'}] 或键名含 cv/cn_CV
        '''
        if not isinstance(rows, list) or not rows:
            return None

        # A) 已经聚合好了
        if isinstance(rows[0], dict) and (("cn_CV" in rows[0]) or ("cv" in rows[0])) and ("characters" in rows[0]):
            lines = ["这些角色的中文配音演员相同，我按配音演员分组整理如下："]
            for r in rows:
                cv = r.get("cn_CV") or r.get("cv")
                chars = r.get("characters") or []
                if not cv or not isinstance(chars, list) or len(chars) < 2:
                    continue
                uniq = sorted({c for c in chars if isinstance(c, str) and c.strip()})
                if len(uniq) >= 2:
                    lines.append(f"- **{cv}**：{'、'.join(uniq)}")
            return "\n".join(lines).strip() if len(lines) > 1 else None

        # B) 两两配对：聚合一下
        cv_key = None
        for k in rows[0].keys():
            if k in ("cn_CV", "cv"):
                cv_key = k
                break
        if not cv_key:
            return None

        by_cv = defaultdict(set)
        for r in rows:
            cv = r.get(cv_key)
            if not cv:
                continue
            for kk, vv in r.items():
                if kk.startswith("character") and isinstance(vv, str) and vv.strip():
                    by_cv[cv].add(vv.strip())

        if not by_cv:
            return None
        lines = ["这些角色的中文配音演员相同，我按配音演员分组整理如下："]
        for cv, chars in sorted(by_cv.items(), key=lambda x: str(x[0])):
            if len(chars) < 2:
                continue
            lines.append(f"- **{cv}**：{'、'.join(sorted(chars))}")
        return "\n".join(lines).strip() if len(lines) > 1 else None

    def _render_generic_answer(self, question, cleaned_rows):
        # 规则优先：能确定结构的直接格式化（更稳、更不幻觉）
        rule = self._render_by_cn_cv(cleaned_rows)
        if rule:
            return rule

        facts_block = self._format_facts_block(cleaned_rows)

        # 无 LLM：直接返回事实清单（不强制逐字符锁死）
        if not self.client:
            return "根据查询结果：\n" + facts_block

        payload = {
            "question": question,
            "rows": cleaned_rows[:50],
            "requirements": [
                "只可基于 rows 作答，不得编造 rows 未出现的实体、属性或结论",
                "优先归纳/分组/合并，避免逐行复述表格",
                "必要时说明‘结果中未体现’",
                "尽量使用项目符号，回答简洁清晰"
            ]
        }
        payload_str = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

        prompt = f"""用户问题：{question}

下面是数据库查询得到的结构化结果（JSON）：
{payload_str}

请输出面向用户的中文回答，遵守 requirements。不要输出 JSON，不要输出 Cypher。""".strip()

        try:
            resp = self.client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": "你是知识图谱问答助手，负责把结构化查询结果整理成易读的中文回答。严禁臆造。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=800,
            )
            answer = (resp.choices[0].message.content or "").strip()

            # 数字白名单：防止模型乱改数值/次数/稀有度等
            illegal_nums = self._numbers_outside_whitelist(answer, self._collect_number_atoms(cleaned_rows))
            if illegal_nums:
                return "为保证准确性，这里先基于原始查询结果给出要点：\n" + facts_block

            return answer or ("根据查询结果：\n" + facts_block)
        except Exception:
            return "根据查询结果：\n" + facts_block

    def _strip_facts_block_once(self, answer, facts_block):
        """把事实清单从回答里移除一次"""
        idx = (answer or "").find(facts_block)
        if idx < 0:
            return answer or ""
        return (answer or "")[:idx] + (answer or "")[idx + len(facts_block):]

    def _contains_any_numbers(self, s):
        """检测非事实区域是否出现“任何数字表达”"""
        if re.search(r"\d", s or ""):
            return True
        if re.search(r"[零一二三四五六七八九十百千万两]+(?:个|条|项|种|次|位|名|级|层|段|天|年|月|日|小时|分钟|秒)", s or ""):
            return True
        return False



    def _assemble_team_facts(self, core_name: str, templates: list, expanded_rows: list):
        """把 TEAM_TEMPLATE_LIST + TEAM_TEMPLATE_EXPAND 的结果聚合成更适合展示/二次加工的结构。"""
        # templates: list[dict] from TEAM_TEMPLATE_LIST
        # expanded_rows: list[dict] from TEAM_TEMPLATE_EXPAND (possibly multiple templates mixed)
        tmap = {t.get("team_template_id"): t for t in (templates or []) if isinstance(t, dict)}

        # group expanded rows by (team_template_id, slot_group, slot)
        groups = {}
        for r in (expanded_rows or []):
            if not isinstance(r, dict):
                continue
            tid = r.get("team_template_id")
            if not tid:
                continue
            key = (tid, r.get("slot_group"), r.get("slot"))
            groups.setdefault(key, []).append(r)

        facts = []
        for (tid, slot_group, slot), rows in groups.items():
            # pick a representative row for metadata
            rep = rows[0]
            tt = tmap.get(tid, {}) or {}
            # aggregate candidates, dedup by candidate_id/name
            cand_seen = set()
            candidates = []
            for row in rows:
                cid = row.get("candidate_id")
                cname = row.get("candidate_name")
                ckey = cid or cname
                if not ckey or ckey in cand_seen:
                    continue
                cand_seen.add(ckey)
                candidates.append({
                    "candidate_id": cid,
                    "candidate_name": cname,
                    "fit": row.get("fit"),
                    "confidence": row.get("confidence"),
                    "hint": row.get("hint"),
                })

            # sort candidates by confidence desc (None last)
            def _conf_key(c):
                v = c.get("confidence")
                return (-float(v) if isinstance(v, (int, float)) else float("-inf")) if v is not None else float("inf")
            candidates.sort(key=_conf_key)

            facts.append({
                "team_template_id": tid,
                "archetype": rep.get("archetype") or tt.get("archetype"),
                "focus": bool(tt.get("focus")) if "focus" in tt else None,
                "core_character": core_name,
                "example_members": tt.get("example_members"),
                "example_evidence": tt.get("example_evidence"),
                "slot_group": slot_group,
                "sg_min": rep.get("sg_min"),
                "sg_max": rep.get("sg_max"),
                "sg_mutex": rep.get("sg_mutex"),
                "slot": slot,
                "must": rep.get("must"),
                "need": rep.get("need"),
                "candidates": candidates,
            })

        # stable ordering: focus desc, archetype, must desc, slot_group, slot
        def _bool_sort(x):
            return 1 if x else 0
        facts.sort(key=lambda x: (
            -_bool_sort(x.get("focus")),
            str(x.get("archetype") or ""),
            -_bool_sort(x.get("must")),
            str(x.get("slot_group") or ""),
            str(x.get("slot") or ""),
        ))
        return facts

    def _team_payload_for_llm(self, team_facts: list):
        """给 LLM 的配队润色输入：只保留纯文本字段，移除所有可能导致数值被改写的字段。"""
        payload = []
        # group by template
        by_tid = {}
        for item in (team_facts or []):
            if not isinstance(item, dict):
                continue
            tid = item.get("team_template_id")
            if not tid:
                continue
            by_tid.setdefault(tid, {"team_template_id": tid,
                                    "archetype": item.get("archetype"),
                                    "example_members": item.get("example_members"),
                                    "example_evidence": item.get("example_evidence"),
                                    "slots": []})
            # slot entry
            slot_entry = {
                "slot_group": item.get("slot_group"),
                "slot": item.get("slot"),
                "must": bool(item.get("must")),
                "need": item.get("need"),
                "candidates": []
            }
            for c in (item.get("candidates") or []):
                if not isinstance(c, dict):
                    continue
                slot_entry["candidates"].append({
                    "name": c.get("candidate_name"),
                    "hint": c.get("hint"),
                    "fit": c.get("fit"),
                })
            by_tid[tid]["slots"].append(slot_entry)

        # ordering stable
        for tid in sorted(by_tid.keys()):
            payload.append(by_tid[tid])
        return payload

    def _render_team_answer_fallback(self, question: str, team_facts: list):
        """无需LLM的兜底：纯规则生成，保证不产生任何数字表达。"""
        payload = self._team_payload_for_llm(team_facts)
        if not payload:
            return "没有查到可用的配队模板或候选队友。"

        lines = []
        # 注意：这里刻意不输出任何数字
        lines.append(f"关于「{question}」，根据知识图谱的配队模板与候选信息，我整理成更易读的版本如下：")
        for tpl in payload:
            archetype = tpl.get("archetype") or "推荐阵容"
            lines.append(f"\n**{archetype}**")
            em = tpl.get("example_members")
            if isinstance(em, list) and em:
                lines.append("示例队伍：" + "、".join([str(x) for x in em if x]))
            ev = tpl.get("example_evidence")
            if isinstance(ev, str) and ev.strip():
                lines.append("备注：" + ev.strip())

            # slots
            for s in tpl.get("slots") or []:
                slot = s.get("slot") or "位置"
                must = s.get("must")
                need = s.get("need")
                head = f"- {slot}"
                if must:
                    head += "（必选）"
                if isinstance(need, str) and need.strip():
                    head += f"：需求为「{need.strip()}」"
                lines.append(head)

                cands = []
                for c in s.get("candidates") or []:
                    name = c.get("name")
                    hint = c.get("hint")
                    if name and hint:
                        cands.append(f"  - {name}：{hint}")
                    elif name:
                        cands.append(f"  - {name}")
                if cands:
                    lines.extend(cands)
        return "\n".join(lines).strip()
    def generate_answer(self, question, query_results):
        """将查询结果转换为自然语言回答"""
        if not query_results:
            return "查询结果为空，没有找到相关信息。"

        # ===== 配队问题：给用户更友好的文本（同时保证不改动任何数值）=====
        if is_team_question(question):
            # query_results 可能已经是聚合后的 facts，也可能是 expand 的原始行
            team_facts = None
            if isinstance(query_results, list) and query_results and isinstance(query_results[0], dict) and "candidates" in query_results[0]:
                team_facts = query_results
            else:
                # 兜底：把“原始 expand 行”聚合一下（没有 template 元数据也能输出）
                core_name = extract_core_name(question) or ""
                team_facts = self._assemble_team_facts(core_name, templates=[], expanded_rows=query_results)

            # 1) 无LLM：规则化生成（保证不出现数字）
            if not self.client:
                return self._render_team_answer_fallback(question, team_facts)

            # 2) 有LLM：只给纯文本摘要（不含任何数字字段），让LLM做“润色”
            try:
                payload = self._team_payload_for_llm(team_facts)
                payload_str = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                prompt = f"""用户问题：{question}

下面是从知识图谱查询结果中提取的【配队事实摘要】（已去除所有数字字段）：
{payload_str}

请把它润色成面向玩家的推荐说明，要求（必须满足）：
1) 只基于摘要内容写作，不得编造未出现的角色、阵容或结论。
2) 输出中禁止出现任何数字表达（包括阿拉伯数字与中文数字）。
3) 结构清晰：按“阵容类型 -> 位置/需求 -> 候选角色”组织，可补充简短的理解提示。
""".strip()

                response = self.client.chat.completions.create(
                    model=self.model_id,
                    messages=[
                        {"role": "system", "content": "你是一个原神配队助手。只能做语言润色，不得引入或改写任何数值；并且输出中禁止出现任何数字。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=800
                )
                answer = response.choices[0].message.content.strip()

                # 安全校验：如果LLM仍输出了数字，直接回退到规则生成
                if self._contains_any_numbers(answer):
                    return self._render_team_answer_fallback(question, team_facts)
                return answer
            except Exception:
                return self._render_team_answer_fallback(question, team_facts)

        # ===== 非配队问题：通用渲染（结构化结果 -> 易读自然语言）=====
        cleaned = self._clean_results(query_results)
        return self._render_generic_answer(question, cleaned)


    def ask(self, question):
        """完整的问答流程"""
        # 1) 生成Cypher + 参数
        cypher, params, error = self.generate_cypher(question)
        if error:
            return None, error, None
        if not cypher:
            return None, "未能生成查询语句", None

        params = params or {}

        # 参数兜底：如果 LLM 生成的 Cypher 引用了参数，但未返回 params，则从 question 尝试补齐
        if "$core_name" in (cypher or "") and "core_name" not in params:
            core_fallback = extract_core_name(question)
            if core_fallback:
                params["core_name"] = core_fallback

        # 参数兜底：替代问题优先用 extract_subject_name_for_substitute 抽主体
        if is_substitute_question(question) and "core_name" not in params:
            sub_core = extract_subject_name_for_substitute(question)
            if sub_core:
                params["core_name"] = sub_core
        if "$team_template_id" in (cypher or "") and "team_template_id" not in params:
            tid_fallback = extract_team_template_id(question)
            if tid_fallback:
                params["team_template_id"] = tid_fallback
        if "$k" in (cypher or "") and "k" not in params:
            params["k"] = 3
        if "$topn" in (cypher or "") and "topn" not in params:
            params["topn"] = 6

        # 2) 执行查询
        results, error = self.execute_query(cypher, params)
        if error:
            return cypher, error, None

        # 2.1) “替代/平替”问题兜底：如果 slot 候选没查到，再按 role_tag 给一份“功能相近”的候选
        if is_substitute_question(question):
            if isinstance(results, list) and len(results) == 0:
                core = params.get("core_name") or extract_subject_name_for_substitute(question) or extract_core_name(question) or ""
                if core:
                    cypher_fallback = SUBSTITUTE_BY_ROLE_TAG
                    results2, err2 = self.execute_query(cypher_fallback, {"core_name": core})
                    if not err2 and isinstance(results2, list) and results2:
                        # 把 cypher 显示成“主查询 + fallback”，方便你调试
                        cypher = cypher + "\n\n// --- fallback by role_tag ---\n" + cypher_fallback
                        results = results2


        # 3) 生成回答
        try:
            # 3.1 配队问题：如果只是列出模板，则继续展开 slot/candidate，再聚合成 facts
            if is_team_question(question):
                if isinstance(results, list) and results and isinstance(results[0], dict) and "team_template_id" in results[0] and "candidates" not in results[0]:
                    core_name = params.get("core_name") or extract_core_name(question) or ""
                    templates = results

                    focus_templates = [t for t in templates if isinstance(t, dict) and t.get("focus")]
                    expand_targets = focus_templates[:3] if focus_templates else templates[:3]

                    expanded_rows = []
                    for t in expand_targets:
                        tid = t.get("team_template_id")
                        if not tid:
                            continue
                        rows, err2 = self.execute_query(TEAM_TEMPLATE_EXPAND, {"team_template_id": tid})
                        if not err2 and rows:
                            expanded_rows.extend(rows)

                    facts = self._assemble_team_facts(core_name, templates=templates, expanded_rows=expanded_rows)
                    answer = self.generate_answer(question, facts)

                    cypher_display = TEAM_TEMPLATE_LIST + "\n\n// ---\n// expanded by:\n" + TEAM_TEMPLATE_EXPAND
                    return cypher_display, facts, answer

                # TEAM_RECOMMEND / TEAM_TEMPLATE_EXPAND 已经返回 candidates 或原始 expand 行：直接走 generate_answer
                answer = self.generate_answer(question, results)
                return cypher, results, answer

            # 3.2 非配队问题
            answer = self.generate_answer(question, results)
            return cypher, results, answer

        except Exception as e:
            return cypher, results, f"查询成功，但生成回答时出错：{str(e)}"



def display_qa_panel(kg):
    """显示问答面板"""

    # 检查LLM配置是否可用
    if 'llm_status' not in st.session_state or st.session_state.llm_status not in ["已配置", "已连接"]:
        st.warning("⚠️ LLM未配置或未连接，请先在侧边栏配置并测试LLM连接")
        if st.button("🔄 重试初始化LLM"):
            st.rerun()
        return

    # 初始化问答系统
    if 'qa_system' not in st.session_state:
        with st.spinner("正在初始化问答系统..."):
            st.info("正在动态获取知识图谱结构信息...")
            st.session_state.qa_system = KGQA_System(kg)
            st.success("✅ 问答系统初始化完成")

    # 检查问答系统是否成功初始化
    if not hasattr(st.session_state.qa_system, 'client') or st.session_state.qa_system.client is None:
        st.error("问答系统初始化失败，请检查LLM配置")
        if st.button("🔄 重新初始化问答系统"):
            del st.session_state.qa_system
            st.rerun()
        return

    st.header("🤖 智能问答系统")

    st.markdown("""
    使用自然语言提问，系统会自动：
    1. 将您的问题转换为Cypher查询语句
    2. 在知识图谱中执行查询
    3. 将查询结果转换为自然语言回答
    """)

    st.divider()

    # 初始化会话状态
    if 'qa_input_question' not in st.session_state:
        st.session_state.qa_input_question = ""

    if 'last_query_result' not in st.session_state:
        st.session_state.last_query_result = None

    # 问题输入区域
    question = st.text_area(
        "💬 请输入您的问题：",
        value=st.session_state.qa_input_question,
        placeholder="例如：胡桃需要哪些突破材料？",
        height=100,
        key="question_input"
    )

    if question != st.session_state.qa_input_question:
        st.session_state.qa_input_question = question

    col1, col2 = st.columns([1, 1])
    with col1:
        ask_button = st.button("🚀 提问", type="primary", use_container_width=True)
    with col2:
        if st.button("🗑️ 清空输入", use_container_width=True):
            st.session_state.qa_input_question = ""
            st.rerun()

    st.write("💡 快速查询示例（点击直接查询）：")
    example_buttons = [
        "胡桃的详细信息是什么？",
        "神里绫华什么突破材料？对应的来源是什么？",
        "有哪些国家？每个国家有多少角色？",
        "护摩之杖适合哪些角色？",
        "什么角色的中文配音演员相同？"
    ]

    for example_text in example_buttons:
        if st.button(f"🔍 {example_text}"):
            st.session_state.qa_input_question = example_text
            with st.spinner(f"正在查询: {example_text}..."):
                result = {}
                cypher, results_or_error, answer = st.session_state.qa_system.ask(example_text)
                result['question'] = example_text
                result['cypher'] = cypher
                result['answer'] = answer
                if isinstance(results_or_error, str):
                    result['error'] = results_or_error
                    result['results'] = None
                else:
                    result['error'] = None
                    result['results'] = results_or_error
                st.session_state.last_query_result = result
            st.rerun()

    if ask_button and st.session_state.qa_input_question:
        with st.spinner(f"正在查询: {st.session_state.qa_input_question}..."):
            result = {}
            cypher, results_or_error, answer = st.session_state.qa_system.ask(st.session_state.qa_input_question)
            result['question'] = st.session_state.qa_input_question
            result['cypher'] = cypher
            result['answer'] = answer
            if isinstance(results_or_error, str):
                result['error'] = results_or_error
                result['results'] = None
            else:
                result['error'] = None
                result['results'] = results_or_error
            st.session_state.last_query_result = result

    if st.session_state.last_query_result:
        st.divider()
        st.subheader("🔍 问答结果")
        result = st.session_state.last_query_result
        st.caption(f"查询问题: {result['question']}")

        if result.get('error'):
            st.error(f"❌ 发生错误：{result['error']}")
            if result['cypher']:
                with st.expander("📝 查看生成的Cypher查询"):
                    st.code(result['cypher'], language="cypher")
        elif result.get('answer'):
            st.markdown("### 💡 回答")
            st.markdown(result['answer'])
            if result['cypher']:
                with st.expander("📝 查看生成的Cypher查询"):
                    st.code(result['cypher'], language="cypher")
            if result.get('results') and isinstance(result['results'], list) and len(result['results']) > 0:
                with st.expander(f"📊 查看原始查询结果 ({len(result['results'])} 条)"):
                    if len(result['results']) <= 10:
                        st.json(result['results'])
                    else:
                        st.write(f"显示前10条结果:")
                        st.json(result['results'][:10])
        else:
            st.info("没有获取到回答。请尝试重新提问。")

if __name__ == "__main__":
    pass