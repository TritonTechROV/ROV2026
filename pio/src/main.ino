#include <Arduino.h>
#include <Servo.h>
#include <map>
#include <sstream>
#include <string>
#include <vector>

// TODO: Add similar logic for *servos*, not just the thrusters
// since there's only one servo, you can ignore the struct, 
// but the control logic is different, and the pwm frequencies are too

const int THRUST_MIN_PWM = 1100;  // Half reverse microseconds (full is 1000)
const int THRUST_MAX_PWM = 1900;  // Half forward microseconds (full is 2000)
const int THRUST_HALT_PWM = 1500; // Stopped

// TODO: do this for each thruster
const int FRONT_LEFT_ESC_PIN = 19; // or something
const int FRONT_RIGHT_ESC_PIN = 21;
const int MIDDLE_LEFT_ESC_PIN = 5;
const int MIDDLE_RIGHT_ESC_PIN = 18;
const int BACK_LEFT_ESC_PIN = 22;
const int BACK_RIGHT_ESC_PIN = 23;

struct Thruster {
  int pin;
  Servo *esc;
};

// This map lets you reference each thruster by short name.
std::map<std::string, Thruster> thrusterMap = {
    {"fl", {FRONT_LEFT_ESC_PIN, new Servo()}},  // front left
    {"fr", {FRONT_RIGHT_ESC_PIN, new Servo()}}, // front right
    {"ml", {MIDDLE_LEFT_ESC_PIN, new Servo()}}, // middle left
    {"mr", {MIDDLE_RIGHT_ESC_PIN, new Servo()}}, // middle right
    {"bl", {BACK_LEFT_ESC_PIN, new Servo()}},  // back left
    {"br", {BACK_RIGHT_ESC_PIN, new Servo()}}  // back right
};

// just splits a string into a vector of strings
std::vector<std::string> split(const std::string &str, char delimiter) {
  std::vector<std::string> tokens;
  std::string token;
  std::istringstream tokenStream(str);

  while (std::getline(tokenStream, token, delimiter)) {
    tokens.push_back(token);
  }

  return tokens;
}

void setup() {
  Serial.begin(115200);

  // Attaches each esc's pwm signal to the pin on esp32
  for (auto &entry : thrusterMap) {
    entry.second.esc->attach(entry.second.pin);
    entry.second.esc->writeMicroseconds(THRUST_HALT_PWM);
  }
  delay(100);
}

void loop() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim(); // gets rid of spaces and new line markers at the beginning and end of commands

    std::string commandStd = command.c_str(); // converts the Arduino string to a cpp string for parsing
    std::vector<std::string> commandComponents = split(commandStd, ' '); // splits the commad into separate components

    if (commandComponents.size() < 3) {
      Serial.println("Error: use 'set [esc] [pwm]'");
      return;
    }

    // This assumes the command is in the format "[instruction] [esc name]
    // [value]", e.g. "set fl 0.5" would make the esc go forward at 50% power
    if (commandComponents[0] == "set") {
      std::string thrusterName =
          commandComponents[1]; // get the ESC name from the command
      float input = std::stof(commandComponents[2]) * (THRUST_MAX_PWM - THRUST_MIN_PWM) / 2 + THRUST_HALT_PWM; // convert value to a float and scales to the pwm range
      int pwmValue =
          constrain(input, THRUST_MIN_PWM,
                    THRUST_MAX_PWM);

      if (thrusterMap.find(thrusterName) != thrusterMap.end()) {
        thrusterMap[thrusterName].esc->writeMicroseconds(pwmValue);
        Serial.println("OK");
      } else {
        Serial.println("Error: Thruster not found");
      }
    }
  }
}
