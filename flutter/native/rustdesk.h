#ifndef VIPER_NATIVE_RUSTDESK_H
#define VIPER_NATIVE_RUSTDESK_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// Native runner entrypoints exported by src/flutter.rs. These are not FRB wire APIs.
bool rustdesk_core_main(void);
void handle_applicationShouldOpenUntitledFile(void);
const uint8_t *session_get_rgba(const char *session_uuid_str, uintptr_t display);

#ifdef __cplusplus
}
#endif

#endif
