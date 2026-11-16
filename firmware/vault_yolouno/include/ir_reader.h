#pragma once
#include <Arduino.h>

void ir_reader_init();
void ir_reader_tick();

// Retourne le nombre de chiffres saisis (0 à 4) pour l'affichage masqué sur le LCD
uint8_t ir_reader_get_pin_count();

// Indique si le dernier code saisi était faux (pour affichage erreur temporaire)
bool ir_reader_is_pin_error();
