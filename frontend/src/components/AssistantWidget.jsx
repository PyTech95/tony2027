import { useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageCircle, X, Send, Mic, PhoneOff, Volume2 } from "lucide-react";
import { api } from "@/lib/api";

// Short, spoken-style utterances the visitor might use to end the chat.
const STOP_RE = /^(no|nope|nah|no thanks|no thank you|nothing|nothing else|that'?s all|that is all|i'?m good|im good|i'?m okay|stop|bye|goodbye|bye bye|see you|cancel|exit)[.!\s]*$/i;
const isStopIntent = (t) => {
  const s = (t || "").trim().toLowerCase();
  if (!s) return false;
  if (STOP_RE.test(s)) return true;
  return s.split(/\s+/).length <= 3 && /\b(no|bye|stop|goodbye|nothing)\b/.test(s);
};

export default function AssistantWidget() {
  const [cfg, setCfg] = useState(null);
  const [open, setOpen] = useState(false);
  const [teaser, setTeaser] = useState(false);
  const [dismissed, setDismissed] = useState(() => sessionStorage.getItem("ty_assistant_dismissed") === "1");
  const [msgs, setMsgs] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [active, setActive] = useState(false);       // voice conversation running
  const [mode, setMode] = useState("idle");          // idle | listening | thinking | speaking
  const [lead, setLead] = useState({ name: "", email: "", phone: "", interest: "" });
  const [leadSent, setLeadSent] = useState(false);
  const [waUrl, setWaUrl] = useState("");
  const [showLead, setShowLead] = useState(false);

  const scrollRef = useRef(null);
  const audioRef = useRef(null);
  const streamRef = useRef(null);
  const mediaRecRef = useRef(null);
  const audioCtxRef = useRef(null);
  const rafRef = useRef(null);
  const activeRef = useRef(false);
  const sessionRef = useRef(null);
  const turnsRef = useRef(0);

  useEffect(() => { api.get("/assistant/config").then(({ data }) => setCfg(data)).catch(() => setCfg(false)); }, []);

  // Show a small teaser bubble shortly after load (once per session, unless dismissed).
  useEffect(() => {
    if (!cfg || cfg.enabled === false || dismissed) return;
    const t = setTimeout(() => setTeaser(true), Math.min((cfg.popup_delay || 3), 4) * 1000);
    return () => clearTimeout(t);
  }, [cfg, dismissed]);

  // Seed the greeting message when the panel opens.
  useEffect(() => {
    if (open && msgs.length === 0 && cfg?.greeting) setMsgs([{ role: "assistant", text: cfg.greeting }]);
  }, [open, cfg, msgs.length]);

  useEffect(() => { scrollRef.current?.scrollTo({ top: 99999, behavior: "smooth" }); }, [msgs, showLead, mode]);
  useEffect(() => { sessionRef.current = sessionId; }, [sessionId]);
  useEffect(() => () => { cleanup(); }, []); // unmount

  const cleanup = () => {
    activeRef.current = false;
    cancelAnimationFrame(rafRef.current);
    try { mediaRecRef.current?.state !== "inactive" && mediaRecRef.current?.stop(); } catch { /* noop */ }
    try { audioRef.current?.pause(); } catch { /* noop */ }
    stopTracks();
  };

  const stopTracks = () => {
    try { streamRef.current?.getTracks().forEach((t) => t.stop()); } catch { /* noop */ }
    streamRef.current = null;
  };

  // Play base64 mp3; resolves when playback finishes (so we don't listen over ourselves).
  const playB64 = (b64) => new Promise((resolve) => {
    if (!b64) return resolve();
    try {
      if (!audioRef.current) audioRef.current = new Audio();
      const a = audioRef.current;
      a.src = `data:audio/mpeg;base64,${b64}`;
      a.onended = () => resolve();
      a.onerror = () => resolve();
      a.play().catch(() => resolve());
    } catch { resolve(); }
  });

  const speakText = async (text) => {
    if (!text) return;
    setMode("speaking");
    try {
      const { data } = await api.post("/assistant/tts", { text });
      await playB64(data.audio_base64);
    } catch { /* silent */ }
  };

  // Record one turn with silence detection (VAD). Resolves with a Blob or null.
  const listenTurn = () => new Promise(async (resolve) => {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") return resolve(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const ctx = audioCtxRef.current || new (window.AudioContext || window.webkitAudioContext)();
      audioCtxRef.current = ctx;
      if (ctx.state === "suspended") { try { await ctx.resume(); } catch { /* noop */ } }
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);

      const rec = new MediaRecorder(stream);
      mediaRecRef.current = rec;
      const chunks = [];
      const st = { speech: false, stopped: false };
      rec.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
      const finish = () => {
        if (st.stopped) return; st.stopped = true;
        cancelAnimationFrame(rafRef.current);
        try { source.disconnect(); } catch { /* noop */ }
        try { rec.state !== "inactive" && rec.stop(); } catch { /* noop */ }
      };
      rec.onstop = () => {
        stopTracks();
        const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
        resolve(st.speech && blob.size > 1200 ? blob : null);
      };
      rec.start();

      const data = new Uint8Array(analyser.frequencyBinCount);
      const start = Date.now();
      let silenceStart = null;
      const THRESH = 0.022;
      const tick = () => {
        if (!activeRef.current) return finish();
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i++) { const x = (data[i] - 128) / 128; sum += x * x; }
        const rms = Math.sqrt(sum / data.length);
        const now = Date.now();
        if (rms > THRESH) { st.speech = true; silenceStart = null; }
        else if (st.speech) {
          if (silenceStart == null) silenceStart = now;
          else if (now - silenceStart > 1300) return finish();   // end of utterance
        }
        if (now - start > 15000) return finish();                 // hard cap
        if (!st.speech && now - start > 7000) return finish();    // no speech -> give up
        rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    } catch { resolve(null); }
  });

  const sendVoice = async (blob) => {
    setMode("thinking");
    try {
      const fd = new FormData();
      fd.append("audio", blob, "voice.webm");
      if (sessionRef.current) fd.append("session_id", sessionRef.current);
      fd.append("speak", "true");
      const { data } = await api.post("/assistant/voice", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setSessionId(data.session_id); sessionRef.current = data.session_id;
      if (data.capped) {
        setMsgs((m) => [...m, { role: "assistant", text: data.reply }]);
        return { stop: true };
      }
      setMsgs((m) => [...m, { role: "visitor", text: data.transcript }, { role: "assistant", text: data.reply }]);
      turnsRef.current += 1;
      if (turnsRef.current >= 2) setShowLead(true);
      const stop = isStopIntent(data.transcript);
      // Play the audio the server already synthesized; fall back to a TTS call only if none.
      setMode("speaking");
      if (data.audio_base64) await playB64(data.audio_base64);
      else if (data.reply) await speakText(data.reply);
      return { stop };
    } catch {
      return { stop: false, error: true };
    }
  };

  // Continuous hands-free loop: listen -> transcribe -> speak -> listen ...
  const conversationLoop = useCallback(async () => {
    while (activeRef.current) {
      setMode("listening");
      const blob = await listenTurn();
      if (!activeRef.current) break;
      if (!blob) { stopVoice(); break; }                 // silence -> pause the call
      const res = await sendVoice(blob);
      if (!activeRef.current) break;
      if (res?.stop) { endCall(); break; }               // "no / bye" -> hang up
    }
  }, []); // eslint-disable-line

  const startVoice = async () => {
    if (activeRef.current) return;
    setTeaser(false);
    activeRef.current = true; setActive(true);
    try {
      const ctx = audioCtxRef.current || new (window.AudioContext || window.webkitAudioContext)();
      audioCtxRef.current = ctx;
      if (ctx.state === "suspended") await ctx.resume();
    } catch { /* noop */ }
    const greet = cfg?.greeting || "Hi, I'm Tony's assistant. How can I help you today?";
    setMsgs((m) => (m.some((x) => x.text === greet) ? m : [...m, { role: "assistant", text: greet }]));
    await speakText(greet);
    if (activeRef.current) conversationLoop();
  };

  const stopVoice = () => {
    activeRef.current = false; setActive(false); setMode("idle");
    cancelAnimationFrame(rafRef.current);
    try { mediaRecRef.current?.state !== "inactive" && mediaRecRef.current?.stop(); } catch { /* noop */ }
    stopTracks();
  };

  const endCall = () => {
    stopVoice();
    setMsgs((m) => [...m, { role: "assistant", text: "Anytime — I'm here whenever you need me. 🌿" }]);
  };

  // Text fallback (typed questions still work + get spoken back if a call is active).
  const send = async (text) => {
    const content = (text ?? input).trim();
    if (!content || sending) return;
    setInput(""); setMsgs((m) => [...m, { role: "visitor", text: content }]); setSending(true);
    try {
      const { data } = await api.post("/assistant/chat", { session_id: sessionRef.current, message: content });
      setSessionId(data.session_id); sessionRef.current = data.session_id;
      setMsgs((m) => [...m, { role: "assistant", text: data.reply }]);
      turnsRef.current += 1;
      if (turnsRef.current >= 2) setShowLead(true);
      if (audioCtxRef.current) speakText(data.reply);
    } catch {
      setMsgs((m) => [...m, { role: "assistant", text: "Sorry, I had trouble replying. You can reach Tony's team on WhatsApp anytime." }]);
    } finally { setSending(false); }
  };

  const submitLead = async () => {
    if (!lead.name && !lead.email && !lead.phone) return;
    try {
      const { data } = await api.post("/assistant/lead", { session_id: sessionRef.current, ...lead });
      setLeadSent(true); setWaUrl(data.whatsapp_url || "");
      const waLine = data.whatsapp_url ? " You can also message us directly on WhatsApp below." : "";
      setMsgs((m) => [...m, { role: "assistant", text: `Thanks ${lead.name || "so much"}! Tony's team will reach out soon.${waLine}` }]);
    } catch { /* noop */ }
  };

  const close = () => { cleanup(); setOpen(false); setTeaser(false); setActive(false); setMode("idle"); setDismissed(true); sessionStorage.setItem("ty_assistant_dismissed", "1"); };

  if (!cfg || cfg.enabled === false) return null;

  const statusLabel = { idle: active ? "Tap the mic to talk" : "", listening: "Listening…", thinking: "Thinking…", speaking: "Speaking…" }[mode];
  const orbClass = {
    idle: "bg-[#F2F2EC] text-[#6B7269]",
    listening: "bg-[#B25A45] text-white animate-pulse ring-4 ring-[#B25A45]/25",
    thinking: "bg-[#1C221F] text-[#E0A38F]",
    speaking: "bg-[#839682] text-white ring-4 ring-[#839682]/25",
  }[mode];

  return (
    <div className="fixed bottom-4 right-4 z-[60] flex flex-col items-end gap-3" data-testid="assistant-widget">
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 20, scale: 0.96 }}
            transition={{ type: "spring", stiffness: 320, damping: 30 }}
            className="w-[92vw] max-w-[380px] h-[74vh] max-h-[600px] rounded-3xl bg-[#FAFAF7] shadow-2xl border border-[#E5E6DF] flex flex-col overflow-hidden"
            data-testid="assistant-panel"
          >
            <div className="flex items-center justify-between bg-[#1C221F] text-[#FAFAF7] px-4 py-3">
              <div className="flex items-center gap-2.5">
                <span className={`h-2 w-2 rounded-full ${active ? "bg-[#7FD1A6] animate-pulse" : "bg-white/30"}`} />
                <div>
                  <div className="text-[13px] font-semibold">Tony's Assistant</div>
                  <div className="text-[10px] text-white/60" data-testid="assistant-status">{active ? (statusLabel || "On a call") : "Voice guide · here to help"}</div>
                </div>
              </div>
              <button onClick={close} data-testid="assistant-close" className="p-1.5 rounded-full hover:bg-white/10"><X className="h-4 w-4" /></button>
            </div>

            <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
              {msgs.map((m, i) => (
                <div key={i} className={`flex ${m.role === "visitor" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[80%] rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed ${m.role === "visitor" ? "bg-[#B25A45] text-white" : "bg-white border border-[#E5E6DF] text-[#1C221F]"}`}>
                    {m.text}
                  </div>
                </div>
              ))}
              {sending && <div className="text-[11px] text-[#839682] pl-1">typing…</div>}

              {showLead && !leadSent && (
                <div className="rounded-2xl bg-white border border-[#E5E6DF] p-3 space-y-2" data-testid="assistant-lead-form">
                  <div className="text-[11px] uppercase tracking-widest font-bold text-[#B25A45]">Get personalised help</div>
                  <input data-testid="assistant-lead-name" value={lead.name} onChange={(e) => setLead({ ...lead, name: e.target.value })} placeholder="Your name" className="w-full rounded-xl border border-[#E5E6DF] px-3 py-2 text-sm" />
                  <input data-testid="assistant-lead-email" value={lead.email} onChange={(e) => setLead({ ...lead, email: e.target.value })} placeholder="Email" className="w-full rounded-xl border border-[#E5E6DF] px-3 py-2 text-sm" />
                  <input data-testid="assistant-lead-phone" value={lead.phone} onChange={(e) => setLead({ ...lead, phone: e.target.value })} placeholder="Phone / WhatsApp" className="w-full rounded-xl border border-[#E5E6DF] px-3 py-2 text-sm" />
                  <button onClick={submitLead} data-testid="assistant-lead-submit" className="pill pill-primary w-full !py-2 !text-xs">Send my details</button>
                </div>
              )}

              {leadSent && waUrl && (
                <a href={waUrl} target="_blank" rel="noopener noreferrer" data-testid="assistant-whatsapp" className="pill w-full !py-2.5 !text-xs !bg-[#25D366] !text-white justify-center">
                  <MessageCircle className="h-4 w-4" /> Chat with Tony on WhatsApp
                </a>
              )}
            </div>

            {/* Voice call bar */}
            <div className="border-t border-[#E5E6DF] bg-white px-4 py-3">
              <div className="flex flex-col items-center gap-2">
                {!active ? (
                  <button
                    onClick={startVoice}
                    data-testid="assistant-voice-start"
                    className="group relative flex items-center gap-2.5 rounded-full bg-[#B25A45] text-white px-6 py-3 text-sm font-semibold shadow-lg hover:bg-[#9c4c39] transition-colors"
                  >
                    <span className="absolute inset-0 rounded-full bg-[#B25A45]/40 animate-ping group-hover:hidden" />
                    <Mic className="h-4 w-4 relative" /> <span className="relative">Talk to Tony's assistant</span>
                  </button>
                ) : (
                  <div className="flex items-center gap-4">
                    <div className={`h-14 w-14 rounded-full flex items-center justify-center transition-all ${orbClass}`} data-testid="assistant-orb">
                      {mode === "speaking" ? <Volume2 className="h-6 w-6" /> : <Mic className="h-6 w-6" />}
                    </div>
                    <button onClick={endCall} data-testid="assistant-voice-stop" className="h-11 w-11 rounded-full bg-[#1C221F] text-white flex items-center justify-center hover:opacity-90" title="End conversation">
                      <PhoneOff className="h-5 w-5" />
                    </button>
                  </div>
                )}
                <div className="text-[11px] text-[#839682] h-4" data-testid="assistant-voice-hint">
                  {active ? (statusLabel || "Just start speaking — I'm listening") : "Hands-free voice · or type below"}
                </div>
              </div>

              <div className="mt-2 flex items-center gap-2">
                <input
                  value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()}
                  data-testid="assistant-input" placeholder="Or type your question…"
                  className="flex-1 rounded-full border border-[#E5E6DF] px-4 py-2 text-sm focus:outline-none focus:border-[#B25A45]"
                />
                <button onClick={() => send()} disabled={sending} data-testid="assistant-send" className="p-2 rounded-full bg-[#B25A45] text-white disabled:opacity-50"><Send className="h-4 w-4" /></button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {!open && (
        <>
          <AnimatePresence>
            {teaser && (
              <motion.div
                initial={{ opacity: 0, y: 12, scale: 0.9 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 12, scale: 0.9 }}
                transition={{ type: "spring", stiffness: 320, damping: 26 }}
                className="relative w-[240px] rounded-2xl rounded-br-md bg-white shadow-xl border border-[#E5E6DF] p-3"
                data-testid="assistant-teaser"
              >
                <button
                  onClick={(e) => { e.stopPropagation(); setTeaser(false); setDismissed(true); sessionStorage.setItem("ty_assistant_dismissed", "1"); }}
                  data-testid="assistant-teaser-close"
                  className="absolute -top-2 -right-2 h-6 w-6 rounded-full bg-[#1C221F] text-white flex items-center justify-center shadow-md hover:opacity-90"
                  aria-label="Dismiss"
                ><X className="h-3 w-3" /></button>
                <button onClick={() => { setOpen(true); setTeaser(false); }} data-testid="assistant-teaser-open" className="flex items-start gap-2.5 text-left w-full">
                  <span className="mt-0.5 h-8 w-8 shrink-0 rounded-full bg-[#B25A45] text-white flex items-center justify-center"><MessageCircle className="h-4 w-4" /></span>
                  <span className="min-w-0">
                    <span className="block text-[11px] font-bold text-[#1C221F]">Tony's Assistant</span>
                    <span className="block text-[12px] text-[#545E56] leading-snug line-clamp-2">{cfg.greeting || "Hi! How can I help you today?"}</span>
                    <span className="mt-1 inline-block text-[11px] font-semibold text-[#B25A45]">Tap to chat →</span>
                  </span>
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          <motion.button
            whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
            onClick={() => { setOpen(true); setTeaser(false); }}
            data-testid="assistant-launcher"
            className="relative h-14 w-14 rounded-full bg-[#B25A45] text-white shadow-xl flex items-center justify-center"
            aria-label="Open Tony's assistant"
          >
            {teaser && <span className="absolute inset-0 rounded-full bg-[#B25A45]/40 animate-ping" />}
            <MessageCircle className="h-6 w-6 relative" />
          </motion.button>
        </>
      )}
    </div>
  );
}
