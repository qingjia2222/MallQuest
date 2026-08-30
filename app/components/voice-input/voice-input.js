/**
 * voice-input 组件：对话式语音输入（边走边问）。
 * 依赖后端 ASR，demo 阶段仅提供 UI 占位。
 * events：voice(text) 识别成功后抛出
 */
Component({
  properties: {
    disabled: { type: Boolean, value: false }
  },
  methods: {
    onTap() {
      // demo：模拟识别一段文字
      if (this.data.disabled) return;
      wx.showLoading({ title: '聆听中…' });
      setTimeout(() => {
        wx.hideLoading();
        const text = '我今天约会'; // 接后端后由 /api/voice/asr 返回真实识别
        this.triggerEvent('voice', { text });
      }, 900);
    }
  }
});
