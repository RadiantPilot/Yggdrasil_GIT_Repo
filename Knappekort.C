#include <Wire.h>

#define I2C_ADDR 0x20  // Adresse RPi bruker for å hente data

const uint8_t buttonPins[5] = {PIN_PA4, PIN_PA5, PIN_PA6, PIN_PA7, PIN_PB3};
volatile uint8_t buttonState = 0;

void setup() {
  for (uint8_t i = 0; i < 5; i++) {
    pinMode(buttonPins[i], INPUT_PULLUP);
  }
  Wire.begin(I2C_ADDR);
  Wire.onRequest(sendButtons);
}

void loop() {
  uint8_t state = 0;
  for (uint8_t i = 0; i < 5; i++) {
    if (digitalRead(buttonPins[i]) == LOW) {  // pullup = aktiv lav
      state |= (1 << i);
    }
  }
  buttonState = state;
  delay(10);  // enkel debouncing
}

void sendButtons() {
  Wire.write(buttonState);
}