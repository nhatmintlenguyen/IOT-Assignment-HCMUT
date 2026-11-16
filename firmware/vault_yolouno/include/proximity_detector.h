#pragma once

struct ProximityResult {
    bool personNear;
    bool enteredRange;
};

ProximityResult update_proximity(float distanceCm, bool readingValid);
