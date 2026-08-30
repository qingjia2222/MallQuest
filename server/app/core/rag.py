import re
from pathlib import Path
KNOWLEDGE_DIR=Path(__file__).resolve().parents[2]/"data"/"knowledge"
def _tokens(text:str):
    lowered=text.lower(); tokens=set(re.findall(r"[A-Za-z0-9]+",lowered))
    for run in re.findall(r"[\u4e00-\u9fff]+",lowered):
        tokens.update(run[i:i+2] for i in range(max(1,len(run)-1)))
    return tokens
def retrieve(query:str,mall_id:str,limit:int=3):
    scored=[]; q=_tokens(query)
    for path in KNOWLEDGE_DIR.glob("*.md"):
        text=path.read_text(encoding="utf-8"); section="正文"
        if f"mall_id: {mall_id}" not in text: continue
        for block in re.split(r"\n\s*\n",text):
            if block.startswith("#"):
                lines=block.splitlines(); section=lines[0].lstrip("# ").strip(); block="\n".join(lines[1:])
            if not block.strip(): continue
            score=len(q&_tokens(block))/max(1,len(q))+sum(.25 for term in q if term in block.lower())
            if score>0: scored.append({"doc":path.name,"section":section,"snippet":block.strip(),"score":round(score,3)})
    return sorted(scored,key=lambda x:x["score"],reverse=True)[:limit]
def answer(query:str,mall_id:str):
    sources=retrieve(query,mall_id)
    return {"answer":sources[0]["snippet"] if sources else "知识库未提供这一规则。","sources":sources}
