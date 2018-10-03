#include <elapsedMillis.h>
#include <Wire.h>
#include <SPI.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include "Adafruit_TSL2591.h"

#include "sensors.h"
#include "publish.h"

#define pmsSerial Serial1
// the SET input is connected to feather pin 5.  high or
// high-Z on this enables the sensor, pull low to disable.
#define pmsEnable 5 

// #define SEALEVELPRESSURE_HPA (1013.25)

Adafruit_BME280 bme; // I2C
Adafruit_TSL2591 tsl = Adafruit_TSL2591(2591); 

struct pms5003data {
  uint16_t framelen;
  uint16_t pm10_standard, pm25_standard, pm100_standard;
  uint16_t pm10_env, pm25_env, pm100_env;
  uint16_t particles_03um, particles_05um, particles_10um, particles_25um, particles_50um, particles_100um;
  uint16_t unused;
  uint16_t checksum;
};

struct pms5003data data;

void configureTLS2591();
void bme280_loop();
void tsl2591_loop(void);
void pms5003_loop(void);
boolean readPMSdata(Stream *s);

void sensor_setup() {
  bool status;
  
  // BME280 pressure, humidity, temperature
  status = bme.begin();  
  if (!status) {
    Serial.println("Could not find a valid BME280 sensor, check wiring!");
    while (1);
  }

  // TSL2591 Lux sensor
  if (tsl.begin())  {
    Serial.println(F("Found a TSL2591 sensor"));
    /* Configure the sensor */
    configureTLS2591();
  } else {
    Serial.println(F("No sensor found ... check your wiring?"));
    while (1);
  }

#ifdef pmsEnable
  pinMode(pmsEnable,OUTPUT);
  digitalWrite(pmsEnable,LOW);
#endif

  // PMS5003 Particulate sensor
  pmsSerial.begin(9600);
}


void bme280_loop() {
  float temp=bme.readTemperature();
  float press=bme.readPressure();
  float humid=bme.readHumidity();

  if ( 0 ) {
    Serial.print("Temperature = ");
    Serial.print(temp);
    Serial.println(" *C");

    Serial.print("Pressure = ");
    Serial.print(press/100.0F);
    Serial.println(" hPa");
    
    // Serial.print("Approx. Altitude = ");
    // Serial.print(bme.readAltitude(SEALEVELPRESSURE_HPA));
    // Serial.println(" m");
    
    Serial.print("Humidity = ");
    Serial.print(humid);
    Serial.println(" %");
    
    Serial.println();
  }

  temp=temp*1.8 + 32.0; // to Fahrenheit
  publish_value("temp1",temp,2);
  publish_value("pressure",press,1);
  publish_value("humidity",humid,1);
}


void sensor_loop(void) {
  bme280_loop();
  pms5003_loop();
  tsl2591_loop();
}

void tsl2591_loop(void)
{
  // More advanced data read example. Read 32 bits with top 16 bits IR, bottom 16 bits full spectrum
  // That way you can do whatever math and comparisons you want!
  float lux;
  uint32_t lum = tsl.getFullLuminosity();
  uint16_t ir, full;
  ir = lum >> 16;
  full = lum & 0xFFFF;
  // the second argument should be IR, but there are some weird faults
  // and that results in negative values often.  So cheat and just provide
  // a 0 there.
  lux=tsl.calculateLux(full, 0);

  if(false) {
    Serial.print(F("[ ")); Serial.print(millis()); Serial.print(F(" ms ] "));
    Serial.print(F("IR: ")); Serial.print(ir);  Serial.print(F("  "));
    Serial.print(F("Full: ")); Serial.print(full); Serial.print(F("  "));
    Serial.print(F("Visible: ")); Serial.print(full - ir); Serial.print(F("  "));
    Serial.print(F("Lux: ")); Serial.println(lux,6);
  }

  publish_value("lux",lux,2);
}

/**************************************************************************/
/*
    Configures the gain and integration time for the TSL2591
*/
/**************************************************************************/
void configureTLS2591(void)
{
  // You can change the gain on the fly, to adapt to brighter/dimmer light situations
  //tsl.setGain(TSL2591_GAIN_LOW);    // 1x gain (bright light)
  tsl.setGain(TSL2591_GAIN_MED);      // 25x gain
  //tsl.setGain(TSL2591_GAIN_HIGH);   // 428x gain
  
  // Changing the integration time gives you a longer time over which to sense light
  // longer timelines are slower, but are good in very low light situtations!
  //tsl.setTiming(TSL2591_INTEGRATIONTIME_100MS);  // shortest integration time (bright light)
  // tsl.setTiming(TSL2591_INTEGRATIONTIME_200MS);
  tsl.setTiming(TSL2591_INTEGRATIONTIME_300MS);
  // tsl.setTiming(TSL2591_INTEGRATIONTIME_400MS);
  // tsl.setTiming(TSL2591_INTEGRATIONTIME_500MS);
  // tsl.setTiming(TSL2591_INTEGRATIONTIME_600MS);  // longest integration time (dim light)

  /* Display the gain and integration time for reference sake */  
  Serial.println(F("------------------------------------"));
  Serial.print  (F("Gain:         "));
  tsl2591Gain_t gain = tsl.getGain();
  switch(gain)
  {
    case TSL2591_GAIN_LOW:
      Serial.println(F("1x (Low)"));
      break;
    case TSL2591_GAIN_MED:
      Serial.println(F("25x (Medium)"));
      break;
    case TSL2591_GAIN_HIGH:
      Serial.println(F("428x (High)"));
      break;
    case TSL2591_GAIN_MAX:
      Serial.println(F("9876x (Max)"));
      break;
  }
  Serial.print  (F("Timing:       "));
  Serial.print((tsl.getTiming() + 1) * 100, DEC); 
  Serial.println(F(" ms"));
  Serial.println(F("------------------------------------"));
  Serial.println(F(""));
}


    
void pms5003_loop() {
#ifdef pmsEnable
  elapsedMillis elapsed=0;
  Serial.print("Sampling PM sensor");
  digitalWrite(pmsEnable,HIGH);

  // manual says 30 seconds for stabilizing data.
  while (elapsed<30*1000) {
    Serial.print("."); 
    delay(1000);
  }
  Serial.println();
  Serial.println("PM sensor ready");
#endif

  if (readPMSdata(&pmsSerial)) {
    // reading data was successful!
    if(false) {
      Serial.println();
      // Serial.println("---------------------------------------");
      // Serial.println("Concentration Units (standard)");
      // Serial.print("PM 1.0: "); Serial.print(data.pm10_standard);
      // Serial.print("\t\tPM 2.5: "); Serial.print(data.pm25_standard);
      // Serial.print("\t\tPM 10: "); Serial.println(data.pm100_standard);
      Serial.println("---------------------------------------");
      Serial.println("Concentration Units (environmental)");
      Serial.print("PM 1.0: "); Serial.print(data.pm10_env);
      Serial.print("\t\tPM 2.5: "); Serial.print(data.pm25_env);
      Serial.print("\t\tPM 10: "); Serial.println(data.pm100_env);
      Serial.println("---------------------------------------");
      Serial.print("Particles > 0.3um / 0.1L air:"); Serial.println(data.particles_03um);
      Serial.print("Particles > 0.5um / 0.1L air:"); Serial.println(data.particles_05um);
      Serial.print("Particles > 1.0um / 0.1L air:"); Serial.println(data.particles_10um);
      Serial.print("Particles > 2.5um / 0.1L air:"); Serial.println(data.particles_25um);
      Serial.print("Particles > 5.0um / 0.1L air:"); Serial.println(data.particles_50um);
      Serial.print("Particles > 50 um / 0.1L air:"); Serial.println(data.particles_100um);
      Serial.println("---------------------------------------");
    }
    
    publish_value("pm1.0",data.pm10_env,1);
    publish_value("pm2.5",data.pm25_env,1);
    publish_value("pm10",data.pm100_env,1);
  }

#ifdef pmsEnable
  Serial.println("Disabling PM sensor");
  digitalWrite(pmsEnable,LOW);
#endif

}

boolean readPMSdata(Stream *s) {
  elapsedMillis timeElapsed;
  unsigned int max_elapsed=2000;
  bool ready=false;
  uint8_t buffer[32];
  uint8_t buff_count=0;
  uint16_t sum;
  uint16_t buffer_u16[15];

  // look for sufficient for only a limited amount of time
  while ( !ready && (timeElapsed < max_elapsed) ) {
    if (! s->available()) {
      delay(10);
      continue;
    }

    buffer[buff_count]=s->read();
    buff_count++;
    
    if ( buff_count==1 && buffer[0] != 0x42 ) {
      buff_count=0;
      continue;
    }

    if (buff_count==32) {
      // get checksum ready
      int8_t i;
      sum=0;
      for (i=0; i<30; i++) {
        sum += buffer[i];
      }
  
      // The data comes in endian'd, this solves it so it works on all platforms
      for (uint8_t i=0; i<15; i++) {
        buffer_u16[i] = buffer[2 + i*2 + 1];
        buffer_u16[i] += (buffer[2 + i*2] << 8);
      }
      
      // put it into a nice struct :)
      memcpy((void *)&data, (void *)buffer_u16, 30);

      if (sum == data.checksum) {
        ready=true;
        break;
      }
      // scan for another 0x42
      int8_t start;
      for(start=1;start<32;start++) {
        if ( buffer[start]==0x42 ) break;
      }
      Serial.print("Checksum failed - retraining ");
      Serial.print(start);
      Serial.println(" bytes ahead");
      
      // here start is either 32, or the index to the first
      // occurrence of 0x42.
      for(i=0;i<32-start;i++) {
        buffer[i]=buffer[start+i];
      }
      buff_count=32-start;
    }
  }
      
  if ( ! ready ) return false;


  /* debugging
  for (uint8_t i=2; i<32; i++) {
    Serial.print("0x"); Serial.print(buffer[i], HEX); Serial.print(", ");
  }
  Serial.println();
  */

  // success!
  return true;
}
