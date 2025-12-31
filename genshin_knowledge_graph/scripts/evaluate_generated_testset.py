"""evaluate_generated_testset.py — 生成测试集覆盖率评估脚本

用途:
- 统计生成的 JSONL 测试集中若干结构化字段的覆盖率（main_stat, substats, rarity, set_effects, recommended_characters）。
- 抽取示例条目到样本文件，输出覆盖率摘要到 JSON。

用法:
        python scripts/evaluate_generated_testset.py --in tests/generated_testset_artifact_qs.jsonl --out-summary tests/eval_summary.json --out-samples tests/eval_samples.jsonl

参数:
    --in           输入 JSONL 文件（默认: tests/generated_testset_artifact_qs.jsonl）
    --out-summary  输出覆盖率摘要 JSON（默认: tests/eval_summary.json）
    --out-samples  输出示例 JSONL（默认: tests/eval_samples.jsonl）

输出:
- `out_summary`（JSON）包含字段覆盖统计与样本计数。
- `out_samples`（JSONL）包含示例条目（带/不带推荐角色）。

注意:
- 本脚本仅分析文件内容，不修改原文件。
"""

import json
from collections import Counter, defaultdict
from random import sample, seed
import sys
import argparse

seed(1)

parser = argparse.ArgumentParser(description='Evaluate generated artifact testset coverage')
parser.add_argument('--in', dest='infile', default='tests/generated_testset_artifact_qs.jsonl', help='input jsonl file')
parser.add_argument('--out-summary', dest='out_summary', default='tests/eval_summary.json', help='output summary json')
parser.add_argument('--out-samples', dest='out_samples', default='tests/eval_samples.jsonl', help='output samples jsonl')
args = parser.parse_args()

IN = args.infile
OUT_SUM = args.out_summary
OUT_SAMPLES = args.out_samples

FIELD_CANDIDATES = {
    'main_stat': ['main_stat', 'mainStat', '主词条'],
    'substats': ['possible_substats', 'sub_stats', 'substats', 'possible_substat_pool', '副词条'],
    'rarity': ['rarity', 'star', '稀有度'],
    'set_effects': ['set_effects', 'setEffect', 'set_description', '套装效果', 'description'],
    'recommended_characters': ['recommended_characters', 'recommended', 'suitable_characters', 'recommended_characters_list', 'suitable']
}

def find_field(obj, keys):
    # search top-level and nested 'artifact' or 'node' dicts
    if not isinstance(obj, dict):
        return None
    for k in keys:
        if k in obj and obj[k] not in (None, '', []):
            return obj[k]
    for nest in ('artifact', 'node', 'properties', 'data'):
        if nest in obj and isinstance(obj[nest], dict):
            for k in keys:
                if k in obj[nest] and obj[nest][k] not in (None, '', []):
                    return obj[nest][k]
    return None


total = 0
present = Counter()
examples_with = defaultdict(list)
all_examples = []

with open(IN, encoding='utf-8') as f:
    for line in f:
        line=line.strip()
        if not line:
            continue
        total += 1
        try:
            obj = json.loads(line)
        except Exception:
            continue
        all_examples.append(obj)
        for field, keys in FIELD_CANDIDATES.items():
            val = find_field(obj, keys)
            if val is not None:
                present[field] += 1
                if len(examples_with[field]) < 200:
                    examples_with[field].append({'index': total-1, 'value': val, 'example': obj})

summary = {
    'input_file': IN,
    'total_examples': total,
    'field_counts': {},
}

for field in FIELD_CANDIDATES:
    cnt = present.get(field, 0)
    summary['field_counts'][field] = {
        'present': cnt,
        'missing': total - cnt,
        'coverage_pct': round(100.0 * cnt / total, 2) if total else 0.0
    }

# sample up to 10 examples that have recommended_characters, and 10 that don't
have_rec = examples_with.get('recommended_characters', [])
with_rec = []
without_rec = []
for i,obj in enumerate(all_examples):
    val = find_field(obj, FIELD_CANDIDATES['recommended_characters'])
    if val is not None:
        if len(with_rec) < 10:
            with_rec.append({'index': i, 'recommended': val, 'example': obj})
    else:
        if len(without_rec) < 10:
            without_rec.append({'index': i, 'recommended': None, 'example': obj})

summary['samples'] = {
    'with_recommended_count': len(with_rec),
    'without_recommended_count': len(without_rec)
}

with open(OUT_SUM, 'w', encoding='utf-8') as fo:
    json.dump(summary, fo, ensure_ascii=False, indent=2)

with open(OUT_SAMPLES, 'w', encoding='utf-8') as fo:
    for item in with_rec + without_rec:
        fo.write(json.dumps(item, ensure_ascii=False) + '\n')

print('WROTE', OUT_SUM, 'and', OUT_SAMPLES)
print('SUMMARY:', json.dumps(summary, ensure_ascii=False))

sys.exit(0)
