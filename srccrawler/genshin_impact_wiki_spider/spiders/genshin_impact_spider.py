import json
import scrapy
import re
from bs4 import BeautifulSoup, Tag
from scrapy.spiders import Spider
from scrapy.http import Request
from scrapy.linkextractors import LinkExtractor


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

        # 辅助函数：模糊查找列索引
        def get_index(headers, keywords):
            for idx, h in enumerate(headers):
                if any(k in h for k in keywords):
                    return idx
            return None

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
        weapons = {}
        headline = soup.find('span', class_='mw-headline', id='武器')
        if headline:
            hx = headline.find_parent('h4')
            weapon_table = hx.find_next('table', class_='wikitable')
            if weapon_table:
                trs = weapon_table.find_all("tr")
                for tr in trs:
                    tds = tr.find_all("td")
                    if not tds:
                        continue
                    for a in tds[0].find_all("a"):
                        weapon_name = a.get('title', '').strip()
                        weapons[weapon_name] = tds[1].get_text(" ", strip=True)

        # --- 3. 阵容搭配 ---
        lineups = []
        lineup_h2 = None
        for h in h2_list:
            if "阵容" in h.get_text():
                lineup_h2 = h
                break

        if lineup_h2:
            # 收集该区块下的所有 table，不论是否在 tabbertab 里
            tables_found = []

            # 遍历兄弟节点直到下一个 h2
            current = lineup_h2.next_sibling
            while current:
                if getattr(current, "name", None) == "h2":
                    break

                if isinstance(current, Tag):
                    # 检查自身是不是 table
                    if current.name == 'table':
                        tables_found.append((None, current))  # (Tab Title, Table Element)

                    # 检查内部有没有 tabbertab
                    tabbers = current.find_all("div", class_="tabbertab")
                    if tabbers:
                        for tab in tabbers:
                            title = tab.get("title", "默认")
                            tbl = tab.find("table", class_="wikitable")
                            if tbl: tables_found.append((title, tbl))

                    # 检查内部有没有普通 table (非 tabber 情况)
                    elif not tabbers:
                        inner_tbls = current.find_all("table", class_="wikitable")
                        for tbl in inner_tbls:
                            tables_found.append(("通用", tbl))

                current = current.next_sibling

            # 解析找到的所有表格
            for tab_title, table in tables_found:
                # 解析表头
                header_cells = table.select("tr th") or table.select("thead th")
                headers = [th.get_text(strip=True) for th in header_cells]

                # 使用模糊匹配查找列
                # 只要找到 "角色" 这一列，我们就认为这是个阵容表
                role_idx = get_index(headers, ["角色", "队友"])
                if role_idx is None:
                    continue  # 不是阵容表，跳过

                panel_idx = get_index(headers, ["面板", "属性"])
                arti_idx = get_index(headers, ["圣遗物", "套装"])
                # 低星武器是可选的，不强求
                low_weap_idx = get_index(headers, ["低星", "过渡", "替代"])

                rows = table.find_all("tr")
                # 跳过表头行 (通常是第一行，也可能是前两行，这里简单处理)
                data_rows = [r for r in rows if not r.find('th')]

                tab_rows = []
                for tr in data_rows:
                    cells = tr.find_all("td")
                    if not cells: continue

                    # 安全获取数据的 helper
                    def get_cell_text(idx):
                        if idx is not None and idx < len(cells):
                            return cells[idx].get_text(" ", strip=True)
                        return ""

                    role_name = get_cell_text(role_idx)
                    if not role_name: continue  # 没有角色名的行跳过

                    tab_rows.append({
                        "role": role_name,
                        "panel": get_cell_text(panel_idx),
                        "artifacts": get_cell_text(arti_idx),
                        "low_star_weapons": get_cell_text(low_weap_idx),
                    })

                if tab_rows:
                    lineups.append({
                        "tab_title": tab_title,
                        "rows": tab_rows
                    })

        yield {
            "type": "character_strategy",
            "data": {
                "character": char_name,
                "role_paragraphs": role_paragraphs,
                "weapons": weapons,
                "lineups": lineups,
            }
        }

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
