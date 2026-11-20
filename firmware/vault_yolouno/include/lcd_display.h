#pragma once

#include "sensor_snapshot.h"
#include "vault_state.h"

void lcd_display_begin();
void lcd_display_update(const SensorSnapshot& sensors, const VaultStatus& status);
void lcd_display_wake();

// Manual navigation across LCD display pages (via IR remote)
void lcd_display_next_page();
void lcd_display_prev_page();

// Transient notification popup (Method / Action feedback for ~1.2s)
void lcd_show_notification(const char* line0, const char* line1, uint32_t durationMs = 1200);
