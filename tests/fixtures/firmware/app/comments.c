// SPDX-License-Identifier: MIT
#include <stdint.h>

/** Doxygen on public API: allowed. */
uint32_t motor_rpm(void);

// bump the gain because the new motor overshoots
static uint32_t gain = 3U;

/* temporary hack until the encoder board is fixed */
static uint32_t offset = 7U;

// REF(RM0090 10.3.2): DMA2 is the only controller that does memory-to-memory
static const char *url = "http://example.com/not//a/comment";

// REF(): source missing
static const char slash = '/';

uint32_t motor_rpm(void) { return gain + offset + (uint32_t)slash; } // NOLINT(readability-x) vendor macro
