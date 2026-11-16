#pragma once

#include "sensor_snapshot.h"
#include "vault_state.h"

void lcd_display_begin();
void lcd_display_update(const SensorSnapshot& sensors, const VaultStatus& status);
