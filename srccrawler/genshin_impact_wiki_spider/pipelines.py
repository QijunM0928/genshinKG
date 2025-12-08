import os
import shutil
import json
import datetime
# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter


class GenshinImpactWikiSpiderPipeline:
    def __init__(self):
        self.data_root = 'data'
        if os.path.exists(self.data_root):
            shutil.rmtree(self.data_root)
        os.makedirs(self.data_root)

    def process_item(self, item, spider):
        file_path = os.path.join(self.data_root, item['type'] + '.json')
        data = item['data']
        f = open(file_path, 'a', encoding = 'utf-8')
        f.write(json.dumps(data, ensure_ascii = False) + '\n')
        f.close()
        return item

class GenshinImpactTimestampJsonPipeline:
    def __init__(self):
        # 输出目录：data
        self.data_root = 'data'
        # 不清空旧数据，只是保证目录存在
        os.makedirs(self.data_root, exist_ok=True)

        # 缓存本次爬取的所有数据，按类型分类
        # 结构类似：{'character': [ {...}, {...} ], 'weapon': [...], 'material': [...]}
        self.buffers = {}

        # 记录本次运行的时间戳，用来给文件命名
        # 例如：20251205_143210
        self.run_ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

    def process_item(self, item, spider):
        # item 结构：{'type': 'character', 'data': {...}}
        t = item.get('type', 'unknown')
        data = item.get('data', {})

        # 按类型把数据放到对应的列表里
        self.buffers.setdefault(t, [])
        self.buffers[t].append(data)
        # print("==== ITEM ====")
        # print(json.dumps(item['data'], ensure_ascii=False, indent=2))
        # print("==============")
        return item

    def close_spider(self, spider):
        # 爬虫结束时，一次性把所有缓存写入文件
        for t, data_list in self.buffers.items():
            if not data_list:
                continue

            # 文件名： character_20251205_143210.json / weapon_20251205_143210.json ...
            filename = f'{t}_{self.run_ts}.json'
            file_path = os.path.join(self.data_root, filename)

            # 标准 JSON 数组写入
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data_list, f, ensure_ascii=False, indent=2)
