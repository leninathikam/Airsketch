import { createRoot } from "react-dom/client";
import { act, useState } from "react";
import Notebook from "./Notebook";
import { initialState } from "./lectureClient";

let container, root;
beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(() => { act(() => root.unmount()); container.remove(); });
function Harness({ onCopy = () => {} }) {
  const [tab, setTab] = useState("Transcript");
  const [comments, setComments] = useState([]);
  return <Notebook state={{ ...initialState, transcript: "Light helps plants. Plants use light.", ready: true }}
    tab={tab} setTab={setTab} comments={comments} setComments={setComments} onCopy={onCopy} onGenerate={() => {}} onRetry={() => {}} />;
}
function fill(node, text) {
  const prototype = node.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(prototype, "value").set.call(node, text);
  node.dispatchEvent(new Event("input", { bubbles: true }));
}

test("search highlights matches, navigates them and copies transcript", () => {
  const copy = jest.fn();
  act(() => root.render(<Harness onCopy={copy} />));
  act(() => fill(container.querySelector('input[type="search"]'), "light"));
  expect(container.querySelectorAll("mark")).toHaveLength(2);
  act(() => container.querySelector('[aria-label="Next match"]').click());
  expect(container.querySelectorAll("mark")[1].dataset.current).toBe("true");
  act(() => [...container.querySelectorAll("button")].find(button => button.textContent.trim() === "Copy").click());
  expect(copy).toHaveBeenCalledWith("Light helps plants. Plants use light.");
});

test("personal notes support keyboard submission and removal", () => {
  act(() => root.render(<Harness />));
  act(() => container.querySelectorAll('[role="tab"]')[2].click());
  act(() => fill(container.querySelector("textarea"), "Review this topic"));
  act(() => container.querySelector("textarea").dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", ctrlKey: true, bubbles: true })));
  expect(container.querySelector(".personal-note").textContent).toContain("Review this topic");
  act(() => container.querySelector('[aria-label^="Remove note"]').click());
  expect(container.querySelector(".personal-note")).toBeNull();
});

test("tabs respond to arrow keys and expose the selected panel", () => {
  act(() => root.render(<Harness />));
  act(() => container.querySelector('[role="tablist"]').dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })));
  expect(container.querySelector('[aria-selected="true"]').textContent).toBe("Study notes");
  expect(container.querySelector('[role="tabpanel"]').getAttribute("aria-labelledby")).toBe("tab-1");
});
