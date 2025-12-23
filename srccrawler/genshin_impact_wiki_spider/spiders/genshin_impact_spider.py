import json
import scrapy
import re
from bs4 import BeautifulSoup, Tag
from scrapy.spiders import Spider
from scrapy.http import Request
from scrapy.linkextractors import LinkExtractor

BLOCK_TAGS = {"p", "li", "dd", "dt", "h1", "h2", "h3", "h4", "h5", "h6"}

class GenshinImpactSpider(Spider):
    name = 'genshin_impact_spider'
    allowed_domains = ['wiki.biligame.com']
    start_urls = ['https://wiki.biligame.com/ys/%E9%A6%96%E9%A1%B5']

    MATERIAL_API_URL = 'https://wiki.biligame.com/ys/api.php?format=json&action=parse&text=%0A%7B%7Cclass%3D%22wikitable%20sortable%22%20style%3D%22width%3A100%25%3Btext-align%3Acenter%22%0A%7C-%0A!%20class%3D%22headersort%22%20style%3D%22width%3A10%25%22%20%7C%20%E5%9B%BE%E6%A0%87%0A!%20class%3D%22headersort%20hidden-xs%22%20style%3D%22width%3A12%25%22%7C%20%E5%90%8D%E7%A7%B0%0A!%20class%3D%22headersort%20hidden-xs%22%20style%3D%22width%3A8%25%22%20%7C%20%E7%A8%80%E6%9C%89%E5%BA%A6%0A!%20style%3D%22width%3A10%25%22%20%7C%20%E7%B1%BB%E5%9E%8B%0A!%20class%3D%22headersort%22%20style%3D%22width%3A25%25%22%20%7C%20%E6%9D%A5%E6%BA%90%0A!%20class%3D%22headersort%20hidden-xs%22%20style%3D%22width%3A30%25%22%20%7C%20%E7%94%A8%E5%A4%84%0A%7C-%7B%7B%23ask%3A%5B%5B%E5%88%86%E7%B1%BB%3A%E6%9D%90%E6%96%99%5D%5D%7C%3F%E5%90%8D%E7%A7%B0%7C%3F%E7%A8%80%E6%9C%89%E5%BA%A6%7C%3F%E7%B1%BB%E5%9E%8B%7C%3F%E6%9D%A5%E6%BA%90%7C%3F%E4%BB%8B%E7%BB%8D%7C%3F%E7%94%A8%E5%A4%84%7Ctemplate%3D%E7%B4%A0%E6%9D%90%E4%B8%80%E8%A7%88%2F%E8%A1%8C%7Csort%3D%E7%A8%80%E6%9C%89%E5%BA%A6%2C%E7%B1%BB%E5%9E%8B%2C%E5%AE%9E%E8%A3%85%E7%89%88%E6%9C%AC%7Corder%3Ddesc%2Casc%2Cdesc%7Climit%3D50%7Coffset%3D{}%7Cheaders%3Dhide%7Csearchlabel%3D%7Cformat%3Dtemplate%7Clink%3Dnone%7D%7D%7C%7D&contentmodel=wikitext'
    MONSTER_API_URL = 'https://wiki.biligame.com/ys/api.php?format=json&action=parse&text=%0A%7B%7Cclass%3D%22wikitable%20sortable%22%20style%3D%22width%3A100%25%3Btext-align%3Acenter%22%0A%7C-%0A!%20class%3D%22headersort%22%20style%3D%22width%3A10%25%22%20%7C%20%E5%9B%BE%E6%A0%87%0A!%20class%3D%22headersort%22%20style%3D%22width%3A10%25%22%7C%20%E6%80%AA%E7%89%A9%E5%90%8D%0A!%20class%3D%22headersort%22%20style%3D%22width%3A8%25%22%20%7C%20%E5%85%83%E7%B4%A0%E5%B1%9E%E6%80%A7%0A!%20class%3D%22headersort%22%20style%3D%22width%3A10%25%22%20%7C%20%E6%80%AA%E7%89%A9%E7%B1%BB%E5%9E%8B%0A!%20class%3D%22headersort%20visible-md%20visible-sm%20visible-lg%22%20style%3D%22width%3A8%25%22%20%7C%20%E5%88%B7%E6%96%B0%E6%97%B6%E9%97%B4%0A!%20class%3D%22headersort%20visible-md%20visible-sm%20visible-lg%22%20style%3D%22width%3A12%25%22%20%7C%20%E5%87%BA%E7%8E%B0%E5%9C%B0%E7%82%B9%0A!%20class%3D%22headersort%20visible-md%20visible-sm%20visible-lg%22%20%7C%20TAG%0A!%20class%3D%22headersort%20visible-md%20visible-sm%20visible-lg%22%20%7C%20%E6%8E%89%E8%90%BD%E7%B4%A0%E6%9D%90%0A%7C-%7B%7B%23ask%3A%5B%5B%E5%88%86%E7%B1%BB%3A%E6%80%AA%E7%89%A9%5D%5D%7C%3F%E6%80%AA%E7%89%A9%E5%90%8D%7C%3F%E5%85%83%E7%B4%A0%E5%B1%9E%E6%80%A7%7C%3F%E5%88%B7%E6%96%B0%E6%97%B6%E9%97%B4%7C%3F%E5%87%BA%E7%8E%B0%E5%9C%B0%E7%82%B9%7C%3F%E6%8E%89%E8%90%BD%E7%B4%A0%E6%9D%90%7C%3F%E6%80%AA%E7%89%A9%E7%B1%BB%E5%9E%8B%7C%3FTAG%7C%3F%E6%94%BB%E5%87%BB%E5%B1%9E%E6%80%A7%7C%3F%E6%80%AA%E7%89%A9%E5%88%86%E7%B1%BB%7C%3F%E6%80%AA%E7%89%A9%E7%B1%BB%E5%88%AB%7C%3F%E5%AE%9E%E8%A3%85%E7%89%88%E6%9C%AC%7C%3F%E5%85%83%E7%B4%A0%E6%99%B6%E7%9F%B3%7C%3F%E6%8E%89%E8%90%BD%E5%9C%A3%E9%81%97%E7%89%A9%7C%3FBOSS%E7%B4%A0%E6%9D%90%7Ctemplate%3D%E6%80%AA%E7%89%A9%E4%B8%80%E8%A7%88%2F%E8%A1%8C%7Csort%3D%E6%80%AA%E7%89%A9%E7%B1%BB%E5%88%AB%E5%BA%8F%E5%8F%B7%2C%E5%AE%9E%E8%A3%85%E7%89%88%E6%9C%AC%2C%E6%80%AA%E7%89%A9%E5%88%86%E7%B1%BB%2C%E6%80%AA%E7%89%A9%E7%B1%BB%E5%9E%8B%2C%E6%80%AA%E7%89%A9%E5%90%8D%7Corder%3Dasc%2Cdesc%7Climit%3D50%7Coffset%3D{}%7Cheaders%3Dhide%7Csearchlabel%3D%7Cformat%3Dtemplate%7Clink%3Dnone%7D%7D%7C%7D&contentmodel=wikitext'

    @staticmethod
    def _build_api_request(base_url, offset, callback):
        return Request(base_url.format(offset), callback=callback, cb_kwargs={'offset': offset})

    def parse(self, response, **kwargs):
        # 角色筛选页
        links = LinkExtractor(restrict_xpaths='//a[@title="角色图鉴"]')
        for link in links.extract_links(response):
            yield Request(link.url, callback=self.parse_character)

        # 角色详情页 + 角色语音
        links = LinkExtractor(restrict_xpaths='//a[@title="角色图鉴"]')
        for link in links.extract_links(response):
            yield Request(link.url, callback=self.parse_url, cb_kwargs={'cb': 'parse_character_detail'}, dont_filter=True)

        # 武器图鉴
        links = LinkExtractor(restrict_xpaths='//a[@title="武器图鉴"]')
        for link in links.extract_links(response):
            yield Request(link.url, callback=self.parse_weapon)

        # 圣遗物图鉴
        links = LinkExtractor(restrict_xpaths='//a[@title="圣遗物图鉴"]')
        for link in links.extract_links(response):
            yield Request(link.url, callback=self.parse_artifact)

        # API请求：材料和怪物
        yield self._build_api_request(self.MATERIAL_API_URL, 0, self.parse_material)
        yield self._build_api_request(self.MONSTER_API_URL, 0, self.parse_monster)

    def parse_url(self, response, cb, **kwargs):
        # 抓取表格内所有链接并访问
        links = LinkExtractor(restrict_xpaths='//table[@id="CardSelectTr"]').extract_links(response)
        if links:
            for link in links: yield Request(link.url, callback=getattr(self, cb))
        else:
            yield from getattr(self, cb)(response)

    @staticmethod
    def parse_wikitable(table):
        """
        同时支持两种 key-value 形式的表：
        1) <tr><th>key</th><td>value</td></tr>
        2) <tr><th>key</th></tr><tr><td>value</td></tr>
        返回一个 dict，比如：
        {
            "元素": "冰",
            "武器": "长柄武器",
            "角色故事1": "......"
        }
        """
        data = {}

        trs = table.find_all('tr')
        if not trs:
            return data

        i = 0
        n = len(trs)

        while i < n:
            tr = trs[i]
            ths = tr.find_all('th')
            tds = tr.find_all('td')

            # 情况 1：同一行里有 th 和 td
            if ths and tds:
                key = " ".join(th.get_text(strip=True) for th in ths if th.get_text(strip=True))
                value = " ".join(td.get_text(strip=True) for td in tds if td.get_text(strip=True))
                if key:
                    data[key] = value
                i += 1
                continue

            # 情况 2：这一行只有 th，试图和下一行的 td 配对
            if ths and not tds:
                # 确保还有下一行
                if i + 1 < n:
                    next_tr = trs[i + 1]
                    next_ths = next_tr.find_all('th')
                    next_tds = next_tr.find_all('td')

                    # 下一行只有 td，没有 th，才认为是配对结构
                    if next_tds and not next_ths:
                        key = " ".join(th.get_text(strip=True) for th in ths if th.get_text(strip=True))
                        value = " ".join(
                            td.get_text(strip=True) for td in next_tds if td.get_text(strip=True))
                        if key:
                            data[key] = value
                        # 吃掉两行
                        i += 2
                        continue

                # 不满足配对条件，就当普通 header 行丢掉
                i += 1
                continue

            # 其他情况（没有 th，或者只有 td），直接跳过
            i += 1

        return data

    @staticmethod
    def parse_character(response, **kwargs):
        soup = BeautifulSoup(response.text, 'lxml')

        # 表格解析
        tbl = soup.find('table', id='CardSelectTr')
        if tbl:
            ths = tbl.find_all('tr')[0].find_all('th')
            for row in tbl.find_all('tr')[1:]:
                character = {}
                tds =  row.find_all('td')
                for k, v in zip(ths, tds): character[k.get_text(strip=True)] = v.get_text(strip=True)
                yield {'type': 'character', 'data': character}

    def parse_character_detail(self, response, **kwargs):
        soup = BeautifulSoup(response.text, 'lxml')

        content = soup.find('div', id='mw-content-text')
        if content:
            content = content.find('div', class_='mw-parser-output') or content
        else:
            content = soup

        h2_list = content.find_all('h2')
        if not h2_list:
            return

        # 第二个 h2 当作角色名
        first_h2 = h2_list[1]
        char_name = first_h2.get_text(strip=True)

        # 1、立绘
        artwork_urls = []

        # 用 lambda 在全局找 alt 里包含“立绘”的 img
        imgs = soup.find_all('img', alt=lambda v: v and char_name+'立绘' in v)

        for img in imgs:
            alt = img.get('alt', '')
            # 有些图片可能用 data-src 做懒加载
            src = img.get('data-src') or img.get('src')
            if not src:
                continue

            # 遇到 //patchwiki 开头的，补上协议
            if src.startswith('//'):
                src = 'https:' + src

            artwork_urls.append({
                "alt": alt,
                "url": src,
            })

        # 去重（按 url 去重就够了）
        uniq = {}
        for a in artwork_urls:
            uniq[a["url"]] = a
        artwork_urls = list(uniq.values())

        # 2、补充信息：只要这几个 H2 底下的表
        wanted_sections = {char_name, "其他信息", "角色故事"}

        # 找正文区域
        content = soup.find('div', id='mw-content-text')
        if content:
            content = content.find('div', class_='mw-parser-output') or content
        else:
            content = soup

        for h2 in content.find_all('h2'):
            section_title = h2.get_text(strip=True)
            if section_title not in wanted_sections:
                continue
            tables = []
            for sib in h2.next_siblings:
                if isinstance(sib, Tag):
                    if sib.name == 'h2':
                        break

                    if sib.name == 'table' and 'wikitable' in (sib.get('class') or []):
                        tables.append(sib)

                    inner_tables = sib.find_all('table', class_='wikitable')
                    tables.extend(inner_tables)
            if not tables:
                continue

            # 对这个 H2 底下的每一张 wikitable 做解析 + yield
            for tbl in tables:
                data = self.parse_wikitable(tbl)
                yield {
                    "type": "character_detail",
                    "data": {
                        "character": char_name,  # 角色名
                        "section": section_title,  # 当前 H2 名：奈芙尔 / 突破 / 角色故事 ...
                        "table": data,  # 这一块 H2 底下对应的 wikitable 解析结果
                        "artworks": artwork_urls,
                    }
                }

        # 3、语音和攻略
        map_div = soup.find('div', class_='map-dh')
        if map_div:
            for a in map_div.find_all('a', href=True):
                href = a['href']
                url = response.urljoin(href)
                if '语音' in a['title']:
                    yield Request(
                        url,
                        callback=self.parse_character_voice,
                        cb_kwargs={
                            "character": char_name,
                        },
                    )
                if '攻略' in a['title']:
                    yield Request(
                        url,
                        callback=self.parse_character_strategy,
                        cb_kwargs={
                            "character": char_name,
                        },
                    )

    @staticmethod
    def parse_character_voice(response, character, **kwargs):
        soup = BeautifulSoup(response.text, 'lxml')
        char_name = character
        root = soup.select_one('div.resp-tabs-container')
        if not root:
            return

        voice_list = []

        # 每一行是一个「display: table」的大 div
        rows = root.find_all('div', style=lambda s: s and 'display: table' in s)

        for row in rows:
            # 1) 标题：width:180px 的那个 cell 里的文本，比如「闲聊·深渊」
            title_cell = row.find(
                'div',
                style=lambda s: s and 'width:180px' in s
            )
            if not title_cell:
                continue
            title = title_cell.get_text(strip=True)

            # 2) 中文语音：正则匹配
            row_html = str(row)
            mp3_urls = re.findall(r'https?://[^"\']+\.(?:mp3|ogg)', row_html)
            cn_audio = mp3_urls[0] if len(mp3_urls) >= 1 else None

            # 3) 中文文本：voice_text_chs 里的内容
            chs_div = row.select_one('div.voice_text_chs')
            cn_text = chs_div.get_text(strip=True) if chs_div else ''

            voice_list.append({
                "title": title,  # 语音触发场景
                "cn_audio": cn_audio,
                "cn_text": cn_text,
            })

        yield {
            "type": "character_voice",
            "data": {
                "character": char_name,
                "voices": voice_list,
            }
        }

    @staticmethod
    def parse_character_strategy(response, character, **kwargs):
        soup = BeautifulSoup(response.text, 'lxml')
        char_name = character

        content = soup.find('div', id='mw-content-text')
        if content:
            content = content.find('div', class_='mw-parser-output') or content
        else:
            content = soup

        h2_list = content.find_all('h2')

        # --- 1. 角色定位 ---
        role_paragraphs = []
        start_node = None
        for h in h2_list:
            if "定位" in h.get_text():
                start_node = h
                break

        if start_node:
            for sibling in start_node.next_siblings:
                if getattr(sibling, "name", None) == "h2": break
                # 不仅找 p，也可以找 div 中的文本，或者是直接的文本节点
                if hasattr(sibling, "get_text"):
                    text = sibling.get_text(strip=True)
                    if text and len(text) > 5:  # 简单的长度过滤，避免空行
                        role_paragraphs.append(text)

        # 2. 配装推荐 -> 武器下的表格（武器 / 推荐理由）
        weapons = []
        headline = soup.find('span', class_='mw-headline', id='武器')
        if headline:
            hx = headline.find_parent(['h2', 'h3', 'h4', 'h5'])
            if hx:
                weapon_table = hx.find_next('table', class_='wikitable')
            if weapon_table:
                trs = weapon_table.find_all("tr")
                priority=0
                for tr in trs:
                    tds = tr.find_all("td")
                    if not tds:
                        continue

                    # 在 for 循环外先初始化一次
                    seen_weapon_names = set()
                    last_description = None
                    for a in tds[0].find_all("a"):
                        weapon = {}
                        weapon_name = a.get('title', '').strip()

                        # 规则1：本轮 weapon_name 之前出现过 -> 跳过
                        if weapon_name in seen_weapon_names:
                            continue
                        seen_weapon_names.add(weapon_name)

                        weapon["weapon"] = weapon_name

                        if len(tds) >= 2:
                            weapon["description"] = tds[1].get_text(" ", strip=True)
                        else:
                            weapon["description"] = ''

                        # 规则2：仅当本轮 description 和上一轮(上一次成功处理的)不同，priority 才加一
                        if last_description is None or weapon["description"] != last_description:
                            priority += 1
                        last_description = weapon["description"]

                        weapon["priority"] = priority
                        weapons.append(weapon)

        # --- 3. 阵容搭配 ---

        headline = soup.find("span", class_="mw-headline", id="阵容搭配")
        if not headline:
            headline = soup.find(
                "span",
                class_="mw-headline",
                string=lambda s: s and "阵容搭配" in s
            )
        hx = headline.find_parent(re.compile(r"^h[2-6]$"))
        root = hx.find_next(
            lambda t: isinstance(t, Tag) and t.get("id") in ("CharGuide", "CharGuide2")
        )
        if not root:
            yield {
                "type": "character_strategy",
                "data": {
                    "character": char_name,
                    "role_paragraphs": role_paragraphs,
                    "weapons": weapons,
                    "team_strategy": "",
                }
            }

        stop = root.select_one("table.wikitable.TeamGuide")
        lines = []
        for node in root.descendants:
            # 到达 table 就停止（不包含 table）
            if node is stop:
                break

            if isinstance(node, Tag) and node.name in BLOCK_TAGS:
                text = node.get_text(" ", strip=True)
                if not text:
                    continue

                # 轻微格式化：列表加个前缀，更像“文本内容”
                if node.name == "li":
                    text = f"- {text}"

                lines.append(text)

        # 去掉连续重复（避免某些嵌套结构造成的重复行）
        out = []
        prev = None
        for t in lines:
            t = t.replace("\xa0", " ").strip()  # 处理 &nbsp; 之类
            if t and t != prev:
                out.append(t)
                prev = t

        try:
            yield {
                "type": "character_strategy",
                "data": {
                    "character": char_name,
                    "role_paragraphs": role_paragraphs,
                    "weapons": weapons,
                    "team_strategy": "\n".join(out),
                }
            }
        except Exception as e:
            # 至少把错误和角色名打出来，避免被上层吞掉
            print(f"[parse fail] {character} url={getattr(response, 'url', None)} err={repr(e)}")

    @staticmethod
    def parse_weapon(response, **kwargs):
        soup = BeautifulSoup(response.text, 'lxml')
        # 表格解析
        tbl = soup.find('table', id='CardSelectTr')
        if tbl:
            ths = tbl.find_all('tr')[0].find_all('th')
            for row in tbl.find_all('tr')[1:]:
                weapon = {}
                tds =  row.find_all('td')
                for i, (k, v) in enumerate(zip(ths, tds)):
                    key = k.get_text(strip=True)
                    if i == 0:
                        # 第一个 td：抓取图标链接
                        img = v.find('img')
                        if img and img.has_attr('src'):
                            weapon[key] = img['src']
                    else:
                        # 后续 td 内容仍然是文本
                        weapon[key] = v.get_text(strip=True)
                yield {'type': 'weapon', 'data': weapon}

    def parse_artifact(self, response, **kwargs):
        soup = BeautifulSoup(response.text, 'lxml')
        tbl = soup.find('table', id='CardSelectTr')
        if tbl:
            ths = tbl.find_all('tr')[0].find_all('th')
            for row in tbl.find_all('tr')[1:]:
                artifact = {}
                tds =  row.find_all('td')
                for i, (k, v) in enumerate(zip(ths, tds)):
                    key = k.get_text(strip=True)
                    if i == 0:
                        img = v.find('img')
                        if img and img.has_attr('src'):
                            artifact[key] = img['src']
                    else:
                        artifact[key] = v.get_text(strip=True)
                link = tds[1].find('a') or tds[0].find('a')
                if link and link.get('href'):
                    yield Request(response.urljoin(link['href']), callback=self.parse_artifact_detail,
                                  cb_kwargs={'base_data': artifact})
                else:
                    yield {'type': 'artifact', 'data': artifact}

    @staticmethod
    def parse_artifact_detail(response, base_data, **kwargs):
        soup = BeautifulSoup(response.text, "lxml")
        artifact = dict(base_data)

        base_url = kwargs.get("base_url") or response.url  # 用于补全相对链接

        recommended_block = soup.select_one("div.recommended")
        rec_list = []

        if recommended_block:
            # 每一条推荐（可能有多条）
            for rec in recommended_block.select("div.rolerec"):
                # 1) 推荐角色列表
                roles = []
                for roleicon in rec.select("div.icon div.roleicon"):
                    # 攻略链接（最后那个 a 通常是 /攻略）
                    guide_a = roleicon.select_one('a[title$="/攻略"]')

                    # 角色名：优先 .L，其次用攻略 a 的文字
                    name_el = roleicon.select_one(".L")
                    name = name_el.get_text(strip=True) if name_el else None
                    if not name and guide_a:
                        name = guide_a.get_text(strip=True)

                    # 兜底：如果都没拿到，跳过
                    if not name:
                        continue

                    roles.append(name)

                # 2) 推荐说明
                desc_el = rec.select_one("div.main div.item")
                desc_text = desc_el.get_text(" ", strip=True) if desc_el else ""

                # 3) 仅当这一条确实解析到角色或说明时才记录
                if roles or desc_text:
                    rec_list.append({
                        "roles": roles,
                        "desc": desc_text,
                    })

        # 写回 artifact
        artifact["recommended_roles"] = rec_list

        yield {"type": "artifact", "data": artifact}


    def parse_material(self, response, offset, **kwargs):
        soup = BeautifulSoup(json.loads(response.text)['parse']['text']['*'], 'lxml')
        rows = soup.select('table.wikitable tr')

        for row in rows[1:]:
            tds = row.find_all('td')
            if len(tds) < 6: continue
            img = tds[0].find('img')
            yield {
                'type': 'material',
                'data': {
                    'icon': img.get('data-src') or img.get('src') if img else '',
                    'name': tds[1].get_text(strip=True),
                    'rarity': tds[2].get_text(strip=True),
                    'type': tds[3].get_text(strip=True),
                    'source': tds[4].get_text(" ", strip=True),
                    'usage': tds[5].get_text(" ", strip=True),
                }
            }

        if len(rows) > 1:
            yield self._build_api_request(self.MATERIAL_API_URL, offset + 50, self.parse_material)

    def parse_monster(self, response, offset, **kwargs):
        soup = BeautifulSoup(json.loads(response.text)['parse']['text']['*'], 'lxml')
        table = soup.find('table', class_='wikitable')
        if not table: return

        rows = table.find_all('tr')

        for row in rows[1:]:
            tds = row.find_all('td')
            if len(tds) < 8: continue

            icon_img = tds[0].find('img')
            drop_items = []
            for a in tds[7].find_all('a'):
                name = a.get('title', '').strip()
                if name: drop_items.append({'名称': name, '链接': response.urljoin(a.get('href', ''))})

            monster = {
                'icon': icon_img.get('data-src') or icon_img.get('src') if icon_img else '',
                'name': tds[1].get_text(strip=True),
                'element': tds[2].get_text(strip=True),
                'type': tds[3].get_text(strip=True),
                'refresh time': tds[4].get_text(strip=True),
                'location': tds[5].get_text(strip=True),
                'TAG': tds[6].get_text(' ', strip=True),
                'drop': [d['名称'] for d in drop_items]
            }

            link = tds[1].find('a') or tds[0].find('a')
            if link and link.get('href'):
                yield Request(response.urljoin(link['href']), callback=self.parse_monster_detail,
                              cb_kwargs={'base_data': monster})
            else:
                yield {'type': 'monster', 'data': monster}

        if len(rows) > 1:
            yield self._build_api_request(self.MONSTER_API_URL, offset + 50, self.parse_monster)

    @staticmethod
    def parse_monster_detail(response, base_data, **kwargs):
        soup = BeautifulSoup(response.text, 'lxml')
        monster = dict(base_data)
        # 补充推荐角色
        headline = soup.find('span', class_='mw-headline', id=lambda x: x in ['挑战推荐角色', '相关攻略'])
        monster['recommend'] = []
        monster['info'] = ''
        if headline:
            hx = headline.find_parent(['h2', 'h3'])
            table = hx.find_next('table', class_='wikitable')
            p = hx.find_next('p').get_text(separator=' ', strip=True)
            monster['info'] = p if p!="游戏中心 | 帐号安全 | 找回密码 | 家长监控 | 用户协议" else ''
            if table:
                trs = table.find_all('tr')
                recommend = []
                for tr in trs[1:]:
                    cells = tr.find_all(['th','td']) # 兼容<th><td>和<td><td>两种格式
                    if len(cells) < 1:
                        continue
                    else:
                        txt = ''
                        for cell in cells:
                            txt += cell.get_text(' ', strip=True)
                        recommend.append(txt)
                monster['recommend'] = recommend
        yield {'type': 'monster', 'data': monster}
