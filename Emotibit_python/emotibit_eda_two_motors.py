from collections import deque
import socket
import time

import numpy as np
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer


# ---------------------------------------------------------
# EmotiBit / incoming OSC settings
# ---------------------------------------------------------

OSC_IP = "127.0.0.1"
OSC_PORT = 12345
EDA_ADDRESS = "/EmotiBit/0/EDA"

# Stock EmotiBit EDA sample rate is approximately 15 Hz.
SAMPLE_RATE = 15


# ---------------------------------------------------------
# Two-motor / outgoing Wi-Fi UDP settings
# ---------------------------------------------------------

# Replace this if the EmotiBit prints a different IP address.
MOTOR_IP = "172.20.10.7"

# Must match MOTOR_UDP_PORT in the rewritten .ino firmware.
MOTOR_PORT = 4210

motor_socket = socket.socket(
    socket.AF_INET,
    socket.SOCK_DGRAM,
)


# ---------------------------------------------------------
# Detection settings
# ---------------------------------------------------------

RECENT_SECONDS = 2
BASELINE_SECONDS = 20

RECENT_SAMPLES = RECENT_SECONDS * SAMPLE_RATE
BASELINE_SAMPLES = BASELINE_SECONDS * SAMPLE_RATE

Z_THRESHOLD = 2.5
MIN_EDA_CHANGE = 0.005
COOLDOWN_SECONDS = 15

# EmotiBit reports 10000 (or higher) on a saturation/error condition.
MAX_VALID_EDA = 10000

# At 15 Hz, eight samples is approximately 0.53 seconds.
REQUIRED_CONSECUTIVE_SAMPLES = 8


# ---------------------------------------------------------
# Detector state
# ---------------------------------------------------------

eda_buffer = deque(
    maxlen=BASELINE_SAMPLES + RECENT_SAMPLES
)

last_trigger_time = float("-inf")
consecutive_trigger_samples = 0


# ---------------------------------------------------------
# Motor commands
# ---------------------------------------------------------

def send_motor_command(command: bytes) -> None:
    """
    Send one UDP command to the EmotiBit Feather.

    b"M" starts both motors.
    b"S" stops both motors.
    """
    try:
        motor_socket.sendto(
            command,
            (MOTOR_IP, MOTOR_PORT),
        )

    except OSError as error:
        print(f"\nCould not send motor command: {error}")


def activate_motors() -> None:
    """
    Tell the Feather firmware to run both DRV8833 channels.

    The firmware automatically stops both motors after
    MOTOR_DURATION_MS.
    """
    print(
        "\n*** STRESS/AROUSAL SPIKE DETECTED "
        "— BOTH MOTORS ACTIVATED ***\n"
    )

    send_motor_command(b"M")


# ---------------------------------------------------------
# EDA processing
# ---------------------------------------------------------

def process_eda_value(eda_value: float) -> None:
    global last_trigger_time
    global consecutive_trigger_samples

    # Ignore the 10000 saturation/error reading.
    if eda_value >= MAX_VALID_EDA:
        print(
            f"Ignoring invalid EDA value: {eda_value}",
            end="\r",
        )
        consecutive_trigger_samples = 0
        return

    eda_buffer.append(eda_value)

    required_length = BASELINE_SAMPLES + RECENT_SAMPLES

    if len(eda_buffer) < required_length:
        seconds_collected = len(eda_buffer) / SAMPLE_RATE

        print(
            f"Calibrating: {seconds_collected:5.1f} / "
            f"{BASELINE_SECONDS + RECENT_SECONDS} seconds",
            end="\r",
        )

        return

    values = np.asarray(eda_buffer, dtype=float)

    baseline_values = values[:BASELINE_SAMPLES]
    recent_values = values[BASELINE_SAMPLES:]

    baseline = float(np.median(baseline_values))

    baseline_std = float(
        np.std(
            baseline_values,
            ddof=1,
        )
    )

    recent_average = float(np.mean(recent_values))
    eda_change = recent_average - baseline

    safe_std = max(baseline_std, 1e-6)
    z_score = eda_change / safe_std

    above_threshold = (
        z_score >= Z_THRESHOLD
        and eda_change >= MIN_EDA_CHANGE
    )

    if above_threshold:
        consecutive_trigger_samples += 1
    else:
        consecutive_trigger_samples = 0

    now = time.monotonic()

    cooldown_finished = (
        now - last_trigger_time >= COOLDOWN_SECONDS
    )

    should_trigger = (
        consecutive_trigger_samples
        >= REQUIRED_CONSECUTIVE_SAMPLES
        and cooldown_finished
    )

    print(
        f"EDA={eda_value:.6f} | "
        f"baseline={baseline:.6f} | "
        f"recent={recent_average:.6f} | "
        f"change={eda_change:+.6f} | "
        f"z={z_score:+.2f} | "
        f"count={consecutive_trigger_samples:02d}",
        end="\r",
    )

    if should_trigger:
        activate_motors()

        last_trigger_time = now
        consecutive_trigger_samples = 0


# ---------------------------------------------------------
# OSC receiver
# ---------------------------------------------------------

def receive_eda(address: str, *osc_values) -> None:
    """
    Process every numeric EDA sample received in an OSC packet.
    """
    del address

    for value in osc_values:
        try:
            eda_value = float(value)

        except (TypeError, ValueError):
            continue

        if np.isfinite(eda_value):
            process_eda_value(eda_value)


# ---------------------------------------------------------
# Main program
# ---------------------------------------------------------

def main() -> None:
    dispatcher = Dispatcher()
    dispatcher.map(
        EDA_ADDRESS,
        receive_eda,
    )

    server = ThreadingOSCUDPServer(
        (OSC_IP, OSC_PORT),
        dispatcher,
    )

    print(
        f"Two-motor commands will be sent to "
        f"{MOTOR_IP}:{MOTOR_PORT}"
    )

    print("Listening for live EmotiBit EDA data")
    print(f"OSC address: {EDA_ADDRESS}")
    print(f"OSC port:    {OSC_PORT}")
    print("Press Control-C to stop.\n")

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print("\nStopping EDA detector.")

    finally:
        # Stop both motors before closing the program.
        send_motor_command(b"S")

        motor_socket.close()
        server.server_close()


if __name__ == "__main__":
    main()
