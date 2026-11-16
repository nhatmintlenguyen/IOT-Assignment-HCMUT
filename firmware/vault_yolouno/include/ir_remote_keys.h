#pragma once

#include <Arduino.h>

// Official IR Remote Mapping (NEC 38 kHz) for OhStem handheld remote
// Captured and verified on YoloUNO (Grove D6-D5, pin D5 = GPIO 8)

#define IR_KEY_0       0x16
#define IR_KEY_1       0x0C
#define IR_KEY_2       0x18
#define IR_KEY_3       0x5E
#define IR_KEY_4       0x08
#define IR_KEY_5       0x1C
#define IR_KEY_6       0x5A
#define IR_KEY_7       0x42
#define IR_KEY_8       0x52
#define IR_KEY_9       0x4A

#define IR_KEY_A       0x45
#define IR_KEY_B       0x46
#define IR_KEY_C       0x47 // Validate / Enter (Action de validation du code PIN)
#define IR_KEY_D       0x44 // Clear / Effacer
#define IR_KEY_E       0x43
#define IR_KEY_F       0x0D

#define IR_KEY_UP      0x40
#define IR_KEY_DOWN    0x19
#define IR_KEY_LEFT    0x07
#define IR_KEY_RIGHT   0x09
#define IR_KEY_CONFIG  0x15

// Convertit une commande hexadécimale en caractère ('0'-'9', 'A'-'F', ou '\0')
inline char ir_code_to_char(uint16_t command) {
    switch (command) {
        case IR_KEY_0: return '0';
        case IR_KEY_1: return '1';
        case IR_KEY_2: return '2';
        case IR_KEY_3: return '3';
        case IR_KEY_4: return '4';
        case IR_KEY_5: return '5';
        case IR_KEY_6: return '6';
        case IR_KEY_7: return '7';
        case IR_KEY_8: return '8';
        case IR_KEY_9: return '9';
        case IR_KEY_A: return 'A';
        case IR_KEY_B: return 'B';
        case IR_KEY_C: return 'C';
        case IR_KEY_D: return 'D';
        case IR_KEY_E: return 'E';
        case IR_KEY_F: return 'F';
        default:       return '\0';
    }
}
