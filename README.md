# CalmFold
UIST 2026 Student Innovation Contest

EmotiBit EDA-Triggered Two-Motor System

This project uses live **EmotiBit EDA data** to detect an increase in physiological arousal and activate **two DC micromotors** simultaneously through a **DRV8833 dual motor driver**.

This README assumes the EmotiBit has already been set up and can stream data using the official [EmotiBit Getting Started guide](https://github.com/EmotiBit/EmotiBit_Docs/blob/master/Getting_Started.md#next-steps-connecting-to-emotibit-and-streaming-emotibit-data). The EmotiBit and host computer must be on the same Wi-Fi network.

## Hardware

* EmotiBit + compatible Feather
* Adafruit DRV8833 dual motor driver
* 2× **Vybronics VZ4SL2A0000003** DC micromotors
* Male-to-female jumper wires
* EmotiBit battery
* Computer running EmotiBit Oscilloscope and Python

Motor:
https://www.digikey.com/en/products/detail/vybronics-inc/VZ4SL2A0000003/7732312

## Files

Use these two files:

```text
EmotiBit_stock_firmware_two_motors.ino
emotibit_eda_two_motors.py
```

The Python script receives live EDA, detects an increase relative to the user's recent baseline, ignores invalid EDA readings of `10000` or higher, and sends a UDP motor command to the EmotiBit.

## Wiring

Each motor uses a separate DRV8833 output channel.

```text
EmotiBit Feather          DRV8833

GPIO 16  ──────────────── AIN1
    └──────────────────── BIN1

GPIO 17  ──────────────── AIN2
    └──────────────────── BIN2

GND      ──────────────── GND
```

Motor connections:

```text
DRV8833              Motor

AOUT1 ───────────── Motor 1 wire 1
AOUT2 ───────────── Motor 1 wire 2

BOUT1 ───────────── Motor 2 wire 1
BOUT2 ───────────── Motor 2 wire 2
```

GPIO 16 controls both `AIN1` and `BIN1`, while GPIO 17 controls both `AIN2` and `BIN2`. This causes both DRV8833 channels to receive the same command, so both motors run simultaneously.

Male-to-female jumper wires were used for the Feather-to-DRV8833 connections.

If one motor spins in the wrong physical direction, reverse that motor's two output wires.

## 1. Upload the Modified EmotiBit Firmware

Use:

```text
EmotiBit_stock_firmware_two_motors.ino
```

This firmware preserves normal EmotiBit operation while adding UDP motor control.

The important settings are:

```cpp
const int MOTOR_IN1 = 16;
const int MOTOR_IN2 = 17;

const unsigned long MOTOR_DURATION_MS = 1000;
const uint16_t MOTOR_UDP_PORT = 4210;
```

When the firmware receives `M`, both motors run for **1 second**. When it receives `S`, both motors stop.

After uploading, open the serial monitor. Once Wi-Fi connects, the firmware prints something similar to:

```text
Motor UDP listener started at 172.20.10.7:4210
```

Record the IP address.

## 2. Configure EmotiBit Oscilloscope

Connect to the EmotiBit and start streaming data.

In **EmotiBit Oscilloscope, make sure `OSC Data` is checked** so the live EDA data is forwarded to the Python script.

```text
OSC Data:    CHECKED
OSC address: /EmotiBit/0/EDA
IP:          127.0.0.1
Port:        12345
```

If `OSC Data` is not checked, the Python script will not receive EDA measurements.

## 3. Install Python Dependencies

```bash
pip install numpy python-osc
```

## 4. Configure the Python Script

Open:

```text
emotibit_eda_two_motors.py
```

Change:

```python
MOTOR_IP = "172.20.10.7"
```

to the IP address printed by your EmotiBit.

The remaining communication settings should be:

```python
OSC_IP = "127.0.0.1"
OSC_PORT = 12345
EDA_ADDRESS = "/EmotiBit/0/EDA"

MOTOR_PORT = 4210
```

## 5. Position the EDA Sensor

Before running the detector, put on the EmotiBit and make sure the **EDA electrodes are flush against the skin with consistent contact**.

Poor or intermittent skin contact can make the initial baseline unreliable.

Once the sensor is positioned correctly, keep the placement consistent during calibration and use.

## 6. Run and Calibrate

Make sure:

1. The EmotiBit is streaming data.
2. **`OSC Data` is checked** in EmotiBit Oscilloscope.
3. The **EDA electrodes are flush against the skin**.
4. The Python script contains the correct EmotiBit IP address.

Then run:

```bash
python3 emotibit_eda_two_motors.py
```

The detector first collects approximately **22 seconds** of data:

```text
20 s baseline + 2 s recent window
```

During this period:

```text
Calibrating: ...
```

will appear in the terminal.

**Keep the EDA sensor flush against the skin and remain relatively still during calibration.** Avoid adjusting the EmotiBit or electrodes until calibration is complete, since changes in electrode contact can cause large changes in the EDA signal.

After calibration, the script continuously compares the newest EDA data against the previous baseline.

## EDA Trigger

The final detection settings are:

```python
BASELINE_SECONDS = 20
RECENT_SECONDS = 2

Z_THRESHOLD = 2.5
MIN_EDA_CHANGE = 0.005
REQUIRED_CONSECUTIVE_SAMPLES = 8

COOLDOWN_SECONDS = 15
```

A motor activation occurs when the recent EDA level:

1. increases by at least `0.005`,
2. is at least `2.5` baseline standard deviations above baseline, and
3. remains above the threshold for 8 consecutive samples.

When triggered, Python sends `M` to the EmotiBit over UDP, and both motors activate simultaneously for one second.

The `15 s` cooldown prevents repeated activations from the same sustained EDA increase.

## Stopping

Press:

```text
Control-C
```

to stop the Python program.

Before exiting, the script sends `S` to stop both motors.

## System Flow

```text
EDA electrodes
[flush with skin]
      │
      ▼
   EmotiBit
      │
      │ Wi-Fi
      ▼
EmotiBit Oscilloscope
[OSC Data checked]
      │
      │ /EmotiBit/0/EDA
      ▼
Python EDA detector
      │
      │ UDP "M"
      ▼
EmotiBit Feather
      │
 GPIO 16 / 17
      ▼
    DRV8833
   ┌────┴────┐
   ▼         ▼
Motor 1    Motor 2
```

## Troubleshooting

**Python receives no EDA:** make sure the EmotiBit is streaming and **`OSC Data` is checked** in EmotiBit Oscilloscope.

**EDA signal is unstable or jumps during calibration:** make sure the EDA electrodes are **flush against the skin**, avoid moving the sensor, and restart the Python script to recalibrate after fixing the contact.

**EDA is streaming but motors do not run:** verify `MOTOR_IP` matches the IP printed by the EmotiBit, both devices are on the same Wi-Fi network, and both the firmware and Python script use UDP port `4210`.

**Only one motor runs:** check that Motor 1 is on `AOUT1/AOUT2` and Motor 2 is on `BOUT1/BOUT2`, and verify GPIO 16 reaches both `AIN1/BIN1` and GPIO 17 reaches both `AIN2/BIN2`.

**EDA displays `10000`:** the Python script ignores values at or above `10000` so they do not falsely trigger the motors.

**Need a longer motor activation:** change:

```cpp
const unsigned long MOTOR_DURATION_MS = 1000;
```

For example, `2000` runs the motors for two seconds. Re-upload the firmware after changing it.
