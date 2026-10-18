import { useEffect, useRef, useState } from "react";
import Icon from "./Icons";
import { searchParts, wordCount } from "./workspaceUtils";

function Transcript({ text }) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const container = useRef(null);
  const parts = searchParts(text, query);
  const count = parts.filter(part => part.match).length;
  useEffect(() => {
    container.current?.querySelector('[data-current="true"]')?.scrollIntoView?.({ block: "nearest" });
  }, [query, active]);
  let match = -1;
  return <>
    <div className="transcript-search">
      <Icon name="search" size={16} />
      <input type="search" aria-label="Search transcript" placeholder="Find in transcript" value={query}
        onChange={event => { setQuery(event.target.value); setActive(0); }} />
      {query && <span className="search-count" role="status">{count ? `${active + 1}/${count}` : "No matches"}</span>}
      {count > 1 && <>
        <button className="icon-button" aria-label="Previous match" onClick={() => setActive((active - 1 + count) % count)}><Icon name="up" size={14} /></button>
        <button className="icon-button" aria-label="Next match" onClick={() => setActive((active + 1) % count)}><Icon name="down" size={14} /></button>
      </>}
    </div>
    <div className="notebook-content transcript-content" ref={container}>
      {text ? <p className="transcript-text">{parts.map((part, index) => {
        if (!part.match) return <span key={index}>{part.text}</span>;
        match += 1;
        return <mark key={index} data-current={match === active}>{part.text}</mark>;
      })}</p> : <Empty icon="mic" title="Keep the conversation."
        description="Start the microphone to turn your lecture into a searchable transcript. New text arrives every 20 seconds." />}
    </div>
  </>;
}

function Empty({ icon, title, description }) {
  return <div className="notebook-empty"><span className="empty-symbol"><Icon name={icon} size={25} /></span>
    <h3>{title}</h3><p>{description}</p></div>;
}

function StudyNotes({ text }) {
  return <div className="study-prose">{text.split("\n").map((line, index) => {
    if (/^#{1,3} /.test(line)) return <h3 key={index}>{line.replace(/^#+ /, "")}</h3>;
    if (line.startsWith("Lecture evidence:")) return <blockquote key={index}>{line.replace("Lecture evidence: ", "")}</blockquote>;
    if (/^[-*] /.test(line)) return <p className="study-bullet" key={index}>{line.slice(2)}</p>;
    return line.trim() ? <p key={index}>{line}</p> : null;
  })}</div>;
}

export default function Notebook({ state, tab, setTab, comments, setComments, onGenerate, onRetry, onCopy }) {
  const [draft, setDraft] = useState("");
  const tabs = ["Transcript", "Study notes", "My notes"];
  const selected = tabs.indexOf(tab);
  const addNote = () => {
    if (!draft.trim()) return;
    setComments(items => [...items.slice(-99), { id: `${Date.now()}-${items.length}`, text: draft.trim(),
      time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) }]);
    setDraft("");
  };
  const copyText = tab === "Transcript" ? state.transcript : tab === "Study notes" ? state.summary : comments.map(item => item.text).join("\n\n");
  return <aside className="notebook" aria-label="Lecture notebook">
    <div className="notebook-heading"><h2>Notebook</h2><span className="quiet-label">THIS LECTURE</span></div>
    <div className="notebook-tabs" role="tablist" aria-label="Notebook views" onKeyDown={event => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === "Home" ? 0 : event.key === "End" ? 2 : (selected + (event.key === "ArrowRight" ? 1 : -1) + 3) % 3;
      setTab(tabs[next]);
      event.currentTarget.querySelectorAll('[role="tab"]')[next].focus();
    }}>
      {tabs.map((name, index) => <button key={name} role="tab" id={`tab-${index}`} aria-controls={`panel-${index}`}
        aria-selected={tab === name} tabIndex={tab === name ? 0 : -1} onClick={() => setTab(name)}>
        {name}{name === "My notes" && comments.length > 0 && <span className="count-badge">{comments.length}</span>}
      </button>)}
    </div>
    <div className="notebook-panel" role="tabpanel" id={`panel-${selected}`} aria-labelledby={`tab-${selected}`}>
      {tab === "Transcript" && <Transcript text={state.transcript} />}
      {tab === "Study notes" && <div className="notebook-content">
        {state.summary ? <StudyNotes text={state.summary} /> : <Empty icon="document" title="Make sense of the lecture."
          description="Turn the transcript into key ideas and review questions, with supporting quotes from the lecture." />}
        {state.warning && <p className="inline-notice" role="status">{state.warning}</p>}
      </div>}
      {tab === "My notes" && <>
        <div className="notebook-content personal-notes">
          {comments.length ? comments.map(note => <article className="personal-note" key={note.id}>
            <div><time>{note.time}</time><button className="icon-button" aria-label={`Remove note: ${note.text.slice(0, 30)}`}
              onClick={() => setComments(items => items.filter(item => item.id !== note.id))}><Icon name="close" size={14} /></button></div>
            <p>{note.text}</p>
          </article>) : <Empty icon="note" title="A thought worth keeping."
            description="Add questions, reminders, or your own takeaways. Personal notes stay in this tab and are included in exports." />}
        </div>
        <div className="note-composer">
          <label className="sr-only" htmlFor="personal-note">Write a personal note</label>
          <textarea id="personal-note" placeholder="Write a thought or a question..." maxLength={2000} value={draft}
            onChange={event => setDraft(event.target.value)} onKeyDown={event => {
              if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); addNote(); }
            }} />
          <div><span>Ctrl / ⌘ + Enter</span><button className="button button-small" disabled={!draft.trim()} onClick={addNote}>Add note <Icon name="plus" size={14} /></button></div>
        </div>
      </>}
    </div>
    {state.failed > 0 && <div className="upload-warning" role="status"><span>{state.failed} clip(s) need another try.</span>
      <button className="text-button" disabled={state.pending > 0} onClick={onRetry}>Retry uploads</button></div>}
    <div className="notebook-meta"><span>{tab === "My notes" ? `${comments.length} personal notes` : `${wordCount(copyText).toLocaleString()} words`}</span>
      <button className="text-button" disabled={!copyText} onClick={() => onCopy(copyText)}><Icon name="copy" size={14} /> Copy</button></div>
    <div className="notebook-bottom">
      <button className="button button-primary generate-button" disabled={!state.ready || state.generating ||
        (!state.transcript && state.microphone === "off" && !state.pending)} onClick={onGenerate}>
        <Icon name="document" size={17} />{state.generating ? "Preparing notes..." : state.summary ? "Regenerate study notes" : "Generate study notes"}<Icon name="arrow" size={17} />
      </button>
      <p>Finishes recording and includes pending audio.</p>
    </div>
  </aside>;
}
