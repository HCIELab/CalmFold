#include <Arduino.h>
#include "EmotiBit.h"
#include <WiFi.h>
#include <WiFiUdp.h>

#define SerialUSB SERIAL_PORT_USBVIRTUAL // Required to work in Visual Micro / Visual Studio IDE
const uint32_t SERIAL_BAUD = 2000000; //115200

EmotiBit emotibit;
const size_t dataSize = EmotiBit::MAX_DATA_BUFFER_SIZE;
float data[dataSize];


// ---------------------------------------------------------
// DRV8833 two-motor control
// ---------------------------------------------------------

// GPIO 16 connects to BOTH AIN1 and BIN1.
// GPIO 17 connects to BOTH AIN2 and BIN2.
const int MOTOR_IN1 = 16;
const int MOTOR_IN2 = 17;

// Both motors run for this long after receiving "M".
const unsigned long MOTOR_DURATION_MS = 1000;

bool motorsRunning = false;
unsigned long motorsStartTime = 0;


// ---------------------------------------------------------
// UDP motor commands
// ---------------------------------------------------------

WiFiUDP motorUdp;
const uint16_t MOTOR_UDP_PORT = 4210;
bool motorUdpStarted = false;


void stopMotors()
{
	digitalWrite(MOTOR_IN1, LOW);
	digitalWrite(MOTOR_IN2, LOW);

	motorsRunning = false;
}


void startMotors()
{
	// Both DRV8833 channels receive the same signals because:
	// GPIO 16 -> AIN1 and BIN1
	// GPIO 17 -> AIN2 and BIN2
	digitalWrite(MOTOR_IN1, HIGH);
	digitalWrite(MOTOR_IN2, LOW);

	motorsRunning = true;
	motorsStartTime = millis();

	Serial.println("Both motors started");
}


void updateMotorUdp()
{
	// Start the UDP listener only after the EmotiBit has connected to Wi-Fi.
	if (!motorUdpStarted && WiFi.status() == WL_CONNECTED)
	{
		if (motorUdp.begin(MOTOR_UDP_PORT))
		{
			motorUdpStarted = true;

			Serial.print("Motor UDP listener started at ");
			Serial.print(WiFi.localIP());
			Serial.print(":");
			Serial.println(MOTOR_UDP_PORT);
		}
	}

	// Stop listening safely if Wi-Fi disconnects.
	if (motorUdpStarted && WiFi.status() != WL_CONNECTED)
	{
		motorUdp.stop();
		motorUdpStarted = false;
		stopMotors();

		Serial.println("Motor UDP listener stopped: Wi-Fi disconnected");
	}

	if (motorUdpStarted)
	{
		const int packetSize = motorUdp.parsePacket();

		if (packetSize > 0)
		{
			char commandBuffer[8];

			const int bytesRead = motorUdp.read(
				commandBuffer,
				sizeof(commandBuffer) - 1
			);

			if (bytesRead > 0)
			{
				commandBuffer[bytesRead] = '\0';
				const char command = commandBuffer[0];

				if (command == 'M')
				{
					startMotors();
				}
				else if (command == 'S')
				{
					stopMotors();
					Serial.println("Both motors stopped");
				}
			}
		}
	}

	// Automatically stop both motors after the selected duration.
	if (
		motorsRunning &&
		millis() - motorsStartTime >= MOTOR_DURATION_MS
	)
	{
		stopMotors();
		Serial.println("Both motors automatically stopped");
	}
}


void onShortButtonPress()
{
	// toggle wifi on/off
	if (emotibit.getPowerMode() == EmotiBit::PowerMode::NORMAL_POWER)
	{
		emotibit.setPowerMode(EmotiBit::PowerMode::WIRELESS_OFF);
		Serial.println("PowerMode::WIRELESS_OFF");
	}
	else
	{
		emotibit.setPowerMode(EmotiBit::PowerMode::NORMAL_POWER);
		Serial.println("PowerMode::NORMAL_POWER");
	}
}


void onLongButtonPress()
{
	// Ensure both motors are off before the EmotiBit sleeps.
	stopMotors();
	emotibit.sleep();
}


void setup()
{
	Serial.begin(SERIAL_BAUD);
	Serial.println("Serial started");
	delay(2000);	// short delay to allow user to connect to serial, if desired

	// Capture the calling ino into firmware_variant information
	String inoFilename = __FILE__;  // returns absolute path of ino file
	inoFilename.replace("/","\\");  // conform to standard directory separator
	// extract filename only if directory separator found in absolute path
	if(inoFilename.lastIndexOf("\\") != -1)
	{
		inoFilename = inoFilename.substring((inoFilename.lastIndexOf("\\")) + 1,(inoFilename.indexOf(".")));
	}

	// Keep the original EmotiBit initialization unchanged.
	emotibit.setup(inoFilename);

	// Initialize only the two confirmed motor-control pins.
	pinMode(MOTOR_IN1, OUTPUT);
	pinMode(MOTOR_IN2, OUTPUT);
	stopMotors();

	// Attach callback functions
	emotibit.attachShortButtonPress(&onShortButtonPress);
	emotibit.attachLongButtonPress(&onLongButtonPress);
}


void loop()
{
	// Keep the original EmotiBit update call first.
	emotibit.update();

	// Check for UDP motor commands without blocking sensing.
	updateMotorUdp();

	size_t dataAvailable = emotibit.readData(EmotiBit::DataType::PPG_GREEN, &data[0], dataSize);
	if (dataAvailable > 0)
	{
		// Hey cool, I got some data! Maybe I can light up my shoes whenever I get excited!

		// print the data to view in the serial plotter
		bool printData = false;
		if (printData)
		{
			for (size_t i = 0; i < dataAvailable && i < dataSize; i++)
			{
				// Note that dataAvailable can be larger than dataSize
				Serial.println(data[i]);
			}
		}
	}
}
