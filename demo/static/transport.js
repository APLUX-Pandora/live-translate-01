/* Ordered PCM delivery with acknowledgement-based retry and bounded HTTP requests. */
(function (scope) {
  async function requestJSON(url, options = {}, timeoutMs = 10000) {
    const controller = new AbortController(), external = options.signal;
    const abort = () => controller.abort();
    if (external) { if (external.aborted) abort(); else external.addEventListener('abort', abort, {once:true}); }
    const timer = setTimeout(abort, timeoutMs);
    try {
      const response = await fetch(url, {...options, signal:controller.signal});
      const data = await response.json();
      if (!response.ok || data.error) {
        const error=new Error(data.error || `HTTP ${response.status}`);
        error.status=response.status; error.payload=data; throw error;
      }
      return data;
    } finally {
      clearTimeout(timer);
      if (external) external.removeEventListener('abort', abort);
    }
  }
  class AudioDelivery {
    constructor({request = requestJSON, changed = () => {}} = {}) {
      this.request = request; this.changed = changed; this.session = null;
    }
    begin(sid) {
      if (this.session && (this.session.queue.length || this.session.active || this.session.failed))
        throw new Error('Finish or recover the current recording before starting another');
      this.session = {sid, queue:[], next:0, active:null, failed:null, ended:false, endAck:false, controller:new AbortController()};
    }
    get busy() { const s=this.session; return !!s && (s.queue.length>0 || !!s.active || !!s.failed || (s.ended && !s.endAck)); }
    get failed() { return this.session && this.session.failed; }
    enqueue(buffer) {
      const s=this.session;
      if (!s || s.ended) return;
      s.queue.push({seq:s.next++, buffer}); this.pump();
    }
    async pump() {
      const s=this.session;
      if (!s || s.active || s.failed) return s && s.active;
      s.active=Promise.resolve().then(async () => {
        try {
          while (this.session === s && s.queue.length) {
            const item=s.queue[0];
            let ack;
            try {
              ack=await this.request(`/api/audio?sid=${s.sid}&seq=${item.seq}`, {
              method:'POST', headers:{'Content-Type':'application/octet-stream'}, body:item.buffer, signal:s.controller.signal});
            } catch (error) {
              if (error.status !== 429) throw error;
              await new Promise(resolve => setTimeout(resolve, 150));
              continue;
            }
            if (this.session !== s) return;
            if (ack.next_seq !== item.seq+1) throw new Error('Unexpected audio acknowledgement; check the server connection');
            s.queue.shift();
            if (this.session===s) this.changed(s);
          }
          if (this.session === s && s.ended && !s.endAck) {
            await this.request('/api/end', {method:'POST', headers:{'Content-Type':'application/json'},
              signal:s.controller.signal, body:JSON.stringify({sid:s.sid, next_seq:s.next})});
            s.endAck=true;
          }
        } catch (error) { s.failed=error; }
        finally { s.active=null; if (this.session===s) this.changed(s); }
      });
      // Defer the task until its owner is assigned, including an already-finished recording.
      await s.active;
    }
    async end() { const s=this.session; if (!s) return; s.ended=true; await this.pump(); }
    async retry() { const s=this.session; if (!s) return; s.failed=null; await this.pump(); }
    discardFailedRecording() {
      const s=this.session;
      this.session=null;
      if (s) s.controller.abort();
    }
  }
  scope.PandoraTransport={requestJSON,AudioDelivery};
  if (typeof module!=='undefined') module.exports=scope.PandoraTransport;
})(typeof globalThis!=='undefined'?globalThis:this);
