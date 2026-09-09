# AndroidController Architecture

## Execution flow

1. Observe Android screen and accessibility/UI state.
2. Normalize the observed state.
3. Plan one or more workflow steps.
4. Execute a controlled Android action.
5. Observe again.
6. Verify the expected result.
7. Emit a Pulse event for every important transition.

## Integration boundary

AndroidController remains isolated from the existing JARVIS `monitor.py`. The future integration point is the bridge layer and the Pulse event stream.
