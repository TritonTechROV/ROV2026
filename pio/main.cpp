void setup() {
  Serial.begin(115200);
}
void loop() {
  if(Serial.available()){
    String response = Serial.readStringUntil('\n');
    response.trim();
    if(response == "ping"){
      Serial.println("pong");
    }
  }
}
