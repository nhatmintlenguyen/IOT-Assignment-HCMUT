#pragma once
#include <Arduino.h>

void ir_reader_init();
void ir_reader_tick();

// Returns the number of entered digits (0 to 4) for masked LCD display
uint8_t ir_reader_get_pin_count();

// Indicates if the last entered PIN was invalid (for temporary error display)
bool ir_reader_is_pin_error();

// Indicates if unlock was attempted without physical approach (distance >= 30cm)
bool ir_reader_is_presence_error();

// Indicates if the PIN was successfully updated
bool ir_reader_is_pin_success();

// Returns current PIN sub-state: 0=Normal, 1=ChangePrompt, 2=EnterOldPin, 3=EnterNewPin
uint8_t ir_reader_get_pin_state();
