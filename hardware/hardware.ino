//##################################################################################################################
//##                                      ELET2415 DATA ACQUISITION SYSTEM CODE                                   ##
//##                                                                                                              ##
//##################################################################################################################

// LIBRARY IMPORTS
#include <rom/rtc.h>
#include <math.h>  // https://www.tutorialspoint.com/c_standard_library/math_h.htm
#include <ctype.h>

// ADD YOUR IMPORTS HERE
#include <WiFi.h>
#include <PubSubClient.h>

#include <DHT.h>
#include <FastLED.h>

// ADD YOUR IMPORTS HERE

#ifndef _WIFI_H
#include <WiFi.h>
#endif

#ifndef STDLIB_H
#include <stdlib.h>
#endif

#ifndef STDIO_H
#include <stdio.h>
#endif

#ifndef ARDUINO_H
#include <Arduino.h>
#endif

#ifndef ARDUINOJSON_H
#include <ArduinoJson.h>
#endif

// PIN DEFINITIONS
#define DHT_PIN     18          // Safe GPIO
#define DHT_TYPE    DHT22
#define LED_PIN     23          // Addressable LED data pin
#define NUM_LEDS    7

// SENSOR & DEVICE OBJECTS
DHT dht(DHT_PIN, DHT_TYPE);

CRGB leds[NUM_LEDS];

// ===== Manual override state (keeps LED control from being overwritten by vUpdate auto-mode) =====
volatile bool manualOverride = false;
volatile unsigned long lastManualMs = 0;

int manualLeds = 7;
int manualBrightness = 255;
CRGB manualColor = CRGB(255,255,255);

const unsigned long MANUAL_TIMEOUT_MS = 15000; // 15s then revert to auto

// DEFINE VARIABLES
#define ARDUINOJSON_USE_DOUBLE      1

// DEFINE THE CONTROL PINS FOR THE DHT22

//hardware configuration was updated to ensure correct network and messaging behviour Wifi credentials were configured to allow ESP32 internet access.
//pub and sub topics were seperated to prevent message feedback, and multiple sub topics were correctly registered.

// MQTT CLIENT CONFIG
static const char* pubtopic      = "620171712";                    // Add your ID number here
static const char* subtopic[]    = {"620171712_sub","/elet2415"};  // Array of Topics(Strings) to subscribe to
static const char* mqtt_server   = "84.247.187.64";               // Broker IP address or Domain name as a String
static uint16_t mqtt_port        = 1883;

// WIFI CREDENTIALS
const char* ssid       = "Galaxy A15 4257";     // Add your Wi-Fi ssid
const char* password   = "12345876";            // Add your Wi-Fi password

// TASK HANDLES
TaskHandle_t xMQTT_Connect          = NULL;
TaskHandle_t xNTPHandle             = NULL;
TaskHandle_t xLOOPHandle            = NULL;
TaskHandle_t xUpdateHandle          = NULL;
TaskHandle_t xButtonCheckeHandle    = NULL;

// FUNCTION DECLARATION
void checkHEAP(const char* Name);   // RETURN REMAINING HEAP SIZE FOR A TASK
void initMQTT(void);                // CONFIG AND INITIALIZE MQTT PROTOCOL
unsigned long getTimeStamp(void);   // GET 10 DIGIT TIMESTAMP FOR CURRENT TIME
void callback(char* topic, byte* payload, unsigned int length);
void initialize(void);
bool publish(const char *topic, const char *payload); // PUBLISH MQTT MESSAGE(PAYLOAD) TO A TOPIC
void vButtonCheck( void * pvParameters );
void vUpdate( void * pvParameters );
bool isNumber(double number);

/* Declare your functions below */
double convert_Celsius_to_fahrenheit(double c);
double convert_fahrenheit_to_Celsius(double f);
double calculateHeatIndex(double Temp, double Humid);

/* Init class Instances for the DHT22 etcc */

//############### IMPORT HEADER FILES ##################
#ifndef NTP_H
#include "NTP.h"
#endif

#ifndef MQTT_H
#include "mqtt.h"
#endif

// Temporary Variables

void setup() {
  // 1. Start Serial IMMEDIATELY to stop the blank screen
  Serial.begin(115200);
  delay(1000); // Give the monitor time to open
  Serial.println("\n--- ESP32 RESTARTING ---");

  // 2. Initialize Hardware BEFORE Network
  dht.begin();
  FastLED.addLeds<WS2812, LED_PIN, GRB>(leds, NUM_LEDS);
  FastLED.clear();
  FastLED.show();
  Serial.println("LEDs and DHT Sensor Initialized.");

  // 3. Start the Network last
  Serial.println("Attempting WiFi Connection...");
  initialize();
}

void loop() {
  // put your main code here, to run repeatedly:
  vTaskDelay(1000 / portTICK_PERIOD_MS);
}

//####################################################################
//#                          UTIL FUNCTIONS                          #
//####################################################################
void vButtonCheck( void * pvParameters )  {
  configASSERT( ( ( uint32_t ) pvParameters ) == 1 );

  for( ;; ) {
    // Add code here to check if a button(S) is pressed
    // then execute appropriate function if a button is pressed

    vTaskDelay(200 / portTICK_PERIOD_MS);
  }
}

// -----------------------------
// UPDATED vUpdate (supports manual override)
// -----------------------------
void vUpdate( void * pvParameters )  {
  configASSERT( ( ( uint32_t ) pvParameters ) == 1 );

  for( ;; ) {

    // 1) Read Humidity and Temperature
    double h = dht.readHumidity();
    double t = dht.readTemperature();

    // Validate sensor readings
    if (!isNumber(t) || !isNumber(h)) {
      // If sensor fails, turn LEDs Yellow
      fill_solid(leds, NUM_LEDS, CRGB::Yellow);
      FastLED.show();
      Serial.println("DHT22 Error: Check wiring/resistor");
      vTaskDelay(2000 / portTICK_PERIOD_MS);
      continue;
    }

    // 2) Heat index calculation
    double tF  = convert_Celsius_to_fahrenheit(t);
    double hiF = calculateHeatIndex(tF, h);
    double hiC = convert_fahrenheit_to_Celsius(hiF);

    // 3) Local LED hardware control
    // If a control message was received recently, KEEP manual LEDs on.
    bool manualActive = manualOverride && (millis() - lastManualMs < MANUAL_TIMEOUT_MS);

    if (manualActive) {
      FastLED.setBrightness((uint8_t)manualBrightness);
      fill_solid(leds, NUM_LEDS, CRGB::Black);

      for (int i = 0; i < manualLeds && i < NUM_LEDS; i++) {
        leds[i] = manualColor;
      }
      FastLED.show();
    } else {
      manualOverride = false;

      // Auto-mode LEDs based on temperature
      if (t < 22.0) {
        fill_solid(leds, NUM_LEDS, CRGB::Blue);
      } else if (t <= 27.0) {
        fill_solid(leds, NUM_LEDS, CRGB::Green);
      } else {
        fill_solid(leds, NUM_LEDS, CRGB::Red);
      }
      FastLED.setBrightness(255);
      FastLED.show();
    }

    // 4) Wait for MQTT connection (don’t spam publish attempts)
    if (!mqtt.connected()) {
      Serial.printf("Waiting for MQTT... state=%d\n", mqtt.state());
      vTaskDelay(2000 / portTICK_PERIOD_MS);
      continue;
    }

    // 5) Build JSON payload
    StaticJsonDocument<256> doc;
    char msg[256];

    doc["id"]          = pubtopic;          // student id/topic
    doc["timestamp"]   = getTimeStamp();    // epoch timestamp
    doc["temperature"] = t;                 // Celsius
    doc["humidity"]    = h;                 // %
    doc["heatindex"]   = hiC;               // Celsius

    serializeJson(doc, msg);

    // 6) Publish and print result
    bool ok = publish(pubtopic, msg);
    Serial.printf("Publish to %s => %s | payload=%s\n", pubtopic, ok ? "OK" : "FAIL", msg);

    vTaskDelay(2000 / portTICK_PERIOD_MS); // DHT22 is slow, 2 seconds is safer
  }
}

unsigned long getTimeStamp(void) {
  // RETURNS 10 DIGIT TIMESTAMP REPRESENTING CURRENT TIME
  time_t now;
  time(&now); // Retrieve time[Timestamp] from system and save to &now variable
  return now;
}

// -----------------------------
// UPDATED callback (fixes variable order + enables manual override)
// -----------------------------
void callback(char* topic, byte* payload, unsigned int length) {
  // ############## MQTT CALLBACK  ######################################
  // RUNS WHENEVER A MESSAGE IS RECEIVED ON A TOPIC SUBSCRIBED TO

  Serial.printf("\nMessage received : ( topic: %s ) \n", topic );

  char *received = new char[length + 1] {0};
  for (unsigned int i = 0; i < length; i++) {
    received[i] = (char)payload[i];
  }

  // PRINT RECEIVED MESSAGE
  Serial.printf("Payload : %s \n", received);

  // CONVERT MESSAGE TO JSON
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, received);

  if (error) {
    Serial.print("deserializeJson() failed: ");
    Serial.println(error.c_str());
    delete[] received;
    return;
  }

  // PROCESS MESSAGE
  const char* type = doc["type"] | "";

  if (strcmp(type, "controls") == 0) {
    // 1) EXTRACT PARAMETERS
    int nodes      = doc["leds"] | doc["nodes"] | 0;
    int red        = doc["red"] | 0;
    int green      = doc["green"] | 0;
    int blue       = doc["blue"] | 0;
    int brightness = doc["brightness"] | 128;

    // If backend sends "color":{r,g,b,a}, allow that too (optional)
    if (doc["color"].is<JsonObject>()) {
      JsonObject c = doc["color"];
      red   = c["r"] | red;
      green = c["g"] | green;
      blue  = c["b"] | blue;
    }

    // 2) CLAMP VALUES
    if (nodes < 0) nodes = 0;
    if (nodes > NUM_LEDS) nodes = NUM_LEDS;

    if (red < 0) red = 0; if (red > 255) red = 255;
    if (green < 0) green = 0; if (green > 255) green = 255;
    if (blue < 0) blue = 0; if (blue > 255) blue = 255;

    if (brightness < 0) brightness = 0;
    if (brightness > 255) brightness = 255;

    // 3) SAVE MANUAL SETTINGS + ENABLE OVERRIDE
    manualOverride = true;
    lastManualMs = millis();
    manualLeds = nodes;
    manualBrightness = brightness;
    manualColor = CRGB((uint8_t)red, (uint8_t)green, (uint8_t)blue);

    // 4) APPLY LEDS IMMEDIATELY
    FastLED.setBrightness((uint8_t)manualBrightness);
    fill_solid(leds, NUM_LEDS, CRGB::Black);
    for (int i = 0; i < manualLeds && i < NUM_LEDS; i++) {
      leds[i] = manualColor;
    }
    FastLED.show();

    Serial.printf("Applied MANUAL LEDs: nodes=%d bright=%d rgb=(%d,%d,%d)\n",
                  manualLeds, manualBrightness, red, green, blue);
  }

  delete[] received;
}

bool publish(const char *topic, const char *payload){
  bool res = false;
  try{
    res = mqtt.publish(topic, payload);

    if(!res){
      res = false;
      throw false;
    }
  }
  catch(...){
    Serial.printf("\nError (%d) >> Unable to publish message\n", res);
  }
  return res;
}

//***** Complete the util functions below ******

double convert_Celsius_to_fahrenheit(double c){
  // CONVERTS INPUT FROM °C TO °F. RETURN RESULTS
  return (c * 9.0 / 5.0) + 32.0;
}

double convert_fahrenheit_to_Celsius(double f){
  // CONVERTS INPUT FROM °F TO °C. RETURN RESULT
  return (f - 32.0) * 5.0 / 9.0;
}

double calculateHeatIndex(double Temp, double Humid) {
  double T = Temp;
  double R = Humid;

  return -42.379
         + 2.04901523 * T
         + 10.14333127 * R
         - 0.22475541 * T * R
         - 0.00683783 * T * T
         - 0.05481717 * R * R
         + 0.00122874 * T * T * R
         + 0.00085282 * T * R * R
         - 0.00000199 * T * T * R * R;
}

bool isNumber(double number){
  char item[20];
  snprintf(item, sizeof(item), "%f\n", number);
  if( isdigit(item[0]) )
    return true;
  return false;
}
