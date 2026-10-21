/* Display paragraphs follow the authoritative transcript; jobs remain internal. */
let translationSid = null;
let translationLanguages = {zh:"Chinese", en:"English", ja:"Japanese", ko:"Korean", fr:"French", de:"German", es:"Spanish", ar:"Arabic", th:"Thai"};
function translationLabel(code) { return `${translationLanguages[code] || ""} translation`.trim(); }
let translationTargetCode = null;
const translatedRows = new Map();
const translationParagraphs = new Map();
let translationFrame = null;
let translationPending = 0;

function updateTranslationPending(count) {
  translationPending = count;
  if (typeof updateLanguageAvailability === "function") updateLanguageAvailability();
  document.getElementById("clearBtn").disabled = count > 0 || document.getElementById("state").classList.contains("running");
  const header = document.getElementById("state");
  if (count && header.textContent === "Done") header.textContent = "Finishing translation";
  else if (!count && header.textContent === "Finishing translation") header.textContent = "Done";
}

function resetTranslation(sid, target) {
  translationSid = sid;
  translationTargetCode = target;
  translatedRows.clear();
  translationParagraphs.clear();
  updateTranslationPending(0);
  document.getElementById("transcript").replaceChildren();
  document.getElementById("translationTarget").textContent = translationLabel(target);
  document.getElementById("translationState").textContent = "Waiting for transcript";
}

function translationParagraph(data) {
  const id = data.paragraph_id || data.id;
  let row = translationParagraphs.get(id);
  if (!row) {
    const element = document.createElement("article");
    element.className = "paragraph-pair transcript-paragraph";
    element.dataset.paragraphId = id;
    element.dataset.translated = "false";
    const heading = document.createElement("div"); heading.className = "pair-heading";
    const stamp = document.createElement("span"); stamp.className = "stamp"; stamp.title = "Play from here";
    const label = document.createElement("span"); label.className = "pair-label"; label.textContent = "Original";
    heading.append(stamp);
    const original = document.createElement("div"); original.className = "original-row";
    const source = document.createElement("div"); source.className = "paragraph-text fresh"; source.dir = "auto";
    original.append(label, source);
    const translation = document.createElement("div"); translation.className = "translation-row";
    const targetLabel = document.createElement("span"); targetLabel.className = "pair-label"; targetLabel.textContent = translationLabel(translationTargetCode);
    const target = document.createElement("span"); target.className = "target"; target.dir = "auto"; target.lang = translationTargetCode;
    target.textContent = "Waiting for translation…";
    translation.append(targetLabel, target);
    element.append(heading, original, translation);
    document.getElementById("transcript").append(element);
    row = {element, stamp, source, target, text: "", start_s: data.start_s};
    translationParagraphs.set(id, row);
  }
  if (data.start_s !== undefined) {
    row.start_s = data.start_s;
    row.stamp.textContent = `[${fmtT(data.start_s)}] `;
    row.stamp.dataset.t = data.start_s;
  }
  return row;
}
function translationRow(id, data) {
  const row = translatedRows.get(id) || {id, text: "", status: "queued", revision: -1};
  if (data.source_text !== undefined) row.sourceText = data.source_text;
  if (data.translation !== undefined) row.text = data.translation;
  if (data.status) row.status = data.status;
  if (data.revision !== undefined) row.revision = data.revision;
  row.paragraph_id = data.paragraph_id || row.paragraph_id || 1;
  translatedRows.set(id, row);
  translationParagraph({paragraph_id: row.paragraph_id});
  return row;
}
function paragraphTranslation(id) {
  let text = "";
  for (const job of translatedRows.values()) {
    if (job.paragraph_id !== id || !job.text) continue;
    const piece = job.text.replace(/\s*\n+\s*/g, ["zh", "ja"].includes(translationTargetCode) ? "" : " ").trim();
    if (text && piece && !["zh", "ja"].includes(translationTargetCode) && !/^[,.;:!?)]/.test(piece)) text += " ";
    text += piece;
  }
  return text;
}
function renderTranslation() {
  if (translationFrame !== null) return;
  translationFrame = requestAnimationFrame(() => {
    translationFrame = null;
    const list = document.getElementById("transcript");
    const follow = list.scrollHeight-list.scrollTop-list.clientHeight < 100;
    for (const [id, row] of translationParagraphs) {
      row.text = paragraphTranslation(id);
      const jobs = [...translatedRows.values()].filter(job => job.paragraph_id === id);
      const active = jobs.some(job => ["queued", "started", "chunk"].includes(job.status));
      row.stamp.textContent = row.start_s === undefined ? "" : `[${fmtT(row.start_s)}] `;
      row.target.textContent = row.text || "Waiting for translation…";
      row.element.dataset.translated = String(Boolean(row.text));
      row.element.dataset.status = active ? "chunk" : row.text ? "done" : "waiting";
      row.element.title = jobs.filter(job => job.error).map(job => job.error).join("; ");
    }
    if (follow) list.scrollTop = list.scrollHeight;
  });
}

function handleTranslationEvent(event) {
  const type = event.type;
  if (type === "info") {
    if (event.languages) translationLanguages = event.languages;
    if (translationSid === null || (event.translation_target !== translationTargetCode && event.sid >= translationSid)) {
      resetTranslation(event.sid || 0, event.translation_target);
    }
    document.getElementById("translationTarget").textContent = translationLabel(event.translation_target);
    return false;
  }
  if (type === "translation_reset") {
    if (translationSid !== null && event.sid < translationSid) return true;
    resetTranslation(event.sid, event.target);
    return false;
  }
  if (type === "translation_snapshot") {
    if (event.sid === null || (translationSid !== null && event.sid < translationSid)) return true;
    resetTranslation(event.sid, event.target);
    for (const paragraph of event.paragraphs || []) translationParagraph(paragraph);
    for (const segment of event.segments) translationRow(segment.id, segment);
    updateTranslationPending(event.pending);
    document.getElementById("translationState").textContent = event.pending ? `${event.pending} pending` : event.segments.length ? "Up to date" : "Waiting for transcript";
    renderTranslation();
    return false;
  }
  if (type === "text") {
    if (event.sid === translationSid) {
      for (const part of event.parts || []) translationParagraph(part);
      renderTranslation();
    }
  }
  if (type === "translation") {
    if (event.sid !== translationSid) return true;
    const previous = translatedRows.get(event.id);
    if (previous && event.revision !== undefined && event.revision <= previous.revision) return true;
    const row = translationRow(event.id, event);
    row.status = event.kind;
    if (event.kind === "chunk") row.text += event.piece;
    if (event.kind === "done" || event.kind === "cancelled") {
      if (event.text !== undefined) row.text = event.text;
    }
    if (event.error) row.error = event.error;
    updateTranslationPending(event.pending);
    document.getElementById("translationState").textContent = event.pending ? `${event.pending} pending` : "Up to date";
    renderTranslation();
    return true;
  }
  // Late ASR events from a replaced session cannot alter the current transcript.
  if (event.sid !== undefined && translationSid !== null && event.sid < translationSid) return true;
  return false;
}

document.getElementById("copyTranslation").onclick = async () => {
  const text = [...translationParagraphs.keys()].map(paragraphTranslation).filter(Boolean).join("\n\n");
  try {
    if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
    else {
      const field = document.createElement("textarea"); field.value = text;
      document.body.append(field); field.select(); document.execCommand("copy"); field.remove();
    }
    document.getElementById("translationState").textContent = "Translation copied";
  } catch (_) { document.getElementById("translationState").textContent = "Could not copy translation"; }
};
