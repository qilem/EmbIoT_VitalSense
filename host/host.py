import argparse
import threading

import matplotlib.pyplot as plt
import numpy as np

from processor import Processor, SAMPLE_PER_CHIRP, CHIRP_PER_FRAME

def main():
    parser = argparse.ArgumentParser(description="Vital Sense Host")

    # 2. Add arguments
    parser.add_argument("-s", "--serial", help="serial port")
    
    # 3. Parse arguments
    args = parser.parse_args()

    lock = threading.Lock()
    result = {"mag": None, "breath": None, "heart": None}
    proc = Processor(result, lock, args.serial)

    threading.Thread(target=proc.worker, daemon=True).start()

    plt.ion()
    fig, (ax_mean, ax_breath, ax_heart) = plt.subplots(3, 1, figsize=(8, 10))
    bins = np.arange(SAMPLE_PER_CHIRP // 2)
    (line_mean,)   = ax_mean  .plot(bins, np.zeros_like(bins, dtype=float))

    # breath/heart share the same slow-time axis: buffer_size * chirps_per_frame samples
    n_slow = 8 * CHIRP_PER_FRAME
    t = np.arange(n_slow) / proc._pipe._fs                     # seconds
    (line_breath,) = ax_breath.plot(t, np.zeros(n_slow))
    (line_heart,)  = ax_heart .plot(t, np.zeros(n_slow))

    ax_mean  .set_title("mean |spec|");       ax_mean  .set_xlabel("range bin")
    ax_breath.set_title("breath (µm)");       ax_breath.set_xlabel("time (s)")
    ax_heart .set_title("heart (µm)");        ax_heart .set_xlabel("time (s)")

    ax_breath.set_ylim(-3000, 3000)
    ax_heart .set_ylim(-1500, 1500)
    fig.tight_layout()

    while True:
        with lock:
            if result["mag"] is not None:
                line_mean.set_ydata(result["mag"])
                line_breath.set_ydata(result["breath"])
                line_heart.set_ydata(result["heart"])

        ax_mean.relim();
        ax_mean.autoscale_view()
        
        fig.canvas.draw_idle()
        fig.canvas.flush_events()
        plt.pause(0.03)     # 30 Hz repaint target

if __name__ == "__main__":
    main()
