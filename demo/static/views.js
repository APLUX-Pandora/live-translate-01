/* Layout selection is local; ASR-only mode pauses the shared translation worker. */
const transcriptTabs = ["viewAsrTab", "viewTranslationTab", "viewBilingualTab"].map(id => document.getElementById(id));
const transcriptScroll = new Map();
function setTranscriptView(view, focus = false) {
  if (!["asr", "translation", "bilingual"].includes(view)) view = "bilingual";
  const list = document.getElementById("transcript");
  transcriptScroll.set(transcriptView, list.scrollTop);
  transcriptView = view;
  document.getElementById("outputPanel").dataset.view = view;
  document.getElementById("outputTitle").textContent = {asr: "ASR transcript", translation: "Translation", bilingual: "Bilingual transcript"}[view];
  document.getElementById("copyBtn").hidden = view === "translation";
  document.getElementById("dlBtn").hidden = view === "translation";
  document.getElementById("translationBar").hidden = view === "asr";
  let selected;
  for (const tab of transcriptTabs) {
    const active = tab.dataset.view === view;
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
    if (active) selected = tab;
  }
  document.getElementById("resultPanel").setAttribute("aria-labelledby", selected.id);
  list.setAttribute("aria-label", {asr: "Original transcript", translation: "Translated text", bilingual: "Original and translated sentences"}[view]);
  for (const id of translationParagraphs.keys()) dirtyParagraphs.add(id);
  renderTranslation();
  requestAnimationFrame(() => {
    if (transcriptView === view) list.scrollTop = transcriptScroll.get(view) ?? list.scrollHeight;
  });
  try { localStorage.setItem("lt01.outputView", view); } catch (_) {}
  if (focus) selected.focus();
}
let viewSwitching = false;
let lastTranslationView = "bilingual";
function syncTranscriptMode(enabled) {
  if (!enabled && transcriptView !== "asr") {
    lastTranslationView = transcriptView;
    setTranscriptView("asr");
  } else if (enabled && transcriptView === "asr" && !viewSwitching) {
    setTranscriptView(lastTranslationView);
  }
}
async function requestTranscriptView(view, focus = false) {
  if (viewSwitching) return;
  const enabled = view !== "asr";
  if (enabled === translationEnabled) {
    setTranscriptView(view, focus);
    if (enabled) lastTranslationView = view;
    return;
  }
  viewSwitching = true;
  for (const tab of transcriptTabs) tab.disabled = true;
  try {
    const result = await post("/api/translation-enabled", {enabled});
    if (result.error) throw new Error(result.error);
    applyTranslationMode(result.enabled, result.epoch);
    setTranscriptView(view, focus);
    if (enabled) lastTranslationView = view;
  } catch (error) {
    document.getElementById("translationState").textContent = error.message || "Could not switch translation mode";
  } finally {
    viewSwitching = false;
    syncTranscriptMode(translationEnabled);
    for (const tab of transcriptTabs) tab.disabled = false;
  }
}
for (const [index, tab] of transcriptTabs.entries()) {
  tab.onclick = () => requestTranscriptView(tab.dataset.view);
  tab.onkeydown = event => {
    let next;
    if (event.key === "ArrowRight") next = (index+1)%transcriptTabs.length;
    else if (event.key === "ArrowLeft") next = (index+transcriptTabs.length-1)%transcriptTabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = transcriptTabs.length-1;
    else return;
    event.preventDefault();
    return requestTranscriptView(transcriptTabs[next].dataset.view, true);
  };
}
let savedTranscriptView = "bilingual";
try { savedTranscriptView = localStorage.getItem("lt01.outputView") || savedTranscriptView; } catch (_) {}
setTranscriptView(savedTranscriptView);
