#include "Arduino.h"
#include "elapsedMillis.h"

#include "publish.h"
#include "credentials.h"
#include <WiFi101.h>

WiFiClient client;

#define URL_MAX_LEN 2048
char url[URL_MAX_LEN];
char *dtostrf(double val, int width, unsigned int prec, char *sout);

// url should be INPUT_URL,
// a GET parameters for privet_key=INPUT_KEY
//  humidity temp1 pressure, lux, pm1.0, pm2.5, pm10


void publish_init(void) {
  strcpy(url,PUB_PATH);
  strcat(url,"?");
  strcat(url,"private_key=");
  strcat(url,INPUT_KEY);
}

void publish_push(void) {
  // close any connection before send a new request.
  // This will free the socket on the WiFi shield
  client.stop();

  // if there's a successful connection:
  if (client.connect(PUB_SERVER, PUB_PORT)) {
    Serial.println("connecting to web server...");
    
    // send the HTTP GET request:
    client.print("GET ");
    client.print(url);
    client.println(" HTTP/1.1");
    
    client.print("Host: ");
    client.println(PUB_SERVER);
    
    client.println("User-Agent: ArduinoWiFi/1.1");
    client.println("Connection: close");
    client.println();


    // if there's incoming data from the net connection.
    // send it out the serial port.  This is for debugging
    // purposes only:
    elapsedMillis elapsed=0;
    while (elapsed<10000) {
      if ( client.available()) {
        char c = client.read();
        // This gets annoying on the console.
        // Serial.write(c);
      } else {
        delay(100);
      }
    }
  }
  else {
    // if you couldn't make a connection:
    Serial.println("connection failed");
  }
}


void publish_value(const char *key,float value,int prec) {
  char buff[100];
  if ( url[strlen(url)-1] != '?' ) {
    strcpy(buff,"&");
  } else {
    buff[0]='\0';
  }
  
  strcat(buff,key);
  strcat(buff,"=");
  dtostrf(value,2+prec,prec,buff + strlen(buff));
  if ( strlen(buff) + strlen(url) < URL_MAX_LEN - 1 ) {
    strcat(url,buff);
  } else {
    Serial.println("Overrun in URL buffer");
  }
}


// paste from http://forum.arduino.cc/index.php?topic=368720.0

/*
  dtostrf - Emulation for dtostrf function from avr-libc
  Copyright (c) 2015 Arduino LLC.  All rights reserved.

  This library is free software; you can redistribute it and/or
  modify it under the terms of the GNU Lesser General Public
  License as published by the Free Software Foundation; either
  version 2.1 of the License, or (at your option) any later version.

  This library is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
  Lesser General Public License for more details.

  You should have received a copy of the GNU Lesser General Public
  License along with this library; if not, write to the Free Software
  Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
*/

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

char *dtostrf(double val, int width, unsigned int prec, char *sout)
{
  int decpt, sign, reqd, pad;
  const char *s, *e;
  char *p;
  s = fcvt(val, prec, &decpt, &sign);
  if (prec == 0 && decpt == 0) {
  s = (*s < '5') ? "0" : "1";
    reqd = 1;
  } else {
    reqd = strlen(s);
    if (reqd > decpt) reqd++;
    if (decpt == 0) reqd++;
  }
  if (sign) reqd++;
  p = sout;
  e = p + reqd;
  pad = width - reqd;
  if (pad > 0) {
    e += pad;
    while (pad-- > 0) *p++ = ' ';
  }
  if (sign) *p++ = '-';
  if (decpt <= 0 && prec > 0) {
    *p++ = '0';
    *p++ = '.';
    e++;
    while ( decpt < 0 ) {
      decpt++;
      *p++ = '0';
    }
  }    
  while (p < e) {
    *p++ = *s++;
    if (p == e) break;
    if (--decpt == 0) *p++ = '.';
  }
  if (width < 0) {
    pad = (reqd + width) * -1;
    while (pad-- > 0) *p++ = ' ';
  }
  *p = 0;
  return sout;
}
