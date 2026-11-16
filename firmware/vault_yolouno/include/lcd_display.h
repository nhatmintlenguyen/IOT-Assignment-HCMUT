#pragma once

#include "sensor_snapshot.h"
#include "vault_state.h"

void lcd_display_begin();
void lcd_display_update(const SensorSnapshot& sensors, const VaultStatus& status);

// Navigation manuelle dans les pages d'affichage (via télécommande IR)
void lcd_display_next_page();
void lcd_display_prev_page();
