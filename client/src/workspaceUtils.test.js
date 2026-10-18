import { searchParts, wordCount, exportLecture, safeFilename } from "./workspaceUtils";
import { buildNotesHtml } from "./notesExport";

test("search is case-insensitive and treats punctuation as literal text", () => {
  const parts = searchParts("C++ is useful. c++ is fast.", "C++");
  expect(parts.filter(part => part.match).map(part => part.text)).toEqual(["C++", "c++"]);
  expect(parts.map(part => part.text).join("")).toBe("C++ is useful. c++ is fast.");
  expect(searchParts("a [ b", "[").filter(part => part.match)).toHaveLength(1);
});

test("export includes title, transcript, study notes and personal notes", () => {
  const text = exportLecture({ title: "Biology", transcript: "Plants use light.", summary: "Photosynthesis", warning: "Local summary", comments: [{ text: "Review chlorophyll" }] });
  for (const value of ["# Biology", "Plants use light.", "Photosynthesis", "Local summary", "Review chlorophyll"]) expect(text).toContain(value);
});

test("HTML exports escape custom titles and lecture content", () => {
  const html = buildNotesHtml('<img src=x onerror="alert(1)">', '<script>bad</script>');
  expect(html).not.toContain("<script>");
  expect(html).not.toContain("<img");
  expect(html).toContain("&lt;script&gt;bad&lt;/script&gt;");
});

test("titles become safe download filenames and word counts ignore whitespace", () => {
  expect(safeFilename(" ../../Biology: Lecture 1 ")).toBe("Biology-Lecture-1");
  expect(safeFilename("???")).toBe("airsketch-lecture");
  expect(wordCount("  one  two\nthree ")).toBe(3);
  expect(wordCount("  ")).toBe(0);
});
