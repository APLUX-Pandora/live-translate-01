/* Sentence pairs follow translation units inside the original ASR paragraphs. */
let translationSid = null;
let translationLanguages = {zh:"Chinese", en:"English", ja:"Japanese", ko:"Korean", fr:"French", de:"German", es:"Spanish", ar:"Arabic", th:"Thai"};
function translationLabel(code) { return `${translationLanguages[code] || ""} translation`.trim(); }
let translationTargetCode = null;
const translatedRows = new Map();
const translationParagraphs = new Map();
let translationFrame = null;
let translationPending = 0;
const dirtyParagraphs = new Set();
function setText(node, value) { if (node.textContent !== value) node.textContent = value; }
function setData(node, name, value) { if (node.dataset[name] !== value) node.dataset[name] = value; }

function updateTranslationPending(count) {
  const changed = translationPending !== count;
  translationPending = count;
  if (changed && typeof updateLanguageAvailability === "function") updateLanguageAvailability();
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
  dirtyParagraphs.clear();
  updateTranslationPending(0);
  document.getElementById("transcript").replaceChildren();
  document.getElementById("translationTarget").textContent = translationLabel(target);
  document.getElementById("translationState").textContent = "Waiting for transcript";
}

function makeSentencePair(id) {
  const element = document.createElement("div"); element.className = "sentence-pair";
  if (id !== undefined) element.dataset.sentenceId = id;
  const source = document.createElement("div"); source.className = "paragraph-text fresh"; source.dir = "auto";
  const target = document.createElement("div"); target.className = "target"; target.dir = "auto"; target.lang = translationTargetCode;
  element.dataset.translated = "false";
  element.append(source, target);
  return {element, source, target};
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
    heading.append(stamp);
    const body = document.createElement("div"); body.className = "sentence-list";
    const draft = makeSentencePair(); draft.element.dataset.pending = "true";
    body.append(draft.element);
    element.append(heading, body);
    document.getElementById("transcript").append(element);
    row = {element, stamp, body, draft, units: new Map(), jobs: [], groups: [], dirtyGroups: new Set(), committedLength: 0, sourceText: "", start_s: undefined};
    dirtyParagraphs.add(id);
    translationParagraphs.set(id, row);
  }
  if (data.text !== undefined && data.text !== row.sourceText) {
    row.sourceText = data.text;
    dirtyParagraphs.add(id);
    const last = row.groups[row.groups.length-1];
    if (last && !last.closed) row.dirtyGroups.add(last);
  }
  if (data.start_s !== undefined && data.start_s !== row.start_s) {
    row.start_s = data.start_s;
    row.stamp.textContent = `[${fmtT(data.start_s)}] `;
    row.stamp.dataset.t = data.start_s;
  }
  return row;
}
function translationRow(id, data) {
  const existing = translatedRows.get(id);
  const row = existing || {id, text: "", status: "queued", revision: -1};
  if (data.source_text !== undefined) row.sourceText = data.source_text;
  if (data.translation !== undefined) row.text = data.translation;
  if (data.status) row.status = data.status;
  if (data.reason !== undefined) row.reason = data.reason;
  if (data.revision !== undefined) row.revision = data.revision;
  row.paragraph_id = data.paragraph_id || row.paragraph_id || 1;
  translatedRows.set(id, row);
  const paragraph = translationParagraph({paragraph_id: row.paragraph_id});
  if (!existing) {
    paragraph.jobs.push(row);
    paragraph.committedLength += (row.sourceText || "").length;
    let group = paragraph.groups[paragraph.groups.length-1];
    if (!group || group.closed) {
      group = {id: row.id, jobs: [], source: "", closed: false};
      paragraph.groups.push(group);
    }
    group.jobs.push(row); group.source += row.sourceText || "";
    group.closed = closesSourceSentence(row);
    row.group = group;
  }
  paragraph.dirtyGroups.add(row.group);
  dirtyParagraphs.add(row.paragraph_id);
  return row;
}
function joinTranslationJobs(jobs) {
  let text = "";
  for (const job of jobs) {
    if (!job.text) continue;
    const piece = job.text.replace(/\s*\n+\s*/g, ["zh", "ja"].includes(translationTargetCode) ? "" : " ").trim();
    if (text && piece && !["zh", "ja"].includes(translationTargetCode) && !/^[,.;:!?)]/.test(piece)) text += " ";
    text += piece;
  }
  return text;
}
function paragraphTranslation(id) {
  return joinTranslationJobs(translationParagraphs.get(id)?.jobs || []);
}
function closesSourceSentence(job) {
  if (["sentence", "semantic_pause", "speech_pause", "finish"].includes(job.reason)) return true;
  const text = (job.sourceText || "").trim().replace(/[”’"')\]}]+$/u, "");
  if (/[。！？!?；;]$/u.test(text)) return true;
  return /\.$/.test(text) && !/(?:\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc)|\b[A-Za-z])\.$/i.test(text);
}

function renderTranslation() {
  if (translationFrame !== null) return;
  translationFrame = requestAnimationFrame(() => {
    translationFrame = null;
    const list = document.getElementById("transcript");
    const follow = list.scrollHeight-list.scrollTop-list.clientHeight < 100;
    for (const id of dirtyParagraphs) {
      const row = translationParagraphs.get(id);
      if (!row) continue;
      const tail = row.sourceText.slice(row.committedLength);
      for (const group of row.dirtyGroups) {
        let unit = row.units.get(group.id);
        if (!unit) {
          unit = makeSentencePair(group.id);
          row.units.set(group.id, unit);
          row.body.insertBefore(unit.element, row.draft.element);
        }
        setText(unit.source, (group.source + (group.closed ? "" : tail)).trim());
        const translated = joinTranslationJobs(group.jobs);
        setText(unit.target, translated);
        setData(unit.element, "translated", String(Boolean(translated)));
        setData(unit.element, "status", group.jobs.some(job => ["queued", "started", "chunk"].includes(job.status)) ? "chunk" : "done");
        const error = group.jobs.filter(job => job.error).map(job => job.error).join("; ");
        if (unit.element.title !== error) unit.element.title = error;
      }
      row.dirtyGroups.clear();
      const last = row.groups[row.groups.length-1];
      const draft = last && !last.closed ? "" : tail.trim();
      setText(row.draft.source, draft);
      if (row.draft.element.hidden !== !draft) row.draft.element.hidden = !draft;
    }
    dirtyParagraphs.clear();
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
    setText(document.getElementById("translationState"), event.pending ? `${event.pending} pending` : "Up to date");
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
