// Own async recording work outside React renders; every callback belongs to a lecture.
export const initialState = {
  ready: false, camera: "off", frameUrl: "", microphone: "off", pending: 0,
  transcript: "", summary: "", source: "", warning: "", error: "", generating: false,
  failed: 0,
};
const SERVER = process.env.REACT_APP_API_URL || "http://127.0.0.1:5000";

export class LectureClient {
  constructor(onChange) {
    this.onChange = onChange;
    this.state = { ...initialState };
    this.disposed = false;
    this.micGeneration = 0;
    this.sequence = 0;
    this.queue = Promise.resolve();
    this.failures = new Map();
    this.cameraWanted = false;
    this.cameraGeneration = 0;
  }

  update(change) {
    Object.assign(this.state, change);
    if (!this.disposed) this.onChange({ ...this.state });
  }

  async request(path, options = {}) {
    const { timeoutMs = 75000, ...fetchOptions } = options;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(`${SERVER}${path}`, {
        ...fetchOptions, signal: controller.signal,
        headers: { "X-Session-Token": this.token || "", ...options.headers },
      });
    } finally { clearTimeout(timeout); }
  }

  async json(path, options = {}, allowRefresh = true) {
    const response = await this.request(path, options);
    const data = await response.json().catch(() => ({}));
    if (response.status === 401 && allowRefresh && path !== "/session") {
      await this.initialize();
      return this.json(path, options, false);
    }
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
    return data;
  }

  async initialize() {
    const data = await this.json("/session", { method: "POST", headers: { "X-AirSketch": "1" } }, false);
    this.token = data.token;
    if (this.disposed) { this.closeRemote(); return; }
    this.update({ ready: true, error: "" });
  }

  async startCamera() {
    if (this.cameraWanted || this.disposed) return;
    this.cameraWanted = true;
    const generation = ++this.cameraGeneration;
    this.update({ camera: "starting", error: "" });
    this.cameraStart = this.json("/camera/start", { method: "POST" });
    try {
      await this.cameraStart;
      if (this.cameraWanted && !this.disposed) this.pollFrame(generation);
    } catch (error) {
      this.cameraWanted = false;
      this.update({ camera: "off" });
      throw error;
    }
  }

  async pollFrame(generation) {
    if (!this.cameraWanted || this.disposed || generation !== this.cameraGeneration) return;
    try {
      const response = await this.request("/frame.jpg", { timeoutMs: 3000 });
      if (response.ok) {
        const blob = await response.blob();
        if (!this.cameraWanted || this.disposed || generation !== this.cameraGeneration) return;
        const url = URL.createObjectURL(blob);
        const previous = this.state.frameUrl;
        this.update({ frameUrl: url, camera: "on" });
        if (previous) URL.revokeObjectURL(previous);
      } else {
        const data = await response.json().catch(() => ({}));
        if (!this.cameraWanted || this.disposed || generation !== this.cameraGeneration) return;
        if (response.status === 401) {
          await this.initialize();
        } else if (["error", "off"].includes(data.state)) {
          this.cameraWanted = false;
          if (this.state.frameUrl) URL.revokeObjectURL(this.state.frameUrl);
          this.update({ frameUrl: "", camera: data.state, error: data.error || "Camera stopped or unavailable. Try starting it again." });
        } else if (!this.state.frameUrl) {
          this.update({ camera: data.state || "starting" });
        }
      }
    } catch {
      if (this.cameraWanted && !this.disposed && generation === this.cameraGeneration && !this.state.frameUrl) {
        this.update({ camera: "reconnecting" });
      }
    }
    if (this.cameraWanted && !this.disposed && generation === this.cameraGeneration) this.frameTimer = setTimeout(() => this.pollFrame(generation), 40);
  }

  async stopCamera() {
    ++this.cameraGeneration;
    this.cameraWanted = false;
    clearTimeout(this.frameTimer);
    if (this.state.frameUrl) URL.revokeObjectURL(this.state.frameUrl);
    this.update({ frameUrl: "", camera: "stopping" });
    await this.cameraStart?.catch(() => {});
    await this.json("/camera/stop", { method: "POST" });
    this.update({ camera: "off" });
  }

  async startMicrophone() {
    if (this.state.microphone !== "off" || this.disposed) return;
    if (this.state.pending + this.failures.size >= 6) {
      throw new Error("Finish or retry pending uploads before recording more audio.");
    }
    if (this.sequence >= 2000) throw new Error("Lecture clip limit reached. Download notes and start a new lecture.");
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      throw new Error("Audio recording is unavailable in this browser. Use a supported browser on localhost or HTTPS.");
    }
    const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"]
      .find(type => MediaRecorder.isTypeSupported(type));
    if (!mime) throw new Error("This browser has no supported recording format.");
    const generation = ++this.micGeneration;
    this.update({ microphone: "requesting", error: "" });
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (this.disposed || generation !== this.micGeneration) {
        stream.getTracks().forEach(track => track.stop());
        return;
      }
      this.stream = stream;
      this.mime = mime;
      this.recording = true;
      this.startClip(generation);
      this.update({ microphone: "on" });
    } catch (error) {
      stream?.getTracks().forEach(track => track.stop());
      if (generation === this.micGeneration) {
        this.recording = false;
        this.stream = null;
        this.update({ microphone: "off" });
        throw new Error(`Microphone could not start: ${error.message}`);
      }
    }
  }

  startClip(generation) {
    const recorder = new MediaRecorder(this.stream, { mimeType: this.mime });
    const chunks = [];
    const sequence = this.sequence++;
    let resolveStopped;
    const stopped = new Promise(resolve => { resolveStopped = resolve; });
    this.clip = { recorder, stopped };
    recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
    recorder.onerror = () => {
      this.update({ error: "Audio recording failed. Check the microphone and try again." });
      this.stopMicrophone();
    };
    recorder.onstop = () => {
      clearTimeout(this.clipTimer);
      const blob = new Blob(chunks, { type: this.mime.split(";")[0] });
      if (!this.disposed && blob.size) this.enqueue(blob, sequence);
      resolveStopped();
      if (this.recording && generation === this.micGeneration && !this.disposed) {
        if (this.state.pending + this.failures.size >= 6 || sequence >= 1999) {
          this.update({ error: "Recording paused: finish or retry pending uploads before continuing." });
          this.stopMicrophone();
        } else {
          try { this.startClip(generation); }
          catch (error) {
            this.update({ error: `Recording stopped: ${error.message}` });
            this.stopMicrophone();
          }
        }
      }
    };
    try { recorder.start(); }
    catch (error) { this.clip = null; resolveStopped(); throw error; }
    this.clipTimer = setTimeout(() => {
      if (recorder.state === "recording") recorder.stop();
    }, 20000);
  }

  async stopMicrophone() {
    ++this.micGeneration;
    this.recording = false;
    clearTimeout(this.clipTimer);
    const clip = this.clip;
    this.update({ microphone: "stopping" });
    if (clip?.recorder.state === "recording") clip.recorder.stop();
    this.stream?.getTracks().forEach(track => track.stop());
    this.stream = null;
    if (clip) await clip.stopped;
    if (this.clip === clip) this.clip = null;
    this.update({ microphone: "off" });
  }

  enqueue(blob, sequence) {
    this.update({ pending: this.state.pending + 1 });
    this.queue = this.queue.then(async () => {
      if (this.disposed) return;
      try {
        const form = new FormData();
        form.append("audio", blob, `lecture-${sequence}`);
        form.append("sequence", String(sequence));
        const data = await this.json("/transcribe", { method: "POST", body: form });
        this.failures.delete(sequence);
        this.update({ transcript: data.transcript, failed: this.failures.size });
      } catch (error) {
        this.failures.set(sequence, blob);
        this.update({ failed: this.failures.size, error: error.message });
        // Bound retained audio even when the service is unavailable.
        this.stopMicrophone();
      } finally { this.update({ pending: this.state.pending - 1 }); }
    });
  }

  async retryUploads() {
    await this.queue;
    const failed = [...this.failures];
    this.update({ error: "" });
    for (const [sequence, blob] of failed) this.enqueue(blob, sequence);
    await this.queue;
  }

  async generate() {
    if (this.state.generating) return;
    this.update({ generating: true, error: "" });
    try {
      await this.stopMicrophone();
      await this.queue;
      if (this.failures.size) throw new Error("Retry failed uploads before generating notes.");
      if (this.disposed) return;
      const data = await this.json("/summarize", { method: "POST" });
      this.update({ summary: data.text, source: data.source, warning: data.warning || "" });
    } finally { this.update({ generating: false }); }
  }

  async boardAction(action) {
    await this.json(`/${action}`, { method: "POST" });
  }

  closeRemote() {
    if (!this.token) return;
    fetch(`${SERVER}/session`, {
      method: "DELETE", headers: { "X-Session-Token": this.token }, keepalive: true,
    }).catch(() => {});
  }

  dispose() {
    this.disposed = true;
    this.cameraWanted = false;
    this.recording = false;
    ++this.micGeneration;
    clearTimeout(this.clipTimer);
    clearTimeout(this.frameTimer);
    if (this.clip?.recorder.state === "recording") this.clip.recorder.stop();
    this.stream?.getTracks().forEach(track => track.stop());
    if (this.state.frameUrl) URL.revokeObjectURL(this.state.frameUrl);
    this.closeRemote();
  }
}
