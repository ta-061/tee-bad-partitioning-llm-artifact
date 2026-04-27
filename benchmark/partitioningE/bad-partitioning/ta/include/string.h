#ifndef TEE_ARTIFACT_STRING_H
#define TEE_ARTIFACT_STRING_H

#include <stddef.h>

size_t strlen(const char *s);
int strcmp(const char *s1, const char *s2);
int snprintf(char *str, size_t size, const char *format, ...);

#endif
