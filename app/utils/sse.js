// utils/sse.js - 流式接收（对话 / 实时状态）
// 【接后端提醒】小程序原生不支持 EventSource，需用 wx.request enableChunked 或 wx.connectSocket
// 本文件为占位，接后端时实现分块解析。当前 demoMode 用 setTimeout 模拟流式。

/**
 * 用 setTimeout 模拟逐字流式输出（demo 用）。
 * @param {string} text    完整文本
 * @param {function} cb    每次回调 { text, done }
 */
function mockStream(text, cb) {
  let i = 0;
  const step = () => {
    if (i > text.length) {
      cb({ text, done: true });
      return;
    }
    i += 2 + Math.floor(Math.random() * 3);
    cb({ text: text.slice(0, i), done: i > text.length });
    if (i <= text.length) setTimeout(step, 40);
  };
  setTimeout(step, 120);
}

module.exports = { mockStream };
