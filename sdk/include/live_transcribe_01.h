/*
 * live_transcribe_01.h - Live Transcribe 01 streaming ASR on Qualcomm NPUs (QNN context binaries via aidlite), C ABI of
 * liblive_transcribe_01.so. The NPU architecture is a property of the model files; the library itself is architecture-neutral.
 *
 * The engine implements the model's own streaming protocol (one text token per audio clock): audio windowing,
 * mel, audio tower + projector (NPU), LM (NPU, native KV), KV / position management, the 30 s rolling context, greedy
 * decoding, the semantic-VAD (end-of-turn) heads and the soft-reset replay mechanism.
 * It is passive: no threads, no timers, no IO. The caller decides when and how much audio to feed; every call runs
 * synchronously all the clocks the audio allows. Policies (silence gate, when to soft-reset, pacing, UI) belong to the
 * caller.
 *
 * Typical use:
 *   lt01_options o; lt01_default_options(&o); o.clock_ms = 160; o.lang = LT01_LANG_ZH;
 *   lt01_engine *e = lt01_create("models", &o);           // loads the bins (~2 s)
 *   lt01_reset(e);                                       // new session
 *   while (have_audio) { lt01_feed(e, pcm, n); n_tok = lt01_read_tokens(e, toks, cap); ... }
 *   lt01_finish(e, -1); lt01_read_tokens(...);             // end of input: drain the last tokens
 *   lt01_destroy(e);
 *
 * Feeding is chunk-invariant: the same audio fed in any chunking gives the same tokens.
 * One engine is not thread-safe; use it from one thread at a time.
 */
#ifndef LIVE_TRANSCRIBE_01_H
#define LIVE_TRANSCRIBE_01_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define LT01_VERSION "0.5.1"

#if defined(__GNUC__)
#define LT01_API __attribute__((visibility("default")))
#else
#define LT01_API
#endif

/* return codes (>= 0 = success) */
#define LT01_OK 0
#define LT01_ERR_ARG -1     /* bad argument */
#define LT01_ERR_MODEL -2   /* model file missing / inconsistent */
#define LT01_ERR_NPU -3     /* aidlite / QNN failure */
#define LT01_ERR_FULL -4    /* LM KV full (only with roll_s = 0): call lt01_finish + lt01_reset */
#define LT01_ERR_STATE -5   /* call not valid in the current state (e.g. lt01_feed after lt01_finish) */
#define LT01_ERR_INTERNAL -6 /* unexpected failure inside the library (e.g. out of memory) */

#define LT01_LANG_ZH 0
#define LT01_LANG_EN 1
#define LT01_EOT_HORIZONS 4 /* semantic VAD horizons, see lt01_info.eot_horizons_s (0.5 / 1 / 2 / 3 s) */
#define LT01_EOT_CLASSES 8

typedef struct lt01_engine lt01_engine;

typedef struct {
    int clock_ms;      /* audio clock: 160 (default) or 80 ms, one text token per clock; selects the model package */
    int lang;          /* LT01_LANG_ZH / LT01_LANG_EN: which LM prefix KV (language token) is loaded */
    double roll_s;     /* LM rolling context in seconds (default 28.8); 0 = no rolling (LT01_ERR_FULL when KV is full) */
    int stable_rows;   /* LM rows kept by every trim; -1 = default (left pad: 9 at 160 ms, 18 at 80 ms) */
    int semantic_vad;  /* 1 = compute the end-of-turn heads for every token (lt01_token.eot), 0 = off. Default 1 */
    double replay_max_s; /* audio rows cached for lt01_soft_reset (default 10 s) */
} lt01_options;

typedef struct {
    int32_t id;        /* token id; EOS is never emitted */
    int32_t is_text;   /* 0 for STREAMING_PAD / STREAMING_WORD / BOS / PAD (no text), 1 otherwise */
    float audio_t;     /* end of the audio clock behind this token, seconds from the session start (real audio, the
                          synthetic left pad excluded) */
    float eot[LT01_EOT_HORIZONS]; /* P(no speech within horizon h) after this token; 0 if semantic_vad is off */
} lt01_token;

typedef struct {
    int sampling_rate;          /* 16000 */
    int samples_per_token;      /* one clock: 2560 at 160 ms, 1280 at 80 ms */
    int clock_ms, lang;
    float eot_horizons_s[LT01_EOT_HORIZONS];
    int num_delay_tokens;       /* model delay in clocks (text lags the audio by num_delay_tokens * clock) */
    int streaming_pad_id;       /* STREAMING_PAD ("nothing new yet"); policies use it to tell silence from output */
    int default_tail_tokens;    /* lt01_finish(e, -1) appends this many silent clocks */
    double roll_s;              /* LM rolling context in use (0 = off) */
} lt01_info;

typedef struct {
    double audio_fed_s;         /* real audio fed in this session */
    int64_t n_tokens;           /* tokens emitted in this session */
    int64_t lm_pos;             /* absolute LM position of the next row */
    int32_t lm_trims;           /* rolling trims so far */
    int32_t soft_resets;        /* lt01_soft_reset calls in this session */
    /* cumulative ms in this session, per stage */
    double ms_mel, ms_tower_prep, ms_tower_npu, ms_tower_post, ms_projector_npu, ms_lm_prep, ms_lm_npu, ms_lm_post;
} lt01_stats;

LT01_API const char *lt01_version(void);
LT01_API void lt01_default_options(lt01_options *opt);

/* Load the model from model_dir (layout: models/README.md). NULL on failure, see lt01_create_error().
   While loading (and in lt01_destroy) the process's stdout is sent to stderr: the vendor runtime prints notices there
   (LT01_KEEP_STDOUT=1 to keep them on stdout). */
LT01_API lt01_engine *lt01_create(const char *model_dir, const lt01_options *opt);
LT01_API const char *lt01_create_error(void);   /* last lt01_create failure (thread-local) */
LT01_API void lt01_destroy(lt01_engine *e);

LT01_API int lt01_get_info(lt01_engine *e, lt01_info *info);
LT01_API const char *lt01_last_error(lt01_engine *e);

/* New session: KV back to the prefix, positions and time restart, token queue cleared. */
LT01_API int lt01_reset(lt01_engine *e);

/* Append n mono float samples (16 kHz, clipped to [-1, 1]) and run every clock they complete.
   Returns the number of new tokens queued (read them with lt01_read_tokens), or < 0. */
LT01_API int lt01_feed(lt01_engine *e, const float *pcm, int n);

/* End of input: append tail_tokens clocks of silence (-1 = default: 5 at 160 ms, 7 at 80 ms) and run them.
   Returns the number of new tokens queued, or < 0. After this only lt01_read_tokens / lt01_reset are valid. */
LT01_API int lt01_finish(lt01_engine *e, int tail_tokens);

/* Pop up to cap queued tokens (oldest first). Returns how many were written. */
LT01_API int lt01_read_tokens(lt01_engine *e, lt01_token *out, int cap);

/* UTF-8 bytes of a token (0 bytes for the no-text tokens). A token may hold part of a multi-byte character: decode
   incrementally across tokens. Returns the byte count (may exceed cap: then only cap bytes are written), or < 0. */
LT01_API int lt01_token_bytes(lt01_engine *e, int32_t id, char *buf, int cap);

/* Soft reset (mechanism; the caller decides when): LM context back to the prefix (fresh positions), then the cached
   audio rows with audio_t > replay_from_s (at most replay_max_s before the next clock) are replayed so the model
   re-hears them. The audio tower and the audio stream are untouched; feeding continues normally afterwards.
   Valid once the first token is out (LT01_ERR_STATE before). Returns the number of new tokens queued by the replay,
   or < 0. */
LT01_API int lt01_soft_reset(lt01_engine *e, double replay_from_s);

/* Full [horizon][class] softmax of the semantic VAD heads after the last token (semantic_vad must be on). */
LT01_API int lt01_eot_probs(lt01_engine *e, float out[LT01_EOT_HORIZONS][LT01_EOT_CLASSES]);

LT01_API int lt01_get_stats(lt01_engine *e, lt01_stats *st);

#ifdef __cplusplus
}
#endif

#endif /* LIVE_TRANSCRIBE_01_H */
