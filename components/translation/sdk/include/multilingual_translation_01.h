#ifndef MULTILINGUAL_TRANSLATION_01_H
#define MULTILINGUAL_TRANSLATION_01_H
#include <stddef.h>
#include <stdint.h>
#if defined(_WIN32)
#define MT01_API __declspec(dllexport)
#else
#define MT01_API __attribute__((visibility("default")))
#endif
#define MT01_VERSION "0.1.0"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct mt01_engine mt01_engine;
enum { MT01_OK = 0, MT01_ARG = -1, MT01_MODEL = -2, MT01_NPU = -3,
       MT01_STATE = -4, MT01_INTERNAL = -5, MT01_CANCELLED = -6 };
enum { MT01_IDLE = 0, MT01_PREPARED, MT01_RUNNING, MT01_DONE, MT01_STOPPED, MT01_FAILED };
/* Prompt budget, including instructions: 32..2048 tokens; default 512. */
typedef struct { uint32_t struct_size; uint32_t max_input_tokens; } mt01_options;
typedef struct {
    uint32_t struct_size;
    uint32_t state;
    uint64_t prompt_tokens;
    uint64_t generated_tokens;
    double init_ms;
    double first_token_ms;
    double generation_ms;
    double tokens_per_second;
} mt01_stats;
typedef void (*mt01_notify)(void *user);
/* Architecture-neutral synchronous engine over the installed AidGen runtime.
 * Sequence: create -> start -> generate -> read_text -> get_stats; repeat; destroy.
 * generate blocks and notifies on queued output. read_text may be called from notify.
 * The application supplies any worker thread, timeout and transport. No worker thread
 * is created by this library. There is one engine per process (vendor restriction).
 * Only abort, read_text and get_stats may run concurrently with generate. Never call
 * abort from notify; request it from a separate application thread. Repeat abort if
 * cancellation races with start-up. destroy requires generate and readers to finish.
 * UTF-8 output is bytes: reads may split a character; decode incrementally.
 * Sampling is greedy with repetition penalty 1.0; each start clears conversation
 * history. No stochastic seed is used. Vendor arithmetic may differ across packages.
 * Strings returned by error functions remain owned by the library.
 */
MT01_API const char *mt01_version(void);
MT01_API mt01_options mt01_default_options(void);
MT01_API mt01_engine *mt01_create(const char *model_dir, const mt01_options *options);
MT01_API void mt01_destroy(mt01_engine *engine);
MT01_API const char *mt01_create_error(void);
MT01_API int mt01_create_error_code(void);
MT01_API const char *mt01_last_error(mt01_engine *engine);
/* Languages: zh en ja ko fr de es ar th. Source and target must differ.
 * start validates UTF-8, language codes and the actual tokenizer budget.
 */
/* Return exact prompt token count, or a negative error, without preparing generation.
 * This may exceed max_input_tokens. Call only when no translation is prepared/running.
 */
MT01_API int mt01_count_prompt_tokens(mt01_engine *engine, const char *utf8, const char *source, const char *target);
MT01_API int mt01_start(mt01_engine *engine, const char *utf8, const char *source, const char *target);
MT01_API int mt01_generate(mt01_engine *engine, mt01_notify notify, void *user);
/* Return bytes copied, zero if queue empty, or a negative error. Does not add NUL. */
MT01_API int mt01_read_text(mt01_engine *engine, char *output, size_t capacity);
MT01_API int mt01_abort(mt01_engine *engine);
MT01_API int mt01_get_stats(mt01_engine *engine, mt01_stats *stats);
/* JSON static capabilities; returns required bytes including NUL if buffer is small. */
MT01_API int mt01_get_info(mt01_engine *engine, char *output, size_t capacity);
#ifdef __cplusplus
}
#endif
#endif
