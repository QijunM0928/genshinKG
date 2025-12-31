"""
RAG 测试与评估脚本

用法示例：
python scripts/eval_rag.py --testset tests\generated_testset_artifact_qs.jsonl --out report.json

需要环境变量：
NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
OPENAI_API_KEY (可选：OPENAI_API_BASE, OPENAI_MODEL_ID)

该脚本会：
- 连接 Neo4j
- 初始化 QA 系统（绕过 Streamlit 的自动初始化）
- 对每个问题调用 `qa.ask(question)` 获取生成答案
- 计算若干文本相似性指标（exact match, LCS-based ROUGE-L, difflib ratio）
- 输出 JSON 报告和 CSV 汇总
"""
import os
import sys
import json
import argparse
from typing import List, Dict
from datetime import datetime
from openai import OpenAI
import time
import statistics
try:
    import psutil
except Exception:
    psutil = None

# 将项目根目录加入路径
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT)

from neo4j_connector import GenshinKnowledgeGraph
from modules.qa_panel import KGQA_System

import streamlit as st
import difflib


def read_jsonl(path: str) -> List[Dict]:
    data = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data.append(json.loads(line))
    return data


def lcs_len(a: str, b: str) -> int:
    # 动态规划求最长公共子序列长度
    if not a or not b:
        return 0
    m, n = len(a), len(b)
    dp = [0] * (n + 1)
    for i in range(1, m + 1):
        prev = 0
        ai = a[i - 1]
        for j in range(1, n + 1):
            temp = dp[j]
            if ai == b[j - 1]:
                dp[j] = prev + 1
            else:
                dp[j] = max(dp[j], dp[j - 1])
            prev = temp
    return dp[n]


def rouge_l_score(pred: str, ref: str):
    l = lcs_len(pred, ref)
    if l == 0:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    p = l / max(1, len(pred))
    r = l / max(1, len(ref))
    f1 = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0
    return {"precision": p, "recall": r, "f1": f1}


def normalize_text(s: str) -> str:
    return (s or "").strip()


def flatten_query_results(results) -> (str, list):
    """把查询结果（可能是 list[dict] 或其它）拼成文本块，并返回每个片段的文本列表。"""
    snippets = []
    if results is None:
        return "", []
    if isinstance(results, str):
        return results, [results]
    if isinstance(results, dict):
        # 将 dict 的字符串值合并
        vals = []
        for v in results.values():
            if isinstance(v, str):
                vals.append(v)
        text = "\n".join(vals)
        return text, [text] if text else []
    if isinstance(results, (list, tuple)):
        for item in results:
            if isinstance(item, str):
                snippets.append(item)
            elif isinstance(item, dict):
                vals = [str(v) for v in item.values() if isinstance(v, (str, int, float))]
                joined = " ".join(vals).strip()
                if joined:
                    snippets.append(joined)
            else:
                try:
                    snippets.append(str(item))
                except Exception:
                    continue
    text = "\n".join(snippets)
    return text, snippets


def normalize_cypher_obj(cypher_obj):
    """从可能的 cypher 返回值中提取 (query_str, params)"""
    if cypher_obj is None:
        return None, None
    # 直接字符串
    if isinstance(cypher_obj, str):
        return cypher_obj, None
    # 列表或元组，常见形式 [query, params, ...]
    if isinstance(cypher_obj, (list, tuple)) and len(cypher_obj) > 0:
        q = cypher_obj[0]
        p = None
        if len(cypher_obj) > 1 and isinstance(cypher_obj[1], dict):
            p = cypher_obj[1]
        if isinstance(q, str):
            return q, p
        # 如果第一个元素也是复杂结构，尝试字符串化
        try:
            return str(q), p
        except Exception:
            return None, None
    # dict 可能包含 query 或 cypher 字段
    if isinstance(cypher_obj, dict):
        if 'query' in cypher_obj and isinstance(cypher_obj['query'], str):
            return cypher_obj['query'], cypher_obj.get('params') or None
        # 尝试直接转换为字符串
        try:
            return str(cypher_obj), None
        except Exception:
            return None, None
    # 兜底
    try:
        return str(cypher_obj), None
    except Exception:
        return None, None


def token_overlap_ratio(pred: str, ref: str) -> float:
    pa = [t for t in (pred or "").lower().split() if t]
    rb = [t for t in (ref or "").lower().split() if t]
    if not rb:
        return 0.0
    common = sum(1 for t in rb if t in pa)
    return common / max(1, len(rb))


def proportion_out_of_retrieval(pred: str, retrieved: str) -> float:
    # 预测中有多少 token 没在检索文本中出现（用于检测幻觉）
    pset = set([t for t in (pred or "").lower().split() if t])
    rset = set([t for t in (retrieved or "").lower().split() if t])
    if not pset:
        return 0.0
    out = sum(1 for t in pset if t not in rset)
    return out / len(pset)


def avg_sentence_length(text: str) -> float:
    if not text:
        return 0.0
    import re
    sents = [s.strip() for s in re.split(r'[。！？.!?]\s*', text) if s.strip()]
    if not sents:
        return 0.0
    words = sum(len(s.split()) for s in sents)
    return words / len(sents)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--testset', required=True, help='JSONL 文件，每行: {"id":.., "question":.., "answer":..}')
    parser.add_argument('--out', default='report.json', help='输出 JSON 报告路径')
    args = parser.parse_args()

    # 从环境变量读取连接与 LLM 配置
    neo4j_uri = os.environ.get('NEO4J_URI')
    neo4j_user = os.environ.get('NEO4J_USER')
    neo4j_password = os.environ.get('NEO4J_PASSWORD')
    openai_key = os.environ.get('OPENAI_API_KEY')
    openai_base = os.environ.get('OPENAI_API_BASE')
    openai_model = os.environ.get('OPENAI_MODEL_ID', 'gpt-3.5-turbo')

    if not (neo4j_uri and neo4j_user and neo4j_password):
        print('请先设置环境变量 NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD')
        sys.exit(1)

    if not openai_key:
        print('警告：未检测到 OPENAI_API_KEY，LLM 可能无法工作（仅当问题走规则化路径时可继续）')

    print('连接 Neo4j...')
    kg = GenshinKnowledgeGraph()
    ok = kg.connect(neo4j_uri, neo4j_user, neo4j_password)
    if not ok:
        print('无法连接 Neo4j')
        sys.exit(1)

    # 绕过 KGQA_System 在构造时尝试使用 Streamlit 初始化 LLM 的动作
    KGQA_System._init_llm_client = lambda self: None
    st.session_state.clear()

    qa = KGQA_System(kg)
    # 手动注入 OpenAI 客户端
    if openai_key:
        try:
            qa.client = OpenAI(api_key=openai_key, base_url=openai_base) if openai_base else OpenAI(api_key=openai_key)
            qa.model_id = openai_model
            print('已设置 OpenAI 客户端')
        except Exception as e:
            print('设置 OpenAI 客户端失败：', e)

    # 读入测试集
    test_items = read_jsonl(args.testset)
    results = []
    # 记录运行时资源概览
    proc = psutil.Process() if psutil else None
    cpu_samples = []
    mem_samples = []

    for item in test_items:
        qid = item.get('id') or item.get('qid') or None
        question = item.get('question')
        reference = item.get('answer') or item.get('ground_truth') or ""
        print(f'[{qid}] 提问：{question}')

        # 优先使用 KGQA_System 的分阶段方法以获得检索结果和各阶段延迟
        start_e2e = time.perf_counter()
        try:
            if hasattr(qa, 'generate_cypher') and hasattr(qa, 'execute_query') and hasattr(qa, 'generate_answer'):
                cypher = qa.generate_cypher(question)
                # 兼容 generate_cypher 可能返回的不同结构
                qstr, qparams = normalize_cypher_obj(cypher)
                t0 = time.perf_counter()
                try:
                    if qstr:
                        query_results = qa.execute_query(qstr, qparams) if qparams is not None else qa.execute_query(qstr)
                    else:
                        query_results = qa.execute_query(cypher)
                except Exception as e:
                    # 如果直接执行失败，尝试把 cypher 当作字符串执行
                    try:
                        query_results = qa.execute_query(str(cypher))
                    except Exception:
                        raise
                t1 = time.perf_counter()
                retrieval_latency_ms = (t1 - t0) * 1000.0

                t2 = time.perf_counter()
                # generate_answer may accept (question, cypher, query_results) or just (question, query_results)
                try:
                    answer = qa.generate_answer(question, cypher, query_results)
                except TypeError:
                    try:
                        answer = qa.generate_answer(question, query_results)
                    except TypeError:
                        # fallback to ask
                        t_ask0 = time.perf_counter()
                        cypher2, query_results2, answer = qa.ask(question)
                        t_ask1 = time.perf_counter()
                        retrieval_latency_ms = None
                        generation_latency_ms = (t_ask1 - t_ask0) * 1000.0
                        end_e2e = time.perf_counter()
                        end_to_end_ms = (end_e2e - start_e2e) * 1000.0
                        query_results = query_results2
                        cypher = cypher2
                        # continue to postprocessing
                        raise StopIteration
                t3 = time.perf_counter()
                generation_latency_ms = (t3 - t2) * 1000.0
            else:
                # 如果没有分阶段接口，退回到 ask()
                t_ask0 = time.perf_counter()
                cypher, query_results, answer = qa.ask(question)
                t_ask1 = time.perf_counter()
                retrieval_latency_ms = None
                generation_latency_ms = (t_ask1 - t_ask0) * 1000.0

            end_e2e = time.perf_counter()
            end_to_end_ms = (end_e2e - start_e2e) * 1000.0
        except StopIteration:
            # 当内部 fallback 已经设置了变量时，捕获并继续
            end_to_end_ms = end_to_end_ms if 'end_to_end_ms' in locals() else None
            retrieval_latency_ms = retrieval_latency_ms if 'retrieval_latency_ms' in locals() else None
            generation_latency_ms = generation_latency_ms if 'generation_latency_ms' in locals() else None
        except Exception as e:
            print('调用 QA 失败：', e)
            cypher = None
            query_results = None
            answer = ""
            retrieval_latency_ms = None
            generation_latency_ms = None
            end_to_end_ms = None

        # 若检索失败或返回空结果，尝试领域特定的直接 DB 回退
        if (not query_results) or (isinstance(query_results, (list, tuple)) and len(query_results) == 0):
            # 简单识别：武器/圣遗物/角色 查询意图
            try:
                qlow = (question or '').lower()
                # 提取名称：优先从 id 中解析，再尝试从问题文本中提取书名号/引号里的名称
                name = None
                if qid and isinstance(qid, str):
                    if qid.startswith('wp_') or qid.startswith('art_') or qid.startswith('char_'):
                        name = qid.split('_', 1)[1]
                if not name:
                    import re
                    m = re.search(r'["“「]?([^"”»»」]+?)["”»»」]?', question or '')
                    if m:
                        name = m.group(1)
                if name:
                    name = name.strip()
                # 武器适配
                if ('适合' in qlow or '适用' in qlow) and ('武器' in qlow or (qid and isinstance(qid, str) and qid.startswith('wp_'))):
                    nm = name or ''
                    chars = kg.get_weapon_characters(nm)
                    if chars:
                        names = [c.get('name') for c in chars if c.get('name')]
                        answer = '适合的角色：' + '、'.join(names)
                        query_results = chars
                # 圣遗物适配
                if (('适合' in qlow or '适用' in qlow) and ('圣遗物' in qlow or (qid and isinstance(qid, str) and qid.startswith('art_')))):
                    nm = name or ''
                    chars = kg.get_artifact_characters(nm)
                    if chars:
                        names = [c.get('name') for c in chars if c.get('name')]
                        answer = '适合的角色：' + '、'.join(names)
                        query_results = chars
                # 角色详情回退
                if (('详细' in qlow or '信息' in qlow) and ('角色' in qlow or (qid and isinstance(qid, str) and qid.startswith('char_')))):
                    nm = name or ''
                    info = kg.get_character_basic_info(nm)
                    if info:
                        # 将字典转为简短描述
                        parts = []
                        if info.get('element'):
                            parts.append('元素: ' + str(info.get('element')))
                        if info.get('weapon_type'):
                            parts.append('武器类型: ' + str(info.get('weapon_type')))
                        if info.get('country'):
                            parts.append('国家: ' + str(info.get('country')))
                        desc = '、'.join(parts)
                        answer = f"{info.get('name')} 的信息：{desc}。"
                        query_results = info
            except Exception:
                pass

        pred = normalize_text(answer or "")
        ref = normalize_text(reference or "")

        # 提取检索文本与片段
        retrieved_text, snippets = flatten_query_results(query_results)

        # 检索指标（近似可测）
        retrieval_relevance = difflib.SequenceMatcher(None, retrieved_text, ref).ratio() if ref else 0.0
        retrieval_precision = 0.0
        if snippets:
            good = 0
            for s in snippets:
                if difflib.SequenceMatcher(None, s, ref).ratio() >= 0.5:
                    good += 1
            retrieval_precision = good / max(1, len(snippets))
        retrieval_recall = token_overlap_ratio(retrieved_text, ref) if ref else 0.0

        # 生成质量指标
        exact = 1 if pred == ref and ref != "" else 0
        seq_ratio = difflib.SequenceMatcher(None, pred, ref).ratio()
        rouge = rouge_l_score(pred, ref)
        # 幻觉比例（预测中不在检索内容的 token 比例）
        hallucination_fraction = proportion_out_of_retrieval(pred, retrieved_text)

        # 系统性能（ms）
        rec_perf = {
            'retrieval_latency_ms': retrieval_latency_ms,
            'generation_latency_ms': generation_latency_ms,
            'end_to_end_ms': end_to_end_ms,
        }

        # 用户体验近似指标
        readability_avg_sent_len = avg_sentence_length(pred)
        answer_completeness = token_overlap_ratio(pred, ref) if ref else 0.0
        # 用户满意度代理：综合相似度、可读性和低幻觉率
        user_satisfaction_proxy = float((seq_ratio + (1 - min(1.0, readability_avg_sent_len / 30.0)) + (1 - hallucination_fraction)) / 3.0)

        rec = {
            'id': qid,
            'question': question,
            'reference': ref,
            'prediction': pred,
            'cypher': cypher,
            'retrieved_text': retrieved_text,
            # Retrieval
            'retrieval_relevance': retrieval_relevance,
            'retrieval_precision': retrieval_precision,
            'retrieval_recall': retrieval_recall,
            # Generation
            'exact_match': exact,
            'seq_ratio': seq_ratio,
            'rouge_l': rouge,
            'hallucination_fraction': hallucination_fraction,
            # Performance
            **rec_perf,
            # UX
            'readability_avg_sentence_len': readability_avg_sent_len,
            'answer_completeness': answer_completeness,
            'user_satisfaction_proxy': user_satisfaction_proxy,
        }
        results.append(rec)

        # 采样资源使用
        if proc:
            try:
                cpu_samples.append(proc.cpu_percent(interval=0.01))
                mem_samples.append(proc.memory_info().rss)
            except Exception:
                pass

    meta = {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'count': len(results)
    }

    out_obj = {'meta': meta, 'results': results}
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out_obj, f, ensure_ascii=False, indent=2)

    print(f'评估完成，已写入 {args.out}')


if __name__ == '__main__':
    main()
