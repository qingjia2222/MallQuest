// utils/format.js - 通用格式化
function formatTime(ts) {
  const d = new Date(ts);
  const pad = n => (n < 10 ? '0' + n : n);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function formatPoints(n) {
  return (n || 0).toLocaleString();
}

function waitingText(w) {
  if (w == null) return '';
  if (w === 0) return '无需等待';
  return `前方 ${w} 桌`;
}

module.exports = { formatTime, formatPoints, waitingText };
