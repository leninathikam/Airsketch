import { useEffect, useRef, useState } from "react";
import "./App.css";
import { downloadNotes, downloadText } from "./notesExport";
import { initialState, LectureClient } from "./lectureClient";
import { exportLecture, safeFilename } from "./workspaceUtils";
import Icon from "./Icons";
import Notebook from "./Notebook";

function App() {
  const [state, setState] = useState(initialState);
  const [lecture, setLecture] = useState(0);
  const [title, setTitle] = useState("Untitled lecture");
  const [comments, setComments] = useState([]);
  const [tab, setTab] = useState("Transcript");
  const [focus, setFocus] = useState(false);
  const [guide, setGuide] = useState(false);
  const [notice, setNotice] = useState("");
  const [format, setFormat] = useState("html");
  const client = useRef(null);
  const noticeTimer = useRef(null);
  const focusButton = useRef(null);

  useEffect(() => {
    const current = new LectureClient(setState);
    client.current = current;
    setState({ ...initialState });
    current.initialize().catch(error => current.update({ error: error.message }));
    const leave = () => current.dispose();
    window.addEventListener("pagehide", leave);
    return () => {
      window.removeEventListener("pagehide", leave);
      current.dispose();
    };
  }, [lecture]);

  useEffect(() => () => clearTimeout(noticeTimer.current), []);
  useEffect(() => {
    const escape = event => {
      if (event.key === "Escape") {
        setFocus(false); setGuide(false);
        if (focus) focusButton.current?.focus();
      }
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [focus]);

  const notify = message => {
    clearTimeout(noticeTimer.current);
    setNotice(message);
    noticeTimer.current = setTimeout(() => setNotice(""), 4000);
  };
  const act = async (method, ...args) => {
    const current = client.current;
    try { await current[method](...args); }
    catch (error) { current.update({ error: error.message }); }
  };
  const cameraActive = ["starting", "on", "reconnecting", "stopping"].includes(state.camera);
  const micActive = state.microphone !== "off";
  const hasContent = Boolean(state.transcript || state.summary || comments.length);
  const newLecture = () => {
    if ((hasContent || micActive || cameraActive || state.pending || state.failed) &&
        !window.confirm("Start a new lecture? Export your notes first. This clears the current drawing, notes, and pending audio.")) return;
    client.current.dispose();
    setComments([]); setTitle("Untitled lecture"); setTab("Transcript"); setNotice("");
    setLecture(value => value + 1);
  };
  const copy = async text => {
    try { await navigator.clipboard.writeText(text); notify("Copied to clipboard"); }
    catch { notify("Clipboard unavailable. Select the text to copy, or export your notes."); }
  };
  const exportNotes = () => {
    const text = exportLecture({ title, transcript: state.transcript, summary: state.summary, warning: state.warning, comments });
    if (format === "html") downloadNotes(text, title);
    else downloadText(text, format, title);
    notify("Export downloaded");
  };
  const saveBoard = () => {
    if (!state.frameUrl) return;
    const link = document.createElement("a");
    link.href = state.frameUrl;
    link.download = `${safeFilename(title)}-board.jpg`;
    link.click();
    notify("Board snapshot downloaded (includes the camera image)");
  };
  const status = !state.ready ? (state.error ? "Server offline" : "Connecting") :
    state.microphone === "on" ? "Recording lecture" : state.pending ? "Transcribing" : "Ready to begin";

  return <div className={`app ${focus ? "focus-mode" : ""}`}>
    <header className="topbar">
      <a className="brand" href="#workspace" aria-label="AirSketch workspace"><span className="brand-mark" aria-hidden="true"><svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="m4 18 7-13 4 8H8m6-3 6 8" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" /></svg></span>AirSketch<span className="brand-divider" /></a>
      <span className="topbar-context">Lecture workspace</span>
      <div className="topbar-actions">
        <span className={`connection ${state.ready ? "connected" : ""}`}><i />{state.ready ? "Connected" : "Offline"}</span>
        <button className="button button-quiet" onClick={newLecture}><Icon name="plus" size={16} />New lecture</button>
      </div>
    </header>
    <main className="workspace" id="workspace">
      <div className="workspace-heading">
        <div><div className="eyebrow">YOUR WORKSPACE <span>/</span> LECTURE {String(lecture + 1).padStart(2, "0")}</div>
          <label className="sr-only" htmlFor="lecture-title">Lecture title</label>
          <input className="lecture-title" id="lecture-title" value={title} maxLength={100} onChange={event => setTitle(event.target.value)}
            onBlur={() => { if (!title.trim()) setTitle("Untitled lecture"); }} />
          <p className="workspace-subtitle">A place to draw, listen, and make ideas your own.</p>
        </div>
        <div className="export-controls"><label className="sr-only" htmlFor="export-format">Export format</label>
          <select id="export-format" value={format} onChange={event => setFormat(event.target.value)}><option value="html">HTML document</option><option value="md">Markdown</option><option value="txt">Plain text</option></select>
          <button className="button" disabled={!hasContent} onClick={exportNotes}><Icon name="download" size={16} />Export notes</button>
        </div>
      </div>
      {state.error && <div className="error-banner" role="alert"><span><strong>{!state.ready ? "Unable to connect. " : "Something needs attention. "}</strong>{state.error === "Failed to fetch" ? "Check that the lecture server is running, then reconnect." : state.error}</span>
        {!state.ready && <button className="text-button" onClick={newLecture}>Reconnect <Icon name="arrow" size={14} /></button>}</div>}
      <div className="workspace-grid">
        <section className="board-panel" aria-label="Gesture whiteboard">
          <div className="panel-heading"><div className="panel-title"><span className="board-indicator" /><h2>Whiteboard</h2></div>
            <div className="panel-tools"><span className="camera-status">{state.camera === "on" ? "Camera live" : state.camera === "off" ? "Camera off" : state.camera}</span>
              <button className="icon-button" title={focus ? "Exit focus mode (Esc)" : "Focus mode"} aria-label={focus ? "Exit focus mode" : "Enter focus mode"}
                aria-pressed={focus} ref={focusButton} onClick={() => setFocus(value => !value)}><Icon name={focus ? "collapse" : "expand"} /></button></div>
          </div>
          <div className={`board-surface ${state.frameUrl ? "has-frame" : ""}`}>
            {state.frameUrl ? <img className="camera-frame" src={state.frameUrl} alt="Live gesture whiteboard and camera" /> : <>
              <svg className="board-grid" aria-hidden="true" width="100%" height="100%"><defs><pattern id="board-dots" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="0.8" fill="currentColor" /></pattern></defs><rect width="100%" height="100%" fill="url(#board-dots)" /></svg>
              <div className="board-empty"><span className="camera-symbol"><Icon name="camera" size={30} /></span>
                <h2>{cameraActive ? "Getting your camera ready" : "Start your whiteboard"}</h2>
                <p>{cameraActive ? "Your camera view will appear here." : "Sketch in the air. Your ideas take shape here."}</p>
                {!cameraActive && <button className="button button-primary" disabled={!state.ready} onClick={() => act("startCamera")}><Icon name="camera" size={17} />Start camera</button>}
                <span className="board-empty-note">Your microphone stays off until you turn it on.</span>
              </div>
              <span className="board-corner-label">AIRSKETCH / CANVAS</span>
            </>}
          </div>
          <div className="board-toolbar">
            <div className="capture-controls"><button className={`button button-small ${cameraActive ? "button-active" : ""}`} disabled={!state.ready}
              onClick={() => act(cameraActive ? "stopCamera" : "startCamera")}><Icon name={cameraActive ? "stop" : "camera"} size={16} />{cameraActive ? "Stop camera" : "Camera"}</button>
              <button className={`button button-small ${micActive ? "button-recording" : ""}`} disabled={!state.ready || state.generating || state.microphone === "stopping"}
                onClick={() => act(micActive ? "stopMicrophone" : "startMicrophone")}><Icon name={micActive ? "stop" : "mic"} size={16} />{state.microphone === "requesting" ? "Cancel microphone" : micActive ? "Stop recording" : "Microphone"}</button></div>
            <div className="drawing-tools"><button className="icon-button" title="Undo clear" aria-label="Undo clear" disabled={!state.ready} onClick={() => act("boardAction", "undo_clear")}><Icon name="undo" /></button>
              <button className="icon-button" title="Clear drawing" aria-label="Clear drawing" disabled={!state.ready} onClick={() => act("boardAction", "clear_board")}><Icon name="erase" /></button>
              <span className="tool-divider" /><button className="icon-button" title="Save board snapshot (includes camera image)" aria-label="Save board snapshot" disabled={!state.frameUrl} onClick={saveBoard}><Icon name="photo" /></button></div>
          </div>
          <div className="gesture-bar"><button className="text-button" onClick={() => setGuide(value => !value)} aria-expanded={guide} aria-controls="gesture-guide"><Icon name="help" size={15} />Gesture guide<Icon name={guide ? "up" : "down"} size={12} /></button>
            <span><b>Pinch</b> Draw</span><span><b>2 fingers</b> Erase</span><span><b>3 fingers</b> Color</span><span><b>Fist</b> Clear</span></div>
          {guide && <div className="gesture-details" id="gesture-guide"><p>Hold your hand in view. Pinch your thumb and index finger to draw; raise your index and middle fingers to erase. Raise three fingers to switch colors.</p><p>Hold a fist for 0.6 seconds to clear the board. Undo clear restores the last cleared drawing. Long drawings retain the latest 20,000 points.</p></div>}
        </section>
        <Notebook key={lecture} state={state} tab={tab} setTab={setTab} comments={comments} setComments={setComments}
          onGenerate={() => { setTab("Study notes"); act("generate"); }} onRetry={() => act("retryUploads")} onCopy={copy} />
      </div>
      <footer className="workspace-footer"><span className={`session-status ${state.microphone === "on" ? "is-recording" : ""}`} role="status"><i />{status}{state.pending > 0 && ` · ${state.pending} clip(s) pending`}</span>
        <span>Audio & transcripts use Google when enabled. <span className="footer-separator">/</span> Export before leaving.</span></footer>
    </main>
    {notice && <div className="toast" role="status"><Icon name="check" size={16} />{notice}</div>}
  </div>;
}
export default App;
