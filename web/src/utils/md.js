// 轻量 Markdown 渲染（零依赖）：支持加粗/斜体/行内代码/链接/有序无序列表/标题/换行
// 用于把 Qwen 回复渲染成富文本，避免显示原始 ** - 等符号。

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// 行内元素：`code`、**bold**、*italic*
function inline(src) {
  return escapeHtml(src)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_]+)__/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, '$1<em>$2</em>');
}

// 块级解析：先按行聚合列表与段落
export function renderMd(src) {
  if (!src) return '';
  const lines = String(src).replace(/\r\n/g, '\n').split('\n');
  let html = '';
  let listType = null; // 'ul' | 'ol'
  const closeList = () => {
    if (listType) { html += `</${listType}>`; listType = null; }
  };

  for (let raw of lines) {
    const line = raw.trim();
    if (!line) { closeList(); continue; }

    // 标题
    const h = line.match(/^(#{1,3})\s+(.*)$/);
    if (h) { closeList(); const lv = Math.min(3, h[1].length); html += `<h${lv}>${inline(h[2])}</h${lv}>`; continue; }

    // 无序 / 有序列表
    const ul = line.match(/^[-*]\s+(.*)$/);
    const ol = line.match(/^(\d+)[.)]\s+(.*)$/);
    if (ul) { if (listType !== 'ul') { closeList(); html += '<ul>'; listType = 'ul'; } html += `<li>${inline(ul[1])}</li>`; continue; }
    if (ol) { if (listType !== 'ol') { closeList(); html += '<ol>'; listType = 'ol'; } html += `<li>${inline(ol[2])}</li>`; continue; }

    // 普通段落 / 一行内的换行
    closeList();
    html += `<p>${inline(line)}</p>`;
  }
  closeList();
  return html;
}
