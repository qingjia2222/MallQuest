import math
import re
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "data" / "knowledge"
NO_EVIDENCE = "本商城暂未提供这项规则或服务说明。"
META_KEYS = {"mall_id", "doc_id", "topic", "version", "updated_at", "authority", "maintainer", "tags"}
NORMALIZATIONS = {
    "厕所": "卫生间", "洗手间": "卫生间", "洗手池": "卫生间",
    "改期": "修改预约时间", "改时间": "修改预约时间", "改人数": "修改预约人数",
    "订位": "预约", "预订": "预约", "代金券": "优惠券", "券": "优惠券",
    "车位": "停车空位", "几点关门": "营业时间", "几点开门": "营业时间",
}
KEY_TERMS = (
    "有效期", "过期", "生日", "兑换", "等级", "权益", "注册", "领取", "门槛", "叠加", "退款",
    "返还", "改期", "修改时间", "修改人数", "取消", "迟到", "留位", "收费", "计费", "减免",
    "空位", "入场", "离场", "缴费", "服务台", "失物招领", "卫生间", "母婴室", "无障碍",
    "消防", "安保", "急救", "营业时间", "跨楼层", "电梯", "扶梯", "有线电视",
)

_cache_signature = None
_cache_documents = []


def _normalize(text: str):
    normalized = text.lower().strip()
    for source, target in NORMALIZATIONS.items():
        normalized = normalized.replace(source, target)
    return normalized


def _tokens(text: str):
    lowered = _normalize(text)
    tokens = set(re.findall(r"[a-z0-9]+", lowered))
    for run in re.findall(r"[\u4e00-\u9fff]+", lowered):
        if len(run) == 1:
            tokens.add(run)
        else:
            tokens.update(run[index:index + 2] for index in range(len(run) - 1))
    return tokens


def _parse_document(path: Path):
    text = path.read_text(encoding="utf-8")
    metadata = {"doc": path.name, "title": path.stem, "topic": "general", "version": "1.0"}
    chunks = []
    section = "正文"
    body = []

    def flush():
        snippet = "\n".join(body).strip()
        if snippet:
            chunks.append({**metadata, "section": section, "snippet": snippet})
        body.clear()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            flush()
            section = heading.group(2).strip()
            if len(heading.group(1)) == 1:
                metadata["title"] = section
            continue
        meta = re.match(r"^([a-z_]+):\s*(.+)$", line, re.I)
        if meta and meta.group(1).lower() in META_KEYS:
            metadata[meta.group(1).lower()] = meta.group(2).strip()
            continue
        if line:
            body.append(line)
        elif body:
            flush()
    flush()
    return metadata, chunks


def _signature():
    return tuple((path.name, path.stat().st_mtime_ns, path.stat().st_size) for path in sorted(KNOWLEDGE_DIR.glob("*.md")))


def _documents():
    global _cache_signature, _cache_documents
    signature = _signature()
    if signature != _cache_signature:
        loaded = []
        for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
            metadata, chunks = _parse_document(path)
            loaded.append({"metadata": metadata, "chunks": chunks})
        _cache_documents = loaded
        _cache_signature = signature
    return _cache_documents


def reload_index():
    global _cache_signature
    _cache_signature = None
    return knowledge_status()


def knowledge_status(mall_id: str | None = None):
    documents = [item for item in _documents() if not mall_id or item["metadata"].get("mall_id") == mall_id]
    return {
        "documents": len(documents),
        "chunks": sum(len(item["chunks"]) for item in documents),
        "topics": sorted({item["metadata"].get("topic", "general") for item in documents}),
    }


def retrieve(query: str, mall_id: str, limit: int = 3, topic: str | None = None, min_score: float = 0.16):
    query_text = _normalize(query)
    query_tokens = _tokens(query_text)
    if not query_tokens:
        return []
    scored = []
    for document in _documents():
        metadata = document["metadata"]
        if metadata.get("mall_id") != mall_id:
            continue
        if topic and metadata.get("topic") != topic:
            continue
        for chunk in document["chunks"]:
            searchable = " ".join((chunk.get("title", ""), chunk.get("section", ""), chunk.get("snippet", "")))
            chunk_tokens = _tokens(searchable)
            overlap = query_tokens & chunk_tokens
            if not overlap:
                continue
            score = len(overlap) / math.sqrt(max(1, len(query_tokens) * len(chunk_tokens)))
            score += 0.12 * len(query_tokens & _tokens(chunk.get("section", "")))
            normalized_searchable = _normalize(searchable)
            score += 0.45 * sum(1 for term in KEY_TERMS if term in query_text and term in normalized_searchable)
            if topic and metadata.get("topic") == topic:
                score += 0.2
            if query_text and query_text in normalized_searchable:
                score += 0.35
            if score >= min_score:
                scored.append({
                    "doc": chunk["doc"], "doc_id": chunk.get("doc_id", Path(chunk["doc"]).stem),
                    "title": chunk.get("title", Path(chunk["doc"]).stem), "topic": chunk.get("topic", "general"),
                    "section": chunk["section"], "snippet": chunk["snippet"], "version": chunk.get("version", "1.0"),
                    "updated_at": chunk.get("updated_at"), "authority": chunk.get("authority"), "score": round(score, 3),
                })
    scored.sort(key=lambda item: (-item["score"], item["doc"], item["section"]))
    return scored[:limit]


def answer(query: str, mall_id: str, topic: str | None = None):
    sources = retrieve(query, mall_id, topic=topic)
    if not sources:
        return {"answer": NO_EVIDENCE, "sources": [], "topic": topic}
    top_score = sources[0]["score"]
    selected = [source for source in sources if source["score"] >= top_score * 0.8][:2]
    snippets = []
    for source in selected:
        if source["snippet"] not in snippets:
            snippets.append(source["snippet"])
    return {"answer": "\n".join(snippets), "sources": sources, "topic": topic or sources[0]["topic"]}
