"""Build a short bullet summary from a lecture transcript."""

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "to", "of", "in", "on", "for",
    "with", "is", "are", "was", "were", "be", "been", "it", "this", "that",
    "i", "you", "we", "they", "he", "she", "as", "at", "from", "by", "not",
}


def _sentences(text):
    chunks = []
    current = []
    for word in text.split():
        current.append(word)
        if word.endswith((".", "!", "?")) or len(current) >= 18:
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))
    return chunks


def summarize(text):
    cleaned = " ".join(text.split())
    if not cleaned:
        return "Nothing to summarize yet."

    counts = {}
    for raw in cleaned.lower().replace(".", " ").replace("!", " ").replace("?", " ").split():
        word = raw.strip("'")
        if len(word) < 3 or word in STOP_WORDS:
            continue
        counts[word] = counts.get(word, 0) + 1

    ranked = []
    for index, sentence in enumerate(_sentences(cleaned)):
        score = sum(counts.get(word.strip(".,!?'").lower(), 0) for word in sentence.split())
        ranked.append((score, index, sentence))

    picked = [item for item in ranked if item[0] > 0]
    picked.sort(key=lambda item: item[0], reverse=True)
    picked = sorted(picked[:4], key=lambda item: item[1])
    if not picked:
        return cleaned[:280]
    return "\n".join(f"- {sentence}" for _, _, sentence in picked)
