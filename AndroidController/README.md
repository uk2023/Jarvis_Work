# AndroidController

Android-facing controller layer for JARVIS.

This branch contains the initial foundation for an Android Computer-Use style subsystem. The implementation starts intentionally minimal and will be expanded incrementally.

## Planned capabilities

- Observe Android screen state
- Read accessibility/UI hierarchy
- Execute taps, swipes, long-presses and text input
- Launch/back/home/recents actions
- Report step-by-step execution state
- Expose a stable bridge for future JARVIS integration
- Provide a workflow/event stream for a future frontend monitor

## Design rule

The Android controller is isolated from the existing JARVIS `monitor.py`. The controller's lightweight runtime monitor is named `pulse.py` so it can later feed the main JARVIS observability layer without conflicting with the existing monitor module.
