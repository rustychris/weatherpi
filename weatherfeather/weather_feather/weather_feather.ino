/*

 Adapted from the ConnectWithWPA example sketch.
  original credits for that example:
   created 13 July 2010
   by dlf (Metodo2 srl)
   modified 31 May 2012
   by Tom Igoe
 */

#include <elapsedMillis.h>
#include <SPI.h>
#include <WiFi101.h>

#include "credentials.h" 
#include "sensors.h"
#include "publish.h"

char ssid[] = SECRET_SSID;        // your network SSID (name)
char pass[] = SECRET_PASS;    // your network password (use for WPA, or use as key for WEP)
int status = WL_IDLE_STATUS;     // the WiFi radio's status

bool ensure_connection();

void setup() {
  //Configure pins for Adafruit ATWINC1500 Feather
  WiFi.setPins(8,7,4,2);

  //Initialize serial and wait for port to open:
  Serial.begin(9600);
  // For headless operation skip this
  // while (!Serial) {
  //   ; // wait for serial port to connect. Needed for native USB port only
  // }

  // check for the presence of the shield:
  if (WiFi.status() == WL_NO_SHIELD) {
    Serial.println("Check pins - no WiFi shield detected");
    // don't continue:
    while (true);
  }

  if ( ensure_connection() ) {
    // Seems to have made less stable
    // WiFi.lowPowerMode();

    // you're connected now, so print out the data:
    Serial.print("Connected to the network");
    printCurrentNet();
    printWiFiData();
  } else {
    Serial.println("WiFi failed to connect.  Will try later");
  }

  sensor_setup();
}

#define CONNECT_RETRIES 10

bool ensure_connection() {
  // for debugging -- disconnect every time
  // with the feather m0 with ufl connector, and now compiling on my linux laptop,
  // i now *have* to do this, or it will fail after 2-3 requests.
  Serial.println("Trying power cycle to wifi");
  WiFi.end();
  Serial.println(" -- sleep 10 seconds");
  delay(10*1000);
  Serial.println(" -- now connect");
  
  status = WiFi.status();
  
  for (int retries=10;
       (status!=WL_CONNECTED) && (retries>=0);
       retries-- ) {
    Serial.print("Attempting to connect to WPA SSID: ");
    Serial.println(ssid);
    // Connect to WPA/WPA2 network:
    status = WiFi.begin(ssid, pass);
  
    for(int secs=0;secs<20;secs++) {
      status=WiFi.status();
      if (status==WL_CONNECTED) {
        Serial.println("Wifi connected!");
        break;
      } else if (status==WL_IDLE_STATUS) {
        Serial.println("... Wifi connecting ");
        delay(500);
      } else if (status==WL_CONNECT_FAILED) {
        Serial.println(" FAILED");
        break; 
      }      
    }

    if ( retries<= 1 ) {
      Serial.println("Trying power cycle to wifi");
      WiFi.end();
      Serial.println(" -- sleep 20 seconds");
      delay(20*1000);
      Serial.println(" -- now try again");
      retries=10; // reset the count
    }
  }
  return status==WL_CONNECTED;
}

void loop() {
  int delay_ms=300*1000;
  //int delay_ms=10*1000; // testing

  // check the network connection once every 10 seconds:
  publish_init();
  sensor_loop();
  Serial.println(url);

  // possibly reconnect
  if ( ensure_connection() ) {
    publish_push();
  } else {
    Serial.println("No WiFi - will try again later");
  }

  // Wait 10seconds at a time, up to 5 minutes
  elapsedMillis elapsed;
  elapsed=0;
  while(elapsed<delay_ms) {
    Serial.print("Waiting ");
    Serial.println(elapsed/1000);
    delay(10000);
  }
}

void printWiFiData() {
  // print your WiFi shield's IP address:
  IPAddress ip = WiFi.localIP();
  Serial.print("IP Address: ");
  Serial.println(ip);

  // print your MAC address:
  byte mac[6];
  WiFi.macAddress(mac);
  Serial.print("MAC address: ");
  Serial.print(mac[5], HEX);
  Serial.print(":");
  Serial.print(mac[4], HEX);
  Serial.print(":");
  Serial.print(mac[3], HEX);
  Serial.print(":");
  Serial.print(mac[2], HEX);
  Serial.print(":");
  Serial.print(mac[1], HEX);
  Serial.print(":");
  Serial.println(mac[0], HEX);

}

void printCurrentNet() {
  // print the SSID of the network you're attached to:
  Serial.print("SSID: ");
  Serial.println(WiFi.SSID());

  // print the MAC address of the router you're attached to:
  byte bssid[6];
  WiFi.BSSID(bssid);
  Serial.print("BSSID: ");
  Serial.print(bssid[5], HEX);
  Serial.print(":");
  Serial.print(bssid[4], HEX);
  Serial.print(":");
  Serial.print(bssid[3], HEX);
  Serial.print(":");
  Serial.print(bssid[2], HEX);
  Serial.print(":");
  Serial.print(bssid[1], HEX);
  Serial.print(":");
  Serial.println(bssid[0], HEX);

  // print the received signal strength:
  long rssi = WiFi.RSSI();
  Serial.print("signal strength (RSSI):");
  Serial.println(rssi);

  // print the encryption type:
  byte encryption = WiFi.encryptionType();
  Serial.print("Encryption Type:");
  Serial.println(encryption, HEX);
  Serial.println();
}

// Currently runs for a while then hangs, anywhere from 5 minutes to a day
// 1. Disconnect/reconnect wifi for each sample?
// 2. Run with console attached, see where it stops
// 3. When frozen, probe board -- not sure what to look for though.
// 4. Sequence the wifi and the pms5003 so that these two current 
//    draws are not simultaneous
