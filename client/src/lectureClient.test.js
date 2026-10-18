import { LectureClient } from "./lectureClient";

const deferred = () => {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
};
const reply = (data, ok = true) => ({ ok, status: ok ? 200 : 502, json: async () => data });
class Recorder {
  static isTypeSupported(type) { return type.startsWith("audio/webm"); }
  constructor() { this.state = "inactive"; }
  start() { this.state = "recording"; }
  stop() {
    this.state = "inactive";
    Promise.resolve().then(() => {
      this.ondataavailable({ data: new Blob(["final audio"]) });
      this.onstop();
    });
  }
}
let client, stopTrack;
beforeEach(() => {
  jest.useFakeTimers();
  global.MediaRecorder = Recorder;
  stopTrack = jest.fn();
  Object.defineProperty(navigator, "mediaDevices", { configurable: true,
    value: { getUserMedia: jest.fn().mockResolvedValue({ getTracks: () => [{ stop: stopTrack }] }) } });
  global.fetch = jest.fn().mockResolvedValue(reply({}));
  URL.createObjectURL = jest.fn(() => "blob:frame");
  URL.revokeObjectURL = jest.fn();
  client = new LectureClient(jest.fn());
  client.token = "test-session";
});
afterEach(() => { client.dispose(); jest.useRealTimers(); });

test("permission resolving after stop cannot reactivate microphone", async () => {
  const permission = deferred();
  navigator.mediaDevices.getUserMedia.mockReturnValue(permission.promise);
  const starting = client.startMicrophone();
  await client.stopMicrophone();
  permission.resolve({ getTracks: () => [{ stop: stopTrack }] });
  await starting;
  expect(stopTrack).toHaveBeenCalled();
  expect(client.state.microphone).toBe("off");
  expect(client.recording).toBe(false);
});

test("generate awaits final audio and preserves separate transcript and summary", async () => {
  const upload = deferred();
  fetch.mockImplementation(url => url.endsWith("/transcribe") ? upload.promise : Promise.resolve(reply({ text: "Study notes", source: "gemini" })));
  await client.startMicrophone();
  const generating = client.generate();
  for (let i = 0; i < 6; i++) await Promise.resolve();
  expect(fetch.mock.calls.some(([url]) => url.endsWith("/summarize"))).toBe(false);
  upload.resolve(reply({ transcript: "Actual lecture", text: "Actual lecture" }));
  await generating;
  expect(client.state.transcript).toBe("Actual lecture");
  expect(client.state.summary).toBe("Study notes");
  expect(stopTrack).toHaveBeenCalled();
  expect(client.state.microphone).toBe("off");
});

test("uploads are serialized and failed clips retain their sequence on retry", async () => {
  const first = deferred();
  fetch.mockReturnValueOnce(first.promise).mockResolvedValue(reply({ transcript: "second" }));
  client.enqueue(new Blob(["first"]), 0);
  client.enqueue(new Blob(["second"]), 1);
  await Promise.resolve();
  expect(fetch).toHaveBeenCalledTimes(1);
  first.resolve(reply({ error: "unavailable" }, false));
  await client.queue;
  expect(client.state.failed).toBe(1);
  await client.retryUploads();
  expect(fetch.mock.calls[2][1].body.get("sequence")).toBe("0");
  expect(client.state.failed).toBe(0);
});

test("recorder startup failure releases microphone and does not hang stop", async () => {
  const original = Recorder.prototype.start;
  Recorder.prototype.start = () => { throw new Error("unsupported"); };
  try {
    await expect(client.startMicrophone()).rejects.toThrow("unsupported");
    await client.stopMicrophone();
    expect(stopTrack).toHaveBeenCalled();
    expect(client.state.microphone).toBe("off");
  } finally { Recorder.prototype.start = original; }
});

test("disposing discards late recorder data and stops media tracks", async () => {
  await client.startMicrophone();
  client.dispose();
  await Promise.resolve();
  await client.queue;
  expect(stopTrack).toHaveBeenCalled();
  expect(fetch.mock.calls.some(([url]) => url.endsWith("/transcribe"))).toBe(false);
});

test("late frames after stop do not allocate a new object URL", async () => {
  const frame = deferred();
  fetch.mockImplementation(url => url.endsWith("/frame.jpg") ? frame.promise : Promise.resolve(reply({})));
  client.cameraWanted = true;
  const polling = client.pollFrame(client.cameraGeneration);
  await client.stopCamera();
  frame.resolve({ ok: true, blob: async () => new Blob(["jpeg"]) });
  await polling;
  expect(URL.createObjectURL).not.toHaveBeenCalled();
  expect(client.state.camera).toBe("off");
});

test("late session initialization after disposal closes the new capability", async () => {
  const session = deferred();
  fetch.mockReturnValueOnce(session.promise).mockResolvedValue(reply({}));
  client.token = null;
  const initializing = client.initialize();
  client.dispose();
  session.resolve(reply({ token: "late-token" }));
  await initializing;
  expect(fetch.mock.calls[1][1].method).toBe("DELETE");
  expect(client.state.ready).toBe(false);
});


test("recording cannot bypass the pending audio cap", async () => {
  client.state.pending = 6;
  await expect(client.startMicrophone()).rejects.toThrow("pending uploads");
  expect(navigator.mediaDevices.getUserMedia).not.toHaveBeenCalled();
});
