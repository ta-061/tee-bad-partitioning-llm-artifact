#ifndef TEE_INTERNAL_API_H
#define TEE_INTERNAL_API_H

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#ifndef __maybe_unused
#define __maybe_unused __attribute__((unused))
#endif

typedef uint32_t TEE_Result;

#define TEE_SUCCESS 0x00000000U
#define TEE_ERROR_BAD_PARAMETERS 0xFFFF0006U

#define TEE_PARAM_TYPE_NONE 0U
#define TEE_PARAM_TYPE_VALUE_INPUT 1U
#define TEE_PARAM_TYPE_VALUE_OUTPUT 2U
#define TEE_PARAM_TYPE_VALUE_INOUT 3U
#define TEE_PARAM_TYPE_MEMREF_INPUT 5U
#define TEE_PARAM_TYPE_MEMREF_OUTPUT 6U
#define TEE_PARAM_TYPE_MEMREF_INOUT 7U

#define TEE_PARAM_TYPES(t0, t1, t2, t3) \
	((uint32_t)(t0) | ((uint32_t)(t1) << 4) | ((uint32_t)(t2) << 8) | ((uint32_t)(t3) << 12))

typedef struct {
	void *buffer;
	size_t size;
} TEE_MemRef;

typedef struct {
	uint32_t a;
	uint32_t b;
} TEE_Value;

typedef union {
	TEE_MemRef memref;
	TEE_Value value;
} TEE_Param;

void *TEE_Malloc(size_t size, uint32_t hint);
void TEE_Free(void *buffer);
void TEE_MemMove(void *dest, const void *src, size_t size);
int TEE_MemCompare(const void *buffer1, const void *buffer2, size_t size);
void TEE_Wait(uint32_t timeout);

#define DMSG(...) ((void)0)
#define IMSG(...) ((void)0)
#define EMSG(...) ((void)0)

#endif
