import logging, os, subprocess, uuid, wave
from pathlib import Path
from app.config import settings
AUDIO_DIR=Path(__file__).resolve().parents[2]/"data"/"audio"
log=logging.getLogger("mall-assistant.tts")
def _silent_fallback(path):
    with wave.open(str(path),"wb") as wav: wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(b"\0\0"*8000)
def synthesize(text):
    if not text.strip(): raise ValueError("TTS text cannot be empty")
    AUDIO_DIR.mkdir(parents=True,exist_ok=True); audio_id=uuid.uuid4().hex; path=AUDIO_DIR/f"{audio_id}.wav"
    script="$out=$env:MALL_TTS_OUT;$text=$env:MALL_TTS_TEXT;$v=New-Object -ComObject SAPI.SpVoice;$zh=$v.GetVoices()|Where-Object{$_.GetDescription() -match 'Huihui|Chinese'}|Select-Object -First 1;if($zh){$v.Voice=$zh};$f=New-Object -ComObject SAPI.SpFileStream;$f.Open($out,3,$false);$v.AudioOutputStream=$f;[void]$v.Speak($text);$f.Close()"
    child_env=os.environ.copy(); child_env["MALL_TTS_OUT"]=str(path); child_env["MALL_TTS_TEXT"]=text
    proc=subprocess.run(["powershell.exe","-NoProfile","-Command",script],capture_output=True,text=True,timeout=30,env=child_env); mode=settings.tts_mode
    if proc.returncode!=0 or not path.exists() or path.stat().st_size<100:
        log.warning("windows_tts_failed returncode=%s stderr=%s",proc.returncode,proc.stderr.strip()[:400]); _silent_fallback(path); mode="wav_emergency_fallback"
    return {"audio_id":audio_id,"audio_url":f"/api/audio/{audio_id}","mime_type":"audio/wav","tts_mode":mode}
