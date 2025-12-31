这是一个关于原神的知识图谱
使用neo4j存储图谱，使用streamlit完成前端和可视化 (使用pyvis实现图可视化)

先下载所有的依赖库：
    pip install -r requirements.txt

为了在浏览器上与图谱交互，在终端运行：
    streamlit run app.py


项目架构：
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
  │   ├── monster_panel.py      # 怪物查询模块
  │   └── relationship_visualizer.py  # 角色关系可视化模块
  │  
  └── requirements.txt          # 依赖包列表



图谱的基本信息：
================================================
节点类型及数量:
  - character_voice: 7735个
  - material: 719个
  - monster: 498个
  - weapon: 226个
  - character: 115个
  - artifact: 57个
  - reaction: 16个
  - country: 9个
  - element: 7个

关系类型及数量:
  - has_voice: 7735条
  - needs_material: 4053条
  - drops_material: 1890条
  - suits_weapon: 775条
  - belongs_role_tag: 348条
  - suits: 347条
  - restrains: 154条
  - has_element: 113条
  - from_country: 108条
  - trigger: 40条

关系模式:
  character --[关系类型]--> character
  character --[belongs_role_tag]--> role_tag
  monster --[drops_material]--> artifact
  monster --[drops_material]--> material
  monster --[drops_material]--> monster
  character --[from_country]--> country
  character --[has_element]--> element
  character --[has_voice]--> character_voice
  character --[needs_material]--> material
  material --[needs_material]--> material
  weapon --[needs_material]--> material
  character --[restrains]--> monster
  character --[suits]--> artifact
  character --[suits_weapon]--> weapon
  element --[trigger]--> reaction
  reaction --[trigger]--> reaction

节点属性:
 - artifact: id, min/max_rarity, 4piece_effect, name, source, 2piece_effect, img_src, suits_roles
 - character: id, name, img_src, profession, birthday, country, cn_CV, gender, weapon_type, description, title, primordial_force, constellation, affiliation, species, nickname, body_type, special_dish, TAG, rarity, element
 - character_voice: id, name, title, cn_audio, cn_text
 - country: id, name, description, army, en_name
 - element: id, name
 - material: id, name, source, img_src, type, usage
 - monster: id, name, img_src, TAG, element, type, drop, region, strategy, refresh_time
 - reaction: id, name, reaction_element
 - role_tag: id, name, description, aliases
 - weapon: id, name, source, img_src, rarity, type, max_subproperty, min_subproperty, min_attack, effect, max_attack

关系属性:
  belongs_role_tag: reasoning_hint, evidence_rule, evidence_value, evidence_side, evidence_confidence, evidence_field
  from_country: reasoning_hint, evidence_rule, evidence_value, evidence_side, evidence_confidence, evidence_field
  has_element: reasoning_hint, evidence_rule, evidence_value, evidence_side, evidence_confidence, evidence_field
  needs_material: reasoning_hint, evidence_rule, evidence_value, evidence_side, evidence_confidence, evidence_field
  restrains: reasoning_hint, evidence_rule, evidence_value, evidence_side, evidence_confidence, evidence_field
  suits: reasoning_hint, evidence_rule, evidence_value, evidence_side, evidence_confidence, evidence_field
  suits_weapon: reasoning_hint, evidence_rule, evidence_value, evidence_side, evidence_confidence, evidence_field, priority
================================================