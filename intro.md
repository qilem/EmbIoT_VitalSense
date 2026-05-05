# Vital Sense: Contactless Radar Health Companion


**The Problem:** Relentless overtime and late-night coding sessions create a silent risk of severe exhaustion or even sudden health crises (like cardiac events) right at the desk. Yet, continuous health monitoring usually means strapping an uncomfortable device to your body or compromising your privacy with invasive camera-based tracking.

**Our Solution:** Vital Sense turns an Infineon CY8CKIT-062S2-AI evaluation board into a 100% passive, contactless health monitor. Using a BGT60TR13C 60 GHz FMCW radar, it detects the micro-displacements of your chest wall caused by your heartbeat and breath—up to 50 cm away, right through your clothing. 

Raw radar frames stream over USB-CDC to our PC-side DSP pipeline, where range FFTs, phase unwrapping, and dual Butterworth filters isolate your breathing (~0.1–0.5 Hz) and heart rate (~0.8–2.5 Hz). 

**The Wow Factor:** We paired this sensing with a anime-style desktop companion. Sitting quietly on your screen, she monitors your real-time vitals and warns you when she senses stress or exhaustion, offering context-aware, "tsundere-style" care to keep you safe during long focus sessions.

**Key Results:** * **Accuracy:** Live BPM within ±5 BPM at rest, breathing rate within ±2 breaths/min.
* **Performance:** ~1 s end-to-end latency, 30–90 cm detection range.


![Vital Sense companion UI — live heart rate detection](docs/figures/working.png)
