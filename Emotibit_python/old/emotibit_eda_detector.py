from collections import deque
import time

import numpy as np
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer


# ---------------------------------------------------------
# EmotiBit / OSC settings
# ---------------------------------------------------------

OSC_IP = "127.0.0.1"
OSC_PORT = 12345
EDA_ADDRESS = "/EmotiBit/0/EDA"

# Stock EmotiBit EDA sample rate is approximately 15 Hz.
SAMPLE_RATE = 15


# ---------------------------------------------------------
# Detection settings
# ---------------------------------------------------------

# Compare the newest 2 seconds against the preceding 20 seconds.
RECENT_SECONDS = 2
BASELINE_SECONDS = 20

RECENT_SAMPLES = RECENT_SECONDS * SAMPLE_RATE
BASELINE_SAMPLES = BASELINE_SECONDS * SAMPLE_RATE

# Require the increase to be this many baseline standard deviations.
Z_THRESHOLD = 2.5

# Require some minimum absolute increase.
# This helps prevent tiny changes from triggering when the baseline
# standard deviation is extremely small.
MIN_EDA_CHANGE = 0.005

# Prevent repeated triggers immediately after one event.
COOLDOWN_SECONDS = 15

# Require several consecutive positive decisions.
# At 15 Hz, 8 samples is approximately 0.53 seconds.
REQUIRED_CONSECUTIVE_SAMPLES = 8


# Store enough data for both windows.
eda_buffer = deque(
    maxlen=BASELINE_SAMPLES + RECENT_SAMPLES
)

last_trigger_time = float("-inf")
consecutive_trigger_samples = 0


def activate_motor():
    """
    Replace this function later with the command that activates
    your motor controller.
    """
    print("\n*** STRESS/AROUSAL SPIKE DETECTED — ACTIVATE MOTOR ***\n")


def process_eda_value(eda_value: float) -> None:
    global last_trigger_time
    global consecutive_trigger_samples

    eda_buffer.append(eda_value)

    required_length = BASELINE_SAMPLES + RECENT_SAMPLES

    # Wait until enough data has been collected.
    if len(eda_buffer) < required_length:
        seconds_collected = len(eda_buffer) / SAMPLE_RATE

        print(
            f"Calibrating: {seconds_collected:5.1f} / "
            f"{BASELINE_SECONDS + RECENT_SECONDS} seconds",
            end="\r",
        )
        return

    values = np.asarray(eda_buffer, dtype=float)

    # The older samples become the baseline window.
    baseline_values = values[:BASELINE_SAMPLES]

    # The newest samples become the recent window.
    recent_values = values[BASELINE_SAMPLES:]

    # Median is less sensitive to individual noisy spikes than mean.
    baseline = float(np.median(baseline_values))

    # Use sample standard deviation to describe normal variation.
    baseline_std = float(np.std(baseline_values, ddof=1))

    recent_average = float(np.mean(recent_values))

    eda_change = recent_average - baseline

    # Avoid dividing by zero if the signal is nearly perfectly flat.
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
        consecutive_trigger_samples >= REQUIRED_CONSECUTIVE_SAMPLES
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
        activate_motor()

        last_trigger_time = now
        consecutive_trigger_samples = 0


def receive_eda(address: str, *osc_values) -> None:
    """
    Called whenever Python receives an OSC message at the EDA address.

    EmotiBit may place one or multiple samples in a transmitted packet,
    so process every numeric value received.
    """
    for value in osc_values:
        try:
            eda_value = float(value)
        except (TypeError, ValueError):
            continue

        if np.isfinite(eda_value):
            process_eda_value(eda_value)


def main() -> None:
    dispatcher = Dispatcher()
    dispatcher.map(EDA_ADDRESS, receive_eda)

    server = ThreadingOSCUDPServer(
        (OSC_IP, OSC_PORT),
        dispatcher,
    )

    print("Listening for live EmotiBit EDA data")
    print(f"OSC address: {EDA_ADDRESS}")
    print(f"OSC port:    {OSC_PORT}")
    print("Press Control-C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping EDA detector.")
        server.shutdown()


if __name__ == "__main__":
    main()
