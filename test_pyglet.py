from psychopy import prefs
prefs.hardware['keyboardBackend'] = 'pyglet'
prefs.hardware['audioLib'] = ['sounddevice', 'pyo', 'pygame']
from psychopy import core, visual, sound
from psychopy.hardware import keyboard

print("Initializing window...")
win = visual.Window([400, 400])
print("Initializing keyboard...")
kb = keyboard.Keyboard()
print("Done. Waiting 1s...")
core.wait(1.0)
win.close()
core.quit()
