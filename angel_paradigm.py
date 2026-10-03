#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This experiment was created using PsychoPy3 Experiment Builder (v2026.1.3),
    on Sat Oct  3 17:17:22 2026
If you publish work using this script the most relevant publication is:

    Peirce J, Gray JR, Simpson S, MacAskill M, Höchenberger R, Sogo H, Kastman E, Lindeløv JK. (2019) 
        PsychoPy2: Experiments in behavior made easy Behav Res 51: 195. 
        https://doi.org/10.3758/s13428-018-01193-y

"""

# --- Import packages ---
from psychopy import locale_setup
from psychopy import prefs
from psychopy import plugins
plugins.activatePlugins()
from psychopy import sound, gui, visual, core, data, event, logging, clock, colors, layout, hardware
from psychopy.tools import environmenttools
from psychopy.constants import (
    NOT_STARTED, STARTED, PLAYING, PAUSED, STOPPED, STOPPING, FINISHED, PRESSED, 
    RELEASED, FOREVER, priority
)

import numpy as np  # whole numpy lib is available, prepend 'np.'
from numpy import (sin, cos, tan, log, log10, pi, average,
                   sqrt, std, deg2rad, rad2deg, linspace, asarray)
from numpy.random import random, randint, normal, shuffle, choice as randchoice
import os  # handy system and path functions
import sys  # to get file system encoding

from psychopy.hardware import keyboard

# Run 'Before Experiment' code from init_code
import angel_paradigm_coder as engine
args = engine.parse_args()
args = engine.show_config_dialog(args)
engine.CURRENT_ARGS = args

# --- Setup global variables (available in all functions) ---
# create a device manager to handle hardware (keyboards, mice, mirophones, speakers, etc.)
deviceManager = hardware.DeviceManager()
# ensure that relative paths start from the same directory as this script
_thisDir = os.path.dirname(os.path.abspath(__file__))
# store info about the experiment session
psychopyVersion = '2026.1.3'
expName = 'angel_paradigm_builder'  # from the Builder filename that created this script
expVersion = ''
# a list of functions to run when the experiment ends (starts off blank)
runAtExit = []
# information about this experiment
expInfo = {
    'participant': 'test',
    'session': '001',
    'date|hid': data.getDateStr(),
    'expName|hid': expName,
    'expVersion|hid': expVersion,
    'psychopyVersion|hid': psychopyVersion,
}

# --- Define some variables which will change depending on pilot mode ---
'''
To run in pilot mode, either use the run/pilot toggle in Builder, Coder and Runner, 
or run the experiment with `--pilot` as an argument. To change what pilot 
#mode does, check out the 'Pilot mode' tab in preferences.
'''
# work out from system args whether we are running in pilot mode
PILOTING = core.setPilotModeFromArgs()
# start off with values from experiment settings
_fullScr = True
_winSize = [1280,800]
# if in pilot mode, apply overrides according to preferences
if PILOTING:
    # force windowed mode
    if prefs.piloting['forceWindowed']:
        _fullScr = False
        # set window size
        _winSize = prefs.piloting['forcedWindowSize']
    # replace default participant ID
    if prefs.piloting['replaceParticipantID']:
        expInfo['participant'] = 'pilot'

def showExpInfoDlg(expInfo):
    """
    Show participant info dialog.
    Parameters
    ==========
    expInfo : dict
        Information about this experiment.
    
    Returns
    ==========
    dict
        Information about this experiment.
    """
    # show participant info dialog
    dlg = gui.DlgFromDict(
        dictionary=expInfo, sortKeys=False, title=expName, alwaysOnTop=True
    )
    if dlg.OK == False:
        core.quit()  # user pressed cancel
    # return expInfo
    return expInfo


def setupData(expInfo, dataDir=None):
    """
    Make an ExperimentHandler to handle trials and saving.
    
    Parameters
    ==========
    expInfo : dict
        Information about this experiment, created by the `setupExpInfo` function.
    dataDir : Path, str or None
        Folder to save the data to, leave as None to create a folder in the current directory.    
    Returns
    ==========
    psychopy.data.ExperimentHandler
        Handler object for this experiment, contains the data to save and information about 
        where to save it to.
    """
    # remove dialog-specific syntax from expInfo
    for key, val in expInfo.copy().items():
        newKey, _ = data.utils.parsePipeSyntax(key)
        expInfo[newKey] = expInfo.pop(key)
    
    # data file name stem = absolute path + name; later add .psyexp, .csv, .log, etc
    if dataDir is None:
        dataDir = 'data'
    filename = u'data/%s_%s_%s' % (engine.CURRENT_ARGS.participant if ('engine' in globals() and hasattr(engine, 'CURRENT_ARGS') and engine.CURRENT_ARGS) else expInfo['participant'], expName, expInfo['date'])
    # make sure filename is relative to dataDir
    if os.path.isabs(filename):
        dataDir = os.path.commonprefix([dataDir, filename])
        filename = os.path.relpath(filename, dataDir)
    
    # an ExperimentHandler isn't essential but helps with data saving
    thisExp = data.ExperimentHandler(
        name=expName, version=expVersion,
        extraInfo=expInfo, runtimeInfo=None,
        originPath='angel_paradigm.py',
        savePickle=True, saveWideText=True,
        dataFileName=dataDir + os.sep + filename, sortColumns='time'
    )
    # store pilot mode in data file
    thisExp.addData('piloting', PILOTING, priority=priority.LOW)
    thisExp.setPriority('thisRow.t', priority.CRITICAL)
    thisExp.setPriority('expName', priority.LOW)
    # return experiment handler
    return thisExp


def setupLogging(filename):
    """
    Setup a log file and tell it what level to log at.
    
    Parameters
    ==========
    filename : str or pathlib.Path
        Filename to save log file and data files as, doesn't need an extension.
    
    Returns
    ==========
    psychopy.logging.LogFile
        Text stream to receive inputs from the logging system.
    """
    # set how much information should be printed to the console / app
    if PILOTING:
        logging.console.setLevel(
            prefs.piloting['pilotConsoleLoggingLevel']
        )
    else:
        logging.console.setLevel('warning')
    # save a log file for detail verbose info
    logFile = logging.LogFile(filename+'.log')
    if PILOTING:
        logFile.setLevel(
            prefs.piloting['pilotLoggingLevel']
        )
    else:
        logFile.setLevel(
            logging.getLevel('info')
        )
    
    return logFile


def setupWindow(expInfo=None, win=None):
    """
    Setup the Window
    
    Parameters
    ==========
    expInfo : dict
        Information about this experiment, created by the `setupExpInfo` function.
    win : psychopy.visual.Window
        Window to setup - leave as None to create a new window.
    
    Returns
    ==========
    psychopy.visual.Window
        Window in which to run this experiment.
    """
    if PILOTING:
        logging.debug('Fullscreen settings ignored as running in pilot mode.')
    
    if win is None:
        # if not given a window to setup, make one
        win = visual.Window(
            size=_winSize, fullscr=_fullScr, screen=0,
            winType='pyglet', allowGUI=False, allowStencil=False,
            monitor='testMonitor', color=[0,0,0], colorSpace='rgb',
            backgroundImage='', backgroundFit='none',
            blendMode='avg', useFBO=True,
            units='height',
            checkTiming=False  # we're going to do this ourselves in a moment
        )
    else:
        # if we have a window, just set the attributes which are safe to set
        win.color = [0,0,0]
        win.colorSpace = 'rgb'
        win.backgroundImage = ''
        win.backgroundFit = 'none'
        win.units = 'height'
    if expInfo is not None:
        # get/measure frame rate if not already in expInfo
        if win._monitorFrameRate is None:
            win._monitorFrameRate = win.getActualFrameRate(infoMsg='Attempting to measure frame rate of screen, please wait...')
        expInfo['frameRate'] = win._monitorFrameRate
    win.hideMessage()
    if PILOTING:
        # show a visual indicator if we're in piloting mode
        if prefs.piloting['showPilotingIndicator']:
            win.showPilotingIndicator()
        # always show the mouse in piloting mode
        if prefs.piloting['forceMouseVisible']:
            win.mouseVisible = True
    
    return win


def setupDevices(expInfo, thisExp, win):
    """
    Setup whatever devices are available (mouse, keyboard, speaker, eyetracker, etc.) and add them to 
    the device manager (deviceManager)
    
    Parameters
    ==========
    expInfo : dict
        Information about this experiment, created by the `setupExpInfo` function.
    thisExp : psychopy.data.ExperimentHandler
        Handler object for this experiment, contains the data to save and information about 
        where to save it to.
    win : psychopy.visual.Window
        Window in which to run this experiment.
    Returns
    ==========
    bool
        True if completed successfully.
    """
    # --- Setup input devices ---
    ioConfig = {}
    ioSession = ioServer = eyetracker = None
    
    # store ioServer object in the device manager
    deviceManager.ioServer = ioServer
    
    # create a default keyboard (e.g. to check for escape)
    if deviceManager.getDevice('defaultKeyboard') is None:
        deviceManager.addDevice(
            deviceClass='keyboard', deviceName='defaultKeyboard', backend='ptb'
        )
    # return True if completed successfully
    return True

def pauseExperiment(thisExp, win=None, timers=[], currentRoutine=None):
    """
    Pause this experiment, preventing the flow from advancing to the next routine until resumed.
    
    Parameters
    ==========
    thisExp : psychopy.data.ExperimentHandler
        Handler object for this experiment, contains the data to save and information about 
        where to save it to.
    win : psychopy.visual.Window
        Window for this experiment.
    timers : list, tuple
        List of timers to reset once pausing is finished.
    currentRoutine : psychopy.data.Routine
        Current Routine we are in at time of pausing, if any. This object tells PsychoPy what Components to pause/play/dispatch.
    """
    # if we are not paused, do nothing
    if thisExp.status != PAUSED:
        return
    
    # start a timer to figure out how long we're paused for
    pauseTimer = core.Clock()
    # pause any playback components
    if currentRoutine is not None:
        for comp in currentRoutine.getPlaybackComponents():
            comp.pause()
    # make sure we have a keyboard
    defaultKeyboard = deviceManager.getDevice('defaultKeyboard')
    if defaultKeyboard is None:
        defaultKeyboard = deviceManager.addKeyboard(
            deviceClass='keyboard',
            deviceName='defaultKeyboard',
            backend='PsychToolbox',
        )
    # run a while loop while we wait to unpause
    while thisExp.status == PAUSED:
        # check for quit (typically the Esc key)
        if defaultKeyboard.getKeys(keyList=['escape']):
            endExperiment(thisExp, win=win)
        # dispatch messages on response components
        if currentRoutine is not None:
            for comp in currentRoutine.getDispatchComponents():
                comp.device.dispatchMessages()
        # sleep 1ms so other threads can execute
        clock.time.sleep(0.001)
    # if stop was requested while paused, quit
    if thisExp.status == FINISHED:
        endExperiment(thisExp, win=win)
    # resume any playback components
    if currentRoutine is not None:
        for comp in currentRoutine.getPlaybackComponents():
            comp.play()
    # reset any timers
    for timer in timers:
        timer.addTime(-pauseTimer.getTime())


def run(expInfo, thisExp, win, globalClock=None, thisSession=None):
    """
    Run the experiment flow.
    
    Parameters
    ==========
    expInfo : dict
        Information about this experiment, created by the `setupExpInfo` function.
    thisExp : psychopy.data.ExperimentHandler
        Handler object for this experiment, contains the data to save and information about 
        where to save it to.
    psychopy.visual.Window
        Window in which to run this experiment.
    globalClock : psychopy.core.clock.Clock or None
        Clock to get global time from - supply None to make a new one.
    thisSession : psychopy.session.Session or None
        Handle of the Session object this experiment is being run from, if any.
    """
    # mark experiment as started
    thisExp.status = STARTED
    # update experiment info
    expInfo['date'] = data.getDateStr()
    expInfo['expName'] = expName
    expInfo['expVersion'] = expVersion
    expInfo['psychopyVersion'] = psychopyVersion
    # make sure window is set to foreground to prevent losing focus
    win.winHandle.activate()
    # make sure variables created by exec are available globally
    exec = environmenttools.setExecEnvironment(globals())
    # get device handles from dict of input devices
    ioServer = deviceManager.ioServer
    # get/create a default keyboard (e.g. to check for escape)
    defaultKeyboard = deviceManager.getDevice('defaultKeyboard')
    if defaultKeyboard is None:
        deviceManager.addDevice(
            deviceClass='keyboard', deviceName='defaultKeyboard', backend='PsychToolbox'
        )
    eyetracker = deviceManager.getDevice('eyetracker')
    # make sure we're running in the directory for this experiment
    os.chdir(_thisDir)
    # get filename from ExperimentHandler for convenience
    filename = thisExp.dataFileName
    frameTolerance = 0.001  # how close to onset before 'same' frame
    endExpNow = False  # flag for 'escape' or other condition => quit the exp
    # get frame duration from frame rate in expInfo
    if 'frameRate' in expInfo and expInfo['frameRate'] is not None:
        frameDur = 1.0 / round(expInfo['frameRate'])
    else:
        frameDur = 1.0 / 60.0  # could not measure, so guess
    
    # Start Code - component code to be run after the window creation
    
    # --- Initialize components for Routine "Init" ---
    # Run 'Begin Experiment' code from init_code
    import random as std_random
    args = engine.CURRENT_ARGS
    levels = [level.strip() for level in args.levels.split(',') if level.strip()]
    engine.validate_config(args)
    # Synchronize KEYS and participant ID
    engine.KEYS['left'] = engine.parse_keys_list(args.left_keys)
    engine.KEYS['right'] = engine.parse_keys_list(args.right_keys)
    engine.KEYS['continue'] = engine.parse_keys_list(getattr(args, 'continue_keys', 'any'))
    engine.KEYS['trigger'] = engine.parse_keys_list(args.trigger_keys)
    KEYS = engine.KEYS
    expInfo['participant'] = args.participant
    thisExp.extraInfo['participant'] = args.participant
    exp_clock = core.Clock()
    markers = engine.MarkerSender(args, core, exp_clock)
    rng = std_random.Random(args.seed)
    assets_by_level = {lvl: engine.load_assets(args.resource_root / engine.LEVEL_TEMPLATES[lvl], args.language) for lvl in levels}
    assets = assets_by_level[levels[0]]
    trial_counter = 0
    main_session_rows = []
    # Adapter so engine can log directly to PsychoPy ExperimentHandler
    class _PsyWriter:
        def writerow(self, row):
            for k, v in row.items():
                thisExp.addData(k, v)
            thisExp.nextEntry()
    class _PsyFile:
        def flush(self): pass
    psy_writer = _PsyWriter()
    psy_file = _PsyFile()
    
    
    # --- Initialize components for Routine "Instructions" ---
    # Run 'Begin Experiment' code from instruction_code
    inst_audio = None
    
    instruction_image = visual.ImageStim(
        win=win,
        name='instruction_image', units='height', 
        image='EPrimeFiles/CCS_EEG_ANGELv2_Level2_Template/english/InstructionLevel1.PNG', mask=None, anchor='center',
        ori=0.0, pos=(0, 0), draggable=False, size=(1.333, 1.0),
        color=[1,1,1], colorSpace='rgb', opacity=None,
        flipHoriz=False, flipVert=False,
        texRes=128.0, interpolate=True, depth=-1.0)
    instruction_key = keyboard.Keyboard(deviceName='defaultKeyboard')
    
    # --- Initialize components for Routine "PracticeRoutine" ---
    
    # --- Initialize components for Routine "TriggerWait" ---
    trigger_text = visual.TextStim(win=win, name='trigger_text',
        text='Waiting for scanner trigger (s)...',
        font='Arial',
        units='height', pos=(0, 0), draggable=False, height=0.05, wrapWidth=None, ori=0.0, 
        color='white', colorSpace='rgb', opacity=None, 
        languageStyle='LTR',
        depth=-1.0);
    trigger_key = keyboard.Keyboard(deviceName='defaultKeyboard')
    
    # --- Initialize components for Routine "TrialRoutine" ---
    fixation = visual.ImageStim(
        win=win,
        name='fixation', units='height', 
        image='EPrimeFiles/CCS_EEG_ANGELv2_Level2_Template/resources/plus.png', mask=None, anchor='center',
        ori=0.0, pos=(0, 0), draggable=False, size=(0.075, 0.075),
        color=[1,1,1], colorSpace='rgb', opacity=None,
        flipHoriz=False, flipVert=False,
        texRes=128.0, interpolate=True, depth=0.0)
    left_mask = visual.ImageStim(
        win=win,
        name='left_mask', units='height', 
        image='EPrimeFiles/CCS_EEG_ANGELv2_Level2_Template/resources/cb.png', mask=None, anchor='center',
        ori=0.0, pos=(-0.42, 0), draggable=False, size=(0.32, 0.41),
        color=[1,1,1], colorSpace='rgb', opacity=None,
        flipHoriz=False, flipVert=False,
        texRes=128.0, interpolate=True, depth=-1.0)
    right_mask = visual.ImageStim(
        win=win,
        name='right_mask', units='height', 
        image='EPrimeFiles/CCS_EEG_ANGELv2_Level2_Template/resources/cb.png', mask=None, anchor='center',
        ori=0.0, pos=(0.42, 0), draggable=False, size=(0.32, 0.41),
        color=[1,1,1], colorSpace='rgb', opacity=None,
        flipHoriz=False, flipVert=False,
        texRes=128.0, interpolate=True, depth=-2.0)
    target_stim = visual.ImageStim(
        win=win,
        name='target_stim', units='height', 
        image='EPrimeFiles/CCS_EEG_ANGELv2_Level2_Template/resources/faa01.png', mask=None, anchor='center',
        ori=0.0, pos=(-0.42, 0), draggable=False, size=(0.32, 0.41),
        color=[1,1,1], colorSpace='rgb', opacity=None,
        flipHoriz=False, flipVert=False,
        texRes=128.0, interpolate=True, depth=-3.0)
    top_distractor = visual.ImageStim(
        win=win,
        name='top_distractor', units='height', 
        image='EPrimeFiles/CCS_EEG_ANGELv2_Level2_Template/resources/cb.png', mask=None, anchor='center',
        ori=0.0, pos=(-0.18, 0.34), draggable=False, size=(0.12, 0.085),
        color=[1,1,1], colorSpace='rgb', opacity=None,
        flipHoriz=False, flipVert=False,
        texRes=128.0, interpolate=True, depth=-4.0)
    bottom_distractor = visual.ImageStim(
        win=win,
        name='bottom_distractor', units='height', 
        image='EPrimeFiles/CCS_EEG_ANGELv2_Level2_Template/resources/cb.png', mask=None, anchor='center',
        ori=0.0, pos=(-0.18, -0.34), draggable=False, size=(0.12, 0.085),
        color=[1,1,1], colorSpace='rgb', opacity=None,
        flipHoriz=False, flipVert=False,
        texRes=128.0, interpolate=True, depth=-5.0)
    response_key = keyboard.Keyboard(deviceName='defaultKeyboard')
    # Run 'Begin Experiment' code from trial_runner
    trials = []
    
    
    # --- Initialize components for Routine "Feedback" ---
    feedback_image = visual.ImageStim(
        win=win,
        name='feedback_image', units='height', 
        image='EPrimeFiles/CCS_EEG_ANGELv2_Level2_Template/english/FeedbackGoodjob.PNG', mask=None, anchor='center',
        ori=0.0, pos=(0, 0.14), draggable=False, size=(1.05, 0.78),
        color=[1,1,1], colorSpace='rgb', opacity=None,
        flipHoriz=False, flipVert=False,
        texRes=128.0, interpolate=True, depth=-1.0)
    feedback_text = visual.TextStim(win=win, name='feedback_text',
        text='Session Complete! Press any key to continue...',
        font='Arial',
        units='height', pos=(0, -0.34), draggable=False, height=0.05, wrapWidth=None, ori=0.0, 
        color='white', colorSpace='rgb', opacity=None, 
        languageStyle='LTR',
        depth=-2.0);
    feedback_key = keyboard.Keyboard(deviceName='defaultKeyboard')
    
    # --- Initialize components for Routine "End" ---
    end_image = visual.ImageStim(
        win=win,
        name='end_image', units='height', 
        image='EPrimeFiles/CCS_EEG_ANGELv2_Level2_Template/english/ExperimentEnd.PNG', mask=None, anchor='center',
        ori=0.0, pos=(0, 0), draggable=False, size=(1.333, 1.0),
        color=[1,1,1], colorSpace='rgb', opacity=None,
        flipHoriz=False, flipVert=False,
        texRes=128.0, interpolate=True, depth=-1.0)
    end_key = keyboard.Keyboard(deviceName='defaultKeyboard')
    
    # create some handy timers
    
    # global clock to track the time since experiment started
    if globalClock is None:
        # create a clock if not given one
        globalClock = core.Clock()
    if isinstance(globalClock, str):
        # if given a string, make a clock accoridng to it
        if globalClock == 'float':
            # get timestamps as a simple value
            globalClock = core.Clock(format='float')
        elif globalClock == 'iso':
            # get timestamps in ISO format
            globalClock = core.Clock(format='%Y-%m-%d_%H:%M:%S.%f%z')
        else:
            # get timestamps in a custom format
            globalClock = core.Clock(format=globalClock)
    if ioServer is not None:
        ioServer.syncClock(globalClock)
    logging.setDefaultClock(globalClock)
    if eyetracker is not None:
        eyetracker.enableEventReporting()
    # routine timer to track time remaining of each (possibly non-slip) routine
    routineTimer = core.Clock()
    win.flip()  # flip window to reset last flip timer
    # store the exact time the global clock started
    expInfo['expStart'] = data.getDateStr(
        format='%Y-%m-%d %Hh%M.%S.%f %z', fractionalSecondDigits=6
    )
    
    # --- Prepare to start Routine "Init" ---
    # create an object to store info about Routine Init
    Init = data.Routine(
        name='Init',
        components=[],
    )
    Init.status = NOT_STARTED
    continueRoutine = True
    # update component parameters for each repeat
    # store start times for Init
    Init.tStartRefresh = win.getFutureFlipTime(clock=globalClock)
    Init.tStart = globalClock.getTime(format='float')
    Init.status = STARTED
    thisExp.addData('Init.started', Init.tStart)
    Init.maxDuration = None
    # keep track of which components have finished
    InitComponents = Init.components
    for thisComponent in Init.components:
        thisComponent.tStart = None
        thisComponent.tStop = None
        thisComponent.tStartRefresh = None
        thisComponent.tStopRefresh = None
        if hasattr(thisComponent, 'status'):
            thisComponent.status = NOT_STARTED
    # reset timers
    t = 0
    _timeToFirstFrame = win.getFutureFlipTime(clock="now")
    frameN = -1
    
    # --- Run Routine "Init" ---
    thisExp.currentRoutine = Init
    Init.forceEnded = routineForceEnded = not continueRoutine
    while continueRoutine:
        # get current time
        t = routineTimer.getTime()
        tThisFlip = win.getFutureFlipTime(clock=routineTimer)
        tThisFlipGlobal = win.getFutureFlipTime(clock=None)
        frameN = frameN + 1  # number of completed frames (so 0 is the first frame)
        # update/draw components on each frame
        
        # check for quit (typically the Esc key)
        if defaultKeyboard.getKeys(keyList=["escape"]):
            thisExp.status = FINISHED
        if thisExp.status == FINISHED or endExpNow:
            endExperiment(thisExp, win=win)
            return
        # pause experiment here if requested
        if thisExp.status == PAUSED:
            pauseExperiment(
                thisExp=thisExp, 
                win=win, 
                timers=[routineTimer, globalClock], 
                currentRoutine=Init,
            )
            # skip the frame we paused on
            continue
        
        # has a Component requested the Routine to end?
        if not continueRoutine:
            Init.forceEnded = routineForceEnded = True
        # has the Routine been forcibly ended?
        if Init.forceEnded or routineForceEnded:
            break
        # has every Component finished?
        continueRoutine = False
        for thisComponent in Init.components:
            if hasattr(thisComponent, "status") and thisComponent.status != FINISHED:
                continueRoutine = True
                break  # at least one component has not yet finished
        
        # refresh the screen
        if continueRoutine:  # don't flip if this routine is over or we'll get a blank screen
            win.flip()
    
    # --- Ending Routine "Init" ---
    for thisComponent in Init.components:
        if hasattr(thisComponent, "setAutoDraw"):
            thisComponent.setAutoDraw(False)
    # store stop times for Init
    Init.tStop = globalClock.getTime(format='float')
    Init.tStopRefresh = tThisFlipGlobal
    thisExp.addData('Init.stopped', Init.tStop)
    thisExp.nextEntry()
    # the Routine "Init" was not non-slip safe, so reset the non-slip timer
    routineTimer.reset()
    
    # --- Prepare to start Routine "Instructions" ---
    # create an object to store info about Routine Instructions
    Instructions = data.Routine(
        name='Instructions',
        components=[instruction_image, instruction_key],
    )
    Instructions.status = NOT_STARTED
    continueRoutine = True
    # update component parameters for each repeat
    # Run 'Begin Routine' code from instruction_code
    if getattr(args, 'skip_instructions', False):
        continueRoutine = False
    else:
        markers.send('instruction_start', 101)
        inst_img = str(assets['language'] / 'InstructionLevel1.PNG')
        instruction_image.setImage(inst_img)
        if getattr(args, 'audio_instructions', False):
            inst_audio_path = assets['language'] / 'InstructionLevel1.mp3'
            if inst_audio_path.exists():
                inst_audio = engine.get_cached_sound(sound, inst_audio_path)
                if inst_audio:
                    try:
                        inst_audio.play()
                    except Exception:
                        pass
    
    # create starting attributes for instruction_key
    instruction_key.keys = []
    instruction_key.rt = []
    _instruction_key_allKeys = []
    # store start times for Instructions
    Instructions.tStartRefresh = win.getFutureFlipTime(clock=globalClock)
    Instructions.tStart = globalClock.getTime(format='float')
    Instructions.status = STARTED
    thisExp.addData('Instructions.started', Instructions.tStart)
    Instructions.maxDuration = None
    # keep track of which components have finished
    InstructionsComponents = Instructions.components
    for thisComponent in Instructions.components:
        thisComponent.tStart = None
        thisComponent.tStop = None
        thisComponent.tStartRefresh = None
        thisComponent.tStopRefresh = None
        if hasattr(thisComponent, 'status'):
            thisComponent.status = NOT_STARTED
    # reset timers
    t = 0
    _timeToFirstFrame = win.getFutureFlipTime(clock="now")
    frameN = -1
    
    # --- Run Routine "Instructions" ---
    thisExp.currentRoutine = Instructions
    Instructions.forceEnded = routineForceEnded = not continueRoutine
    while continueRoutine:
        # get current time
        t = routineTimer.getTime()
        tThisFlip = win.getFutureFlipTime(clock=routineTimer)
        tThisFlipGlobal = win.getFutureFlipTime(clock=None)
        frameN = frameN + 1  # number of completed frames (so 0 is the first frame)
        # update/draw components on each frame
        
        # *instruction_image* updates
        
        # if instruction_image is starting this frame...
        if instruction_image.status == NOT_STARTED and tThisFlip >= 0.0-frameTolerance:
            # keep track of start time/frame for later
            instruction_image.frameNStart = frameN  # exact frame index
            instruction_image.tStart = t  # local t and not account for scr refresh
            instruction_image.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(instruction_image, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'instruction_image.started')
            # update status
            instruction_image.status = STARTED
            instruction_image.setAutoDraw(True)
        
        # if instruction_image is active this frame...
        if instruction_image.status == STARTED:
            # update params
            pass
        
        # *instruction_key* updates
        waitOnFlip = False
        
        # if instruction_key is starting this frame...
        if instruction_key.status == NOT_STARTED and tThisFlip >= 0.0-frameTolerance:
            # keep track of start time/frame for later
            instruction_key.frameNStart = frameN  # exact frame index
            instruction_key.tStart = t  # local t and not account for scr refresh
            instruction_key.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(instruction_key, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'instruction_key.started')
            # update status
            instruction_key.status = STARTED
            # keyboard checking is just starting
            waitOnFlip = True
            win.callOnFlip(instruction_key.clock.reset)  # t=0 on next screen flip
            win.callOnFlip(instruction_key.clearEvents, eventType='keyboard')  # clear events on next screen flip
        
        # if instruction_key is stopping this frame...
        if instruction_key.status == STARTED:
            # is it time to stop? (based on global clock, using actual start)
            if tThisFlipGlobal > instruction_key.tStartRefresh + (getattr(args, 'slide_timeout', 5.0) if getattr(args, 'slide_timeout', 5.0) > 0 else 999999.0)-frameTolerance:
                # keep track of stop time/frame for later
                instruction_key.tStop = t  # not accounting for scr refresh
                instruction_key.tStopRefresh = tThisFlipGlobal  # on global time
                instruction_key.frameNStop = frameN  # exact frame index
                # add timestamp to datafile
                thisExp.timestampOnFlip(win, 'instruction_key.stopped')
                # update status
                instruction_key.status = FINISHED
                instruction_key.status = FINISHED
        if instruction_key.status == STARTED and not waitOnFlip:
            theseKeys = instruction_key.getKeys(keyList=None, ignoreKeys=["escape"], waitRelease=False)
            _instruction_key_allKeys.extend(theseKeys)
            if len(_instruction_key_allKeys):
                instruction_key.keys = _instruction_key_allKeys[-1].name  # just the last key pressed
                instruction_key.rt = _instruction_key_allKeys[-1].rt
                instruction_key.duration = _instruction_key_allKeys[-1].duration
                # a response ends the routine
                continueRoutine = False
        
        # check for quit (typically the Esc key)
        if defaultKeyboard.getKeys(keyList=["escape"]):
            thisExp.status = FINISHED
        if thisExp.status == FINISHED or endExpNow:
            endExperiment(thisExp, win=win)
            return
        # pause experiment here if requested
        if thisExp.status == PAUSED:
            pauseExperiment(
                thisExp=thisExp, 
                win=win, 
                timers=[routineTimer, globalClock], 
                currentRoutine=Instructions,
            )
            # skip the frame we paused on
            continue
        
        # has a Component requested the Routine to end?
        if not continueRoutine:
            Instructions.forceEnded = routineForceEnded = True
        # has the Routine been forcibly ended?
        if Instructions.forceEnded or routineForceEnded:
            break
        # has every Component finished?
        continueRoutine = False
        for thisComponent in Instructions.components:
            if hasattr(thisComponent, "status") and thisComponent.status != FINISHED:
                continueRoutine = True
                break  # at least one component has not yet finished
        
        # refresh the screen
        if continueRoutine:  # don't flip if this routine is over or we'll get a blank screen
            win.flip()
    
    # --- Ending Routine "Instructions" ---
    for thisComponent in Instructions.components:
        if hasattr(thisComponent, "setAutoDraw"):
            thisComponent.setAutoDraw(False)
    # store stop times for Instructions
    Instructions.tStop = globalClock.getTime(format='float')
    Instructions.tStopRefresh = tThisFlipGlobal
    thisExp.addData('Instructions.stopped', Instructions.tStop)
    # Run 'End Routine' code from instruction_code
    markers.send('instruction_end', 102)
    if 'inst_audio' in locals() and inst_audio:
        try:
            inst_audio.stop()
        except Exception:
            pass
    
    # check responses
    if instruction_key.keys in ['', [], None]:  # No response was made
        instruction_key.keys = None
    thisExp.addData('instruction_key.keys',instruction_key.keys)
    if instruction_key.keys != None:  # we had a response
        thisExp.addData('instruction_key.rt', instruction_key.rt)
        thisExp.addData('instruction_key.duration', instruction_key.duration)
    thisExp.nextEntry()
    # the Routine "Instructions" was not non-slip safe, so reset the non-slip timer
    routineTimer.reset()
    
    # --- Prepare to start Routine "PracticeRoutine" ---
    # create an object to store info about Routine PracticeRoutine
    PracticeRoutine = data.Routine(
        name='PracticeRoutine',
        components=[],
    )
    PracticeRoutine.status = NOT_STARTED
    continueRoutine = True
    # update component parameters for each repeat
    # Run 'Begin Routine' code from practice_code
    # ==============================================================================
    # ANGEL PRACTICE CONTROLLER: RUNS STRICTLY BEFORE SCANNER TRIGGER WAIT
    # ==============================================================================
    if getattr(args, 'practice', 0) > 0 and not getattr(args, 'skip_instructions', False):
        markers.send('practice_start', 103)
        trial_counter = engine.run_practice_phase(
            levels, args, win, core, event, visual, sound,
            psy_writer, psy_file, rng, trial_counter, exp_clock, markers,
            show_instructions=False
        )
        markers.send('practice_end', 104)
    continueRoutine = False
    
    # store start times for PracticeRoutine
    PracticeRoutine.tStartRefresh = win.getFutureFlipTime(clock=globalClock)
    PracticeRoutine.tStart = globalClock.getTime(format='float')
    PracticeRoutine.status = STARTED
    thisExp.addData('PracticeRoutine.started', PracticeRoutine.tStart)
    PracticeRoutine.maxDuration = None
    # keep track of which components have finished
    PracticeRoutineComponents = PracticeRoutine.components
    for thisComponent in PracticeRoutine.components:
        thisComponent.tStart = None
        thisComponent.tStop = None
        thisComponent.tStartRefresh = None
        thisComponent.tStopRefresh = None
        if hasattr(thisComponent, 'status'):
            thisComponent.status = NOT_STARTED
    # reset timers
    t = 0
    _timeToFirstFrame = win.getFutureFlipTime(clock="now")
    frameN = -1
    
    # --- Run Routine "PracticeRoutine" ---
    thisExp.currentRoutine = PracticeRoutine
    PracticeRoutine.forceEnded = routineForceEnded = not continueRoutine
    while continueRoutine:
        # get current time
        t = routineTimer.getTime()
        tThisFlip = win.getFutureFlipTime(clock=routineTimer)
        tThisFlipGlobal = win.getFutureFlipTime(clock=None)
        frameN = frameN + 1  # number of completed frames (so 0 is the first frame)
        # update/draw components on each frame
        
        # check for quit (typically the Esc key)
        if defaultKeyboard.getKeys(keyList=["escape"]):
            thisExp.status = FINISHED
        if thisExp.status == FINISHED or endExpNow:
            endExperiment(thisExp, win=win)
            return
        # pause experiment here if requested
        if thisExp.status == PAUSED:
            pauseExperiment(
                thisExp=thisExp, 
                win=win, 
                timers=[routineTimer, globalClock], 
                currentRoutine=PracticeRoutine,
            )
            # skip the frame we paused on
            continue
        
        # has a Component requested the Routine to end?
        if not continueRoutine:
            PracticeRoutine.forceEnded = routineForceEnded = True
        # has the Routine been forcibly ended?
        if PracticeRoutine.forceEnded or routineForceEnded:
            break
        # has every Component finished?
        continueRoutine = False
        for thisComponent in PracticeRoutine.components:
            if hasattr(thisComponent, "status") and thisComponent.status != FINISHED:
                continueRoutine = True
                break  # at least one component has not yet finished
        
        # refresh the screen
        if continueRoutine:  # don't flip if this routine is over or we'll get a blank screen
            win.flip()
    
    # --- Ending Routine "PracticeRoutine" ---
    for thisComponent in PracticeRoutine.components:
        if hasattr(thisComponent, "setAutoDraw"):
            thisComponent.setAutoDraw(False)
    # store stop times for PracticeRoutine
    PracticeRoutine.tStop = globalClock.getTime(format='float')
    PracticeRoutine.tStopRefresh = tThisFlipGlobal
    thisExp.addData('PracticeRoutine.stopped', PracticeRoutine.tStop)
    thisExp.nextEntry()
    # the Routine "PracticeRoutine" was not non-slip safe, so reset the non-slip timer
    routineTimer.reset()
    
    # --- Prepare to start Routine "TriggerWait" ---
    # create an object to store info about Routine TriggerWait
    TriggerWait = data.Routine(
        name='TriggerWait',
        components=[trigger_text, trigger_key],
    )
    TriggerWait.status = NOT_STARTED
    continueRoutine = True
    # update component parameters for each repeat
    # Run 'Begin Routine' code from trigger_code
    if not getattr(args, 'fmri_mode', False):
        continueRoutine = False
    else:
        markers.send('trigger_wait_start', 105)
        dummy_n = getattr(args, 'dummy_scans', 5)
        tr_val = getattr(args, 'tr_s', 2.0)
        wait_s = dummy_n * tr_val
        tr_keys = getattr(args, 'trigger_keys', ['s'])
        tr_keys_str = ', '.join(tr_keys) if isinstance(tr_keys, list) else str(tr_keys)
        msg = f'fMRI Scanner Session\n\nWaiting for scanner trigger ({tr_keys_str})...\n\n(Equilibration: {dummy_n} TRs = {wait_s:.1f}s)'
        trigger_text.setText(msg)
    
    # create starting attributes for trigger_key
    trigger_key.keys = []
    trigger_key.rt = []
    _trigger_key_allKeys = []
    # store start times for TriggerWait
    TriggerWait.tStartRefresh = win.getFutureFlipTime(clock=globalClock)
    TriggerWait.tStart = globalClock.getTime(format='float')
    TriggerWait.status = STARTED
    thisExp.addData('TriggerWait.started', TriggerWait.tStart)
    TriggerWait.maxDuration = None
    # keep track of which components have finished
    TriggerWaitComponents = TriggerWait.components
    for thisComponent in TriggerWait.components:
        thisComponent.tStart = None
        thisComponent.tStop = None
        thisComponent.tStartRefresh = None
        thisComponent.tStopRefresh = None
        if hasattr(thisComponent, 'status'):
            thisComponent.status = NOT_STARTED
    # reset timers
    t = 0
    _timeToFirstFrame = win.getFutureFlipTime(clock="now")
    frameN = -1
    
    # --- Run Routine "TriggerWait" ---
    thisExp.currentRoutine = TriggerWait
    TriggerWait.forceEnded = routineForceEnded = not continueRoutine
    while continueRoutine:
        # get current time
        t = routineTimer.getTime()
        tThisFlip = win.getFutureFlipTime(clock=routineTimer)
        tThisFlipGlobal = win.getFutureFlipTime(clock=None)
        frameN = frameN + 1  # number of completed frames (so 0 is the first frame)
        # update/draw components on each frame
        
        # *trigger_text* updates
        
        # if trigger_text is starting this frame...
        if trigger_text.status == NOT_STARTED and tThisFlip >= 0.0-frameTolerance:
            # keep track of start time/frame for later
            trigger_text.frameNStart = frameN  # exact frame index
            trigger_text.tStart = t  # local t and not account for scr refresh
            trigger_text.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(trigger_text, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'trigger_text.started')
            # update status
            trigger_text.status = STARTED
            trigger_text.setAutoDraw(True)
        
        # if trigger_text is active this frame...
        if trigger_text.status == STARTED:
            # update params
            pass
        
        # *trigger_key* updates
        waitOnFlip = False
        
        # if trigger_key is starting this frame...
        if trigger_key.status == NOT_STARTED and tThisFlip >= 0.0-frameTolerance:
            # keep track of start time/frame for later
            trigger_key.frameNStart = frameN  # exact frame index
            trigger_key.tStart = t  # local t and not account for scr refresh
            trigger_key.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(trigger_key, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'trigger_key.started')
            # update status
            trigger_key.status = STARTED
            # keyboard checking is just starting
            waitOnFlip = True
            win.callOnFlip(trigger_key.clock.reset)  # t=0 on next screen flip
            win.callOnFlip(trigger_key.clearEvents, eventType='keyboard')  # clear events on next screen flip
        if trigger_key.status == STARTED and not waitOnFlip:
            theseKeys = trigger_key.getKeys(keyList=['s', 'space', '4', '9'], ignoreKeys=["escape"], waitRelease=False)
            _trigger_key_allKeys.extend(theseKeys)
            if len(_trigger_key_allKeys):
                trigger_key.keys = _trigger_key_allKeys[-1].name  # just the last key pressed
                trigger_key.rt = _trigger_key_allKeys[-1].rt
                trigger_key.duration = _trigger_key_allKeys[-1].duration
                # a response ends the routine
                continueRoutine = False
        
        # check for quit (typically the Esc key)
        if defaultKeyboard.getKeys(keyList=["escape"]):
            thisExp.status = FINISHED
        if thisExp.status == FINISHED or endExpNow:
            endExperiment(thisExp, win=win)
            return
        # pause experiment here if requested
        if thisExp.status == PAUSED:
            pauseExperiment(
                thisExp=thisExp, 
                win=win, 
                timers=[routineTimer, globalClock], 
                currentRoutine=TriggerWait,
            )
            # skip the frame we paused on
            continue
        
        # has a Component requested the Routine to end?
        if not continueRoutine:
            TriggerWait.forceEnded = routineForceEnded = True
        # has the Routine been forcibly ended?
        if TriggerWait.forceEnded or routineForceEnded:
            break
        # has every Component finished?
        continueRoutine = False
        for thisComponent in TriggerWait.components:
            if hasattr(thisComponent, "status") and thisComponent.status != FINISHED:
                continueRoutine = True
                break  # at least one component has not yet finished
        
        # refresh the screen
        if continueRoutine:  # don't flip if this routine is over or we'll get a blank screen
            win.flip()
    
    # --- Ending Routine "TriggerWait" ---
    for thisComponent in TriggerWait.components:
        if hasattr(thisComponent, "setAutoDraw"):
            thisComponent.setAutoDraw(False)
    # store stop times for TriggerWait
    TriggerWait.tStop = globalClock.getTime(format='float')
    TriggerWait.tStopRefresh = tThisFlipGlobal
    thisExp.addData('TriggerWait.stopped', TriggerWait.tStop)
    # Run 'End Routine' code from trigger_code
    if getattr(args, 'fmri_mode', False):
        trig_t = exp_clock.getTime()
        args.trigger_onset_global = trig_t
        markers.send('trigger_received', 106)
        markers.record_trigger_onset(trig_t)
        dummy_n = getattr(args, 'dummy_scans', 5)
        tr_val = getattr(args, 'tr_s', 2.0)
        wait_s = dummy_n * tr_val
        if wait_s > 0:
            eq_start = exp_clock.getTime()
            while exp_clock.getTime() - eq_start < wait_s:
                rem = wait_s - (exp_clock.getTime() - eq_start)
                trigger_text.setText(f'Scanner Trigger Received!\n\nEquilibrating dummy scans...\n\n{rem:.1f}s remaining')
                trigger_text.draw()
                win.flip()
                if event.getKeys(keyList=['escape']):
                    raise KeyboardInterrupt
    
    # check responses
    if trigger_key.keys in ['', [], None]:  # No response was made
        trigger_key.keys = None
    thisExp.addData('trigger_key.keys',trigger_key.keys)
    if trigger_key.keys != None:  # we had a response
        thisExp.addData('trigger_key.rt', trigger_key.rt)
        thisExp.addData('trigger_key.duration', trigger_key.duration)
    thisExp.nextEntry()
    # the Routine "TriggerWait" was not non-slip safe, so reset the non-slip timer
    routineTimer.reset()
    
    # --- Prepare to start Routine "TrialRoutine" ---
    # create an object to store info about Routine TrialRoutine
    TrialRoutine = data.Routine(
        name='TrialRoutine',
        components=[fixation, left_mask, right_mask, target_stim, top_distractor, bottom_distractor, response_key],
    )
    TrialRoutine.status = NOT_STARTED
    continueRoutine = True
    # update component parameters for each repeat
    # create starting attributes for response_key
    response_key.keys = []
    response_key.rt = []
    _response_key_allKeys = []
    # Run 'Begin Routine' code from trial_runner
    # ==============================================================================
    # ANGEL MAIN SESSION CONTROLLER
    # ==============================================================================
    active_trials, baseline_trials = engine.parse_trials_per_block(args.trials_per_block)
    block_trial_count = active_trials + baseline_trials
    total_main_trials = args.blocks * block_trial_count
    for level in levels:
        assets = assets_by_level[level]
        stimuli = engine.make_stimuli(win, visual, assets)
        audio_cache = engine.make_audio_cache(sound, assets)
        block_rows = []
        for trial in engine.generate_level_trials(
            level, args.blocks, rng, args.category_set,
            args.paired_tone_offset_mode, args.paired_tone_offset_min,
            args.paired_tone_offset_max, args.cd_schedule,
            active_trials, baseline_trials, args.level2_cd
        ):
            if trial.trial_in_block == 1:
                markers.send('block_start', 1)
            trial_counter += 1
            block_name = f'level{level}_block{trial.block:02d}'
            row = engine.run_trial(
                trial, args, win, core, event, visual, sound, stimuli,
                assets, audio_cache, rng, trial_counter, exp_clock, markers, block_name
            )
            row['phase'] = 'main'
            block_rows.append(row)
            main_session_rows.append(row)
            for k, v in row.items():
                thisExp.addData(k, v)
            thisExp.nextEntry()
            # Mid-block feedback (only if show_feedback is True)
            if getattr(args, 'show_feedback', True) and trial.trial_in_block == block_trial_count and trial.block % getattr(args, 'feedback_frequency', 2) == 0:
                markers.send('feedback_start', 107)
                engine.show_feedback(
                    win, event, visual, sound, assets['language'],
                    block_rows[-2 * block_trial_count:],
                    len(block_rows), total_main_trials
                )
                markers.send('feedback_end', 108)
            # Level 2 Reversal Rule Slide (at halfway point)
            if level == '2' and trial.block == args.blocks // 2 and trial.trial_in_block == block_trial_count:
                markers.send('reversal_rule_start', 109)
                rev_text = 'Rule change\n\nMeaningful: RIGHT\nAmbiguous: LEFT'
                if getattr(args, 'passive_mode', False):
                    rev_text += '\n\nContinuing automatically...'
                else:
                    rev_text += f'\n\nPress {engine._continue_hint()} to continue'
                reversal = visual.TextStim(win, text=rev_text, color='white', height=0.04, units='height')
                reversal.draw()
                win.flip()
                engine.wait_for_continue(event, timeout=getattr(args, 'slide_timeout', 5.0))
                markers.send('reversal_rule_end', 110)
        # Level Session Summary (only if show_feedback is True)
        if getattr(args, 'show_feedback', True):
            engine.show_session_summary(win, event, visual, sound, assets['language'], block_rows, label=f'Level {level} Session')
    # Export fMRI Events CSV and Marker Log if in fMRI mode
    if getattr(args, 'fmri_mode', False) and getattr(args, 'trigger_onset_global', None) is not None:
        from pathlib import Path
        csv_p = Path(thisExp.dataFileName + '.csv')
        events_p = csv_p.with_name(csv_p.stem + '_fmri_events.csv')
        engine.save_fmri_events(events_p, main_session_rows, args.trigger_onset_global)
        markers_p = csv_p.with_name(csv_p.stem + '_markers.csv')
        markers.save_log(markers_p)
    continueRoutine = False
    
    # store start times for TrialRoutine
    TrialRoutine.tStartRefresh = win.getFutureFlipTime(clock=globalClock)
    TrialRoutine.tStart = globalClock.getTime(format='float')
    TrialRoutine.status = STARTED
    thisExp.addData('TrialRoutine.started', TrialRoutine.tStart)
    TrialRoutine.maxDuration = None
    # keep track of which components have finished
    TrialRoutineComponents = TrialRoutine.components
    for thisComponent in TrialRoutine.components:
        thisComponent.tStart = None
        thisComponent.tStop = None
        thisComponent.tStartRefresh = None
        thisComponent.tStopRefresh = None
        if hasattr(thisComponent, 'status'):
            thisComponent.status = NOT_STARTED
    # reset timers
    t = 0
    _timeToFirstFrame = win.getFutureFlipTime(clock="now")
    frameN = -1
    
    # --- Run Routine "TrialRoutine" ---
    thisExp.currentRoutine = TrialRoutine
    TrialRoutine.forceEnded = routineForceEnded = not continueRoutine
    while continueRoutine and routineTimer.getTime() < 1.5:
        # get current time
        t = routineTimer.getTime()
        tThisFlip = win.getFutureFlipTime(clock=routineTimer)
        tThisFlipGlobal = win.getFutureFlipTime(clock=None)
        frameN = frameN + 1  # number of completed frames (so 0 is the first frame)
        # update/draw components on each frame
        
        # *fixation* updates
        
        # if fixation is starting this frame...
        if fixation.status == NOT_STARTED and tThisFlip >= 0.0-frameTolerance:
            # keep track of start time/frame for later
            fixation.frameNStart = frameN  # exact frame index
            fixation.tStart = t  # local t and not account for scr refresh
            fixation.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(fixation, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'fixation.started')
            # update status
            fixation.status = STARTED
            fixation.setAutoDraw(True)
        
        # if fixation is active this frame...
        if fixation.status == STARTED:
            # update params
            pass
        
        # if fixation is stopping this frame...
        if fixation.status == STARTED:
            # is it time to stop? (based on global clock, using actual start)
            if tThisFlipGlobal > fixation.tStartRefresh + 1.5-frameTolerance:
                # keep track of stop time/frame for later
                fixation.tStop = t  # not accounting for scr refresh
                fixation.tStopRefresh = tThisFlipGlobal  # on global time
                fixation.frameNStop = frameN  # exact frame index
                # add timestamp to datafile
                thisExp.timestampOnFlip(win, 'fixation.stopped')
                # update status
                fixation.status = FINISHED
                fixation.setAutoDraw(False)
        
        # *left_mask* updates
        
        # if left_mask is starting this frame...
        if left_mask.status == NOT_STARTED and tThisFlip >= 0.0-frameTolerance:
            # keep track of start time/frame for later
            left_mask.frameNStart = frameN  # exact frame index
            left_mask.tStart = t  # local t and not account for scr refresh
            left_mask.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(left_mask, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'left_mask.started')
            # update status
            left_mask.status = STARTED
            left_mask.setAutoDraw(True)
        
        # if left_mask is active this frame...
        if left_mask.status == STARTED:
            # update params
            pass
        
        # if left_mask is stopping this frame...
        if left_mask.status == STARTED:
            # is it time to stop? (based on global clock, using actual start)
            if tThisFlipGlobal > left_mask.tStartRefresh + 1.5-frameTolerance:
                # keep track of stop time/frame for later
                left_mask.tStop = t  # not accounting for scr refresh
                left_mask.tStopRefresh = tThisFlipGlobal  # on global time
                left_mask.frameNStop = frameN  # exact frame index
                # add timestamp to datafile
                thisExp.timestampOnFlip(win, 'left_mask.stopped')
                # update status
                left_mask.status = FINISHED
                left_mask.setAutoDraw(False)
        
        # *right_mask* updates
        
        # if right_mask is starting this frame...
        if right_mask.status == NOT_STARTED and tThisFlip >= 0.0-frameTolerance:
            # keep track of start time/frame for later
            right_mask.frameNStart = frameN  # exact frame index
            right_mask.tStart = t  # local t and not account for scr refresh
            right_mask.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(right_mask, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'right_mask.started')
            # update status
            right_mask.status = STARTED
            right_mask.setAutoDraw(True)
        
        # if right_mask is active this frame...
        if right_mask.status == STARTED:
            # update params
            pass
        
        # if right_mask is stopping this frame...
        if right_mask.status == STARTED:
            # is it time to stop? (based on global clock, using actual start)
            if tThisFlipGlobal > right_mask.tStartRefresh + 1.5-frameTolerance:
                # keep track of stop time/frame for later
                right_mask.tStop = t  # not accounting for scr refresh
                right_mask.tStopRefresh = tThisFlipGlobal  # on global time
                right_mask.frameNStop = frameN  # exact frame index
                # add timestamp to datafile
                thisExp.timestampOnFlip(win, 'right_mask.stopped')
                # update status
                right_mask.status = FINISHED
                right_mask.setAutoDraw(False)
        
        # *target_stim* updates
        
        # if target_stim is starting this frame...
        if target_stim.status == NOT_STARTED and tThisFlip >= 0.24-frameTolerance:
            # keep track of start time/frame for later
            target_stim.frameNStart = frameN  # exact frame index
            target_stim.tStart = t  # local t and not account for scr refresh
            target_stim.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(target_stim, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'target_stim.started')
            # update status
            target_stim.status = STARTED
            target_stim.setAutoDraw(True)
        
        # if target_stim is active this frame...
        if target_stim.status == STARTED:
            # update params
            pass
        
        # if target_stim is stopping this frame...
        if target_stim.status == STARTED:
            # is it time to stop? (based on global clock, using actual start)
            if tThisFlipGlobal > target_stim.tStartRefresh + 0.24-frameTolerance:
                # keep track of stop time/frame for later
                target_stim.tStop = t  # not accounting for scr refresh
                target_stim.tStopRefresh = tThisFlipGlobal  # on global time
                target_stim.frameNStop = frameN  # exact frame index
                # add timestamp to datafile
                thisExp.timestampOnFlip(win, 'target_stim.stopped')
                # update status
                target_stim.status = FINISHED
                target_stim.setAutoDraw(False)
        
        # *top_distractor* updates
        
        # if top_distractor is starting this frame...
        if top_distractor.status == NOT_STARTED and tThisFlip >= 0.24-frameTolerance:
            # keep track of start time/frame for later
            top_distractor.frameNStart = frameN  # exact frame index
            top_distractor.tStart = t  # local t and not account for scr refresh
            top_distractor.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(top_distractor, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'top_distractor.started')
            # update status
            top_distractor.status = STARTED
            top_distractor.setAutoDraw(True)
        
        # if top_distractor is active this frame...
        if top_distractor.status == STARTED:
            # update params
            pass
        
        # if top_distractor is stopping this frame...
        if top_distractor.status == STARTED:
            # is it time to stop? (based on global clock, using actual start)
            if tThisFlipGlobal > top_distractor.tStartRefresh + 0.24-frameTolerance:
                # keep track of stop time/frame for later
                top_distractor.tStop = t  # not accounting for scr refresh
                top_distractor.tStopRefresh = tThisFlipGlobal  # on global time
                top_distractor.frameNStop = frameN  # exact frame index
                # add timestamp to datafile
                thisExp.timestampOnFlip(win, 'top_distractor.stopped')
                # update status
                top_distractor.status = FINISHED
                top_distractor.setAutoDraw(False)
        
        # *bottom_distractor* updates
        
        # if bottom_distractor is starting this frame...
        if bottom_distractor.status == NOT_STARTED and tThisFlip >= 0.24-frameTolerance:
            # keep track of start time/frame for later
            bottom_distractor.frameNStart = frameN  # exact frame index
            bottom_distractor.tStart = t  # local t and not account for scr refresh
            bottom_distractor.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(bottom_distractor, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'bottom_distractor.started')
            # update status
            bottom_distractor.status = STARTED
            bottom_distractor.setAutoDraw(True)
        
        # if bottom_distractor is active this frame...
        if bottom_distractor.status == STARTED:
            # update params
            pass
        
        # if bottom_distractor is stopping this frame...
        if bottom_distractor.status == STARTED:
            # is it time to stop? (based on global clock, using actual start)
            if tThisFlipGlobal > bottom_distractor.tStartRefresh + 0.24-frameTolerance:
                # keep track of stop time/frame for later
                bottom_distractor.tStop = t  # not accounting for scr refresh
                bottom_distractor.tStopRefresh = tThisFlipGlobal  # on global time
                bottom_distractor.frameNStop = frameN  # exact frame index
                # add timestamp to datafile
                thisExp.timestampOnFlip(win, 'bottom_distractor.stopped')
                # update status
                bottom_distractor.status = FINISHED
                bottom_distractor.setAutoDraw(False)
        
        # *response_key* updates
        waitOnFlip = False
        
        # if response_key is starting this frame...
        if response_key.status == NOT_STARTED and tThisFlip >= 0.24-frameTolerance:
            # keep track of start time/frame for later
            response_key.frameNStart = frameN  # exact frame index
            response_key.tStart = t  # local t and not account for scr refresh
            response_key.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(response_key, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'response_key.started')
            # update status
            response_key.status = STARTED
            # keyboard checking is just starting
            waitOnFlip = True
            win.callOnFlip(response_key.clock.reset)  # t=0 on next screen flip
            win.callOnFlip(response_key.clearEvents, eventType='keyboard')  # clear events on next screen flip
        
        # if response_key is stopping this frame...
        if response_key.status == STARTED:
            # is it time to stop? (based on global clock, using actual start)
            if tThisFlipGlobal > response_key.tStartRefresh + 0.70-frameTolerance:
                # keep track of stop time/frame for later
                response_key.tStop = t  # not accounting for scr refresh
                response_key.tStopRefresh = tThisFlipGlobal  # on global time
                response_key.frameNStop = frameN  # exact frame index
                # add timestamp to datafile
                thisExp.timestampOnFlip(win, 'response_key.stopped')
                # update status
                response_key.status = FINISHED
                response_key.status = FINISHED
        if response_key.status == STARTED and not waitOnFlip:
            theseKeys = response_key.getKeys(keyList=['left', 'right', 'z', 'slash', '1', '2', '4', '9'], ignoreKeys=["escape"], waitRelease=False)
            _response_key_allKeys.extend(theseKeys)
            if len(_response_key_allKeys):
                response_key.keys = _response_key_allKeys[-1].name  # just the last key pressed
                response_key.rt = _response_key_allKeys[-1].rt
                response_key.duration = _response_key_allKeys[-1].duration
        
        # check for quit (typically the Esc key)
        if defaultKeyboard.getKeys(keyList=["escape"]):
            thisExp.status = FINISHED
        if thisExp.status == FINISHED or endExpNow:
            endExperiment(thisExp, win=win)
            return
        # pause experiment here if requested
        if thisExp.status == PAUSED:
            pauseExperiment(
                thisExp=thisExp, 
                win=win, 
                timers=[routineTimer, globalClock], 
                currentRoutine=TrialRoutine,
            )
            # skip the frame we paused on
            continue
        
        # has a Component requested the Routine to end?
        if not continueRoutine:
            TrialRoutine.forceEnded = routineForceEnded = True
        # has the Routine been forcibly ended?
        if TrialRoutine.forceEnded or routineForceEnded:
            break
        # has every Component finished?
        continueRoutine = False
        for thisComponent in TrialRoutine.components:
            if hasattr(thisComponent, "status") and thisComponent.status != FINISHED:
                continueRoutine = True
                break  # at least one component has not yet finished
        
        # refresh the screen
        if continueRoutine:  # don't flip if this routine is over or we'll get a blank screen
            win.flip()
    
    # --- Ending Routine "TrialRoutine" ---
    for thisComponent in TrialRoutine.components:
        if hasattr(thisComponent, "setAutoDraw"):
            thisComponent.setAutoDraw(False)
    # store stop times for TrialRoutine
    TrialRoutine.tStop = globalClock.getTime(format='float')
    TrialRoutine.tStopRefresh = tThisFlipGlobal
    thisExp.addData('TrialRoutine.stopped', TrialRoutine.tStop)
    # check responses
    if response_key.keys in ['', [], None]:  # No response was made
        response_key.keys = None
    thisExp.addData('response_key.keys',response_key.keys)
    if response_key.keys != None:  # we had a response
        thisExp.addData('response_key.rt', response_key.rt)
        thisExp.addData('response_key.duration', response_key.duration)
    # using non-slip timing so subtract the expected duration of this Routine (unless ended on request)
    if TrialRoutine.maxDurationReached:
        routineTimer.addTime(-TrialRoutine.maxDuration)
    elif TrialRoutine.forceEnded:
        routineTimer.reset()
    else:
        routineTimer.addTime(-1.500000)
    thisExp.nextEntry()
    
    # --- Prepare to start Routine "Feedback" ---
    # create an object to store info about Routine Feedback
    Feedback = data.Routine(
        name='Feedback',
        components=[feedback_image, feedback_text, feedback_key],
    )
    Feedback.status = NOT_STARTED
    continueRoutine = True
    # update component parameters for each repeat
    # Run 'Begin Routine' code from feedback_code
    if not getattr(args, 'show_feedback', True):
        continueRoutine = False
    else:
        if getattr(args, 'passive_mode', False):
            feedback_text.setText('Session Complete!\n\nContinuing automatically...')
    
    # create starting attributes for feedback_key
    feedback_key.keys = []
    feedback_key.rt = []
    _feedback_key_allKeys = []
    # store start times for Feedback
    Feedback.tStartRefresh = win.getFutureFlipTime(clock=globalClock)
    Feedback.tStart = globalClock.getTime(format='float')
    Feedback.status = STARTED
    thisExp.addData('Feedback.started', Feedback.tStart)
    Feedback.maxDuration = None
    # keep track of which components have finished
    FeedbackComponents = Feedback.components
    for thisComponent in Feedback.components:
        thisComponent.tStart = None
        thisComponent.tStop = None
        thisComponent.tStartRefresh = None
        thisComponent.tStopRefresh = None
        if hasattr(thisComponent, 'status'):
            thisComponent.status = NOT_STARTED
    # reset timers
    t = 0
    _timeToFirstFrame = win.getFutureFlipTime(clock="now")
    frameN = -1
    
    # --- Run Routine "Feedback" ---
    thisExp.currentRoutine = Feedback
    Feedback.forceEnded = routineForceEnded = not continueRoutine
    while continueRoutine:
        # get current time
        t = routineTimer.getTime()
        tThisFlip = win.getFutureFlipTime(clock=routineTimer)
        tThisFlipGlobal = win.getFutureFlipTime(clock=None)
        frameN = frameN + 1  # number of completed frames (so 0 is the first frame)
        # update/draw components on each frame
        
        # *feedback_image* updates
        
        # if feedback_image is starting this frame...
        if feedback_image.status == NOT_STARTED and tThisFlip >= 0.0-frameTolerance:
            # keep track of start time/frame for later
            feedback_image.frameNStart = frameN  # exact frame index
            feedback_image.tStart = t  # local t and not account for scr refresh
            feedback_image.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(feedback_image, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'feedback_image.started')
            # update status
            feedback_image.status = STARTED
            feedback_image.setAutoDraw(True)
        
        # if feedback_image is active this frame...
        if feedback_image.status == STARTED:
            # update params
            pass
        
        # *feedback_text* updates
        
        # if feedback_text is starting this frame...
        if feedback_text.status == NOT_STARTED and tThisFlip >= 0.0-frameTolerance:
            # keep track of start time/frame for later
            feedback_text.frameNStart = frameN  # exact frame index
            feedback_text.tStart = t  # local t and not account for scr refresh
            feedback_text.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(feedback_text, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'feedback_text.started')
            # update status
            feedback_text.status = STARTED
            feedback_text.setAutoDraw(True)
        
        # if feedback_text is active this frame...
        if feedback_text.status == STARTED:
            # update params
            pass
        
        # *feedback_key* updates
        waitOnFlip = False
        
        # if feedback_key is starting this frame...
        if feedback_key.status == NOT_STARTED and tThisFlip >= 0.0-frameTolerance:
            # keep track of start time/frame for later
            feedback_key.frameNStart = frameN  # exact frame index
            feedback_key.tStart = t  # local t and not account for scr refresh
            feedback_key.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(feedback_key, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'feedback_key.started')
            # update status
            feedback_key.status = STARTED
            # keyboard checking is just starting
            waitOnFlip = True
            win.callOnFlip(feedback_key.clock.reset)  # t=0 on next screen flip
            win.callOnFlip(feedback_key.clearEvents, eventType='keyboard')  # clear events on next screen flip
        
        # if feedback_key is stopping this frame...
        if feedback_key.status == STARTED:
            # is it time to stop? (based on global clock, using actual start)
            if tThisFlipGlobal > feedback_key.tStartRefresh + (getattr(args, 'slide_timeout', 5.0) if getattr(args, 'slide_timeout', 5.0) > 0 else 999999.0)-frameTolerance:
                # keep track of stop time/frame for later
                feedback_key.tStop = t  # not accounting for scr refresh
                feedback_key.tStopRefresh = tThisFlipGlobal  # on global time
                feedback_key.frameNStop = frameN  # exact frame index
                # add timestamp to datafile
                thisExp.timestampOnFlip(win, 'feedback_key.stopped')
                # update status
                feedback_key.status = FINISHED
                feedback_key.status = FINISHED
        if feedback_key.status == STARTED and not waitOnFlip:
            theseKeys = feedback_key.getKeys(keyList=None, ignoreKeys=["escape"], waitRelease=False)
            _feedback_key_allKeys.extend(theseKeys)
            if len(_feedback_key_allKeys):
                feedback_key.keys = _feedback_key_allKeys[-1].name  # just the last key pressed
                feedback_key.rt = _feedback_key_allKeys[-1].rt
                feedback_key.duration = _feedback_key_allKeys[-1].duration
                # a response ends the routine
                continueRoutine = False
        
        # check for quit (typically the Esc key)
        if defaultKeyboard.getKeys(keyList=["escape"]):
            thisExp.status = FINISHED
        if thisExp.status == FINISHED or endExpNow:
            endExperiment(thisExp, win=win)
            return
        # pause experiment here if requested
        if thisExp.status == PAUSED:
            pauseExperiment(
                thisExp=thisExp, 
                win=win, 
                timers=[routineTimer, globalClock], 
                currentRoutine=Feedback,
            )
            # skip the frame we paused on
            continue
        
        # has a Component requested the Routine to end?
        if not continueRoutine:
            Feedback.forceEnded = routineForceEnded = True
        # has the Routine been forcibly ended?
        if Feedback.forceEnded or routineForceEnded:
            break
        # has every Component finished?
        continueRoutine = False
        for thisComponent in Feedback.components:
            if hasattr(thisComponent, "status") and thisComponent.status != FINISHED:
                continueRoutine = True
                break  # at least one component has not yet finished
        
        # refresh the screen
        if continueRoutine:  # don't flip if this routine is over or we'll get a blank screen
            win.flip()
    
    # --- Ending Routine "Feedback" ---
    for thisComponent in Feedback.components:
        if hasattr(thisComponent, "setAutoDraw"):
            thisComponent.setAutoDraw(False)
    # store stop times for Feedback
    Feedback.tStop = globalClock.getTime(format='float')
    Feedback.tStopRefresh = tThisFlipGlobal
    thisExp.addData('Feedback.stopped', Feedback.tStop)
    # check responses
    if feedback_key.keys in ['', [], None]:  # No response was made
        feedback_key.keys = None
    thisExp.addData('feedback_key.keys',feedback_key.keys)
    if feedback_key.keys != None:  # we had a response
        thisExp.addData('feedback_key.rt', feedback_key.rt)
        thisExp.addData('feedback_key.duration', feedback_key.duration)
    thisExp.nextEntry()
    # the Routine "Feedback" was not non-slip safe, so reset the non-slip timer
    routineTimer.reset()
    
    # --- Prepare to start Routine "End" ---
    # create an object to store info about Routine End
    End = data.Routine(
        name='End',
        components=[end_image, end_key],
    )
    End.status = NOT_STARTED
    continueRoutine = True
    # update component parameters for each repeat
    # Run 'Begin Routine' code from end_code
    markers.send('experiment_end', 99)
    
    # create starting attributes for end_key
    end_key.keys = []
    end_key.rt = []
    _end_key_allKeys = []
    # store start times for End
    End.tStartRefresh = win.getFutureFlipTime(clock=globalClock)
    End.tStart = globalClock.getTime(format='float')
    End.status = STARTED
    thisExp.addData('End.started', End.tStart)
    End.maxDuration = None
    # keep track of which components have finished
    EndComponents = End.components
    for thisComponent in End.components:
        thisComponent.tStart = None
        thisComponent.tStop = None
        thisComponent.tStartRefresh = None
        thisComponent.tStopRefresh = None
        if hasattr(thisComponent, 'status'):
            thisComponent.status = NOT_STARTED
    # reset timers
    t = 0
    _timeToFirstFrame = win.getFutureFlipTime(clock="now")
    frameN = -1
    
    # --- Run Routine "End" ---
    thisExp.currentRoutine = End
    End.forceEnded = routineForceEnded = not continueRoutine
    while continueRoutine:
        # get current time
        t = routineTimer.getTime()
        tThisFlip = win.getFutureFlipTime(clock=routineTimer)
        tThisFlipGlobal = win.getFutureFlipTime(clock=None)
        frameN = frameN + 1  # number of completed frames (so 0 is the first frame)
        # update/draw components on each frame
        
        # *end_image* updates
        
        # if end_image is starting this frame...
        if end_image.status == NOT_STARTED and tThisFlip >= 0.0-frameTolerance:
            # keep track of start time/frame for later
            end_image.frameNStart = frameN  # exact frame index
            end_image.tStart = t  # local t and not account for scr refresh
            end_image.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(end_image, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'end_image.started')
            # update status
            end_image.status = STARTED
            end_image.setAutoDraw(True)
        
        # if end_image is active this frame...
        if end_image.status == STARTED:
            # update params
            pass
        
        # *end_key* updates
        waitOnFlip = False
        
        # if end_key is starting this frame...
        if end_key.status == NOT_STARTED and tThisFlip >= 0.0-frameTolerance:
            # keep track of start time/frame for later
            end_key.frameNStart = frameN  # exact frame index
            end_key.tStart = t  # local t and not account for scr refresh
            end_key.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(end_key, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'end_key.started')
            # update status
            end_key.status = STARTED
            # keyboard checking is just starting
            waitOnFlip = True
            win.callOnFlip(end_key.clock.reset)  # t=0 on next screen flip
            win.callOnFlip(end_key.clearEvents, eventType='keyboard')  # clear events on next screen flip
        
        # if end_key is stopping this frame...
        if end_key.status == STARTED:
            # is it time to stop? (based on global clock, using actual start)
            if tThisFlipGlobal > end_key.tStartRefresh + (getattr(args, 'slide_timeout', 5.0) if getattr(args, 'slide_timeout', 5.0) > 0 else 999999.0)-frameTolerance:
                # keep track of stop time/frame for later
                end_key.tStop = t  # not accounting for scr refresh
                end_key.tStopRefresh = tThisFlipGlobal  # on global time
                end_key.frameNStop = frameN  # exact frame index
                # add timestamp to datafile
                thisExp.timestampOnFlip(win, 'end_key.stopped')
                # update status
                end_key.status = FINISHED
                end_key.status = FINISHED
        if end_key.status == STARTED and not waitOnFlip:
            theseKeys = end_key.getKeys(keyList=None, ignoreKeys=["escape"], waitRelease=False)
            _end_key_allKeys.extend(theseKeys)
            if len(_end_key_allKeys):
                end_key.keys = _end_key_allKeys[-1].name  # just the last key pressed
                end_key.rt = _end_key_allKeys[-1].rt
                end_key.duration = _end_key_allKeys[-1].duration
                # a response ends the routine
                continueRoutine = False
        
        # check for quit (typically the Esc key)
        if defaultKeyboard.getKeys(keyList=["escape"]):
            thisExp.status = FINISHED
        if thisExp.status == FINISHED or endExpNow:
            endExperiment(thisExp, win=win)
            return
        # pause experiment here if requested
        if thisExp.status == PAUSED:
            pauseExperiment(
                thisExp=thisExp, 
                win=win, 
                timers=[routineTimer, globalClock], 
                currentRoutine=End,
            )
            # skip the frame we paused on
            continue
        
        # has a Component requested the Routine to end?
        if not continueRoutine:
            End.forceEnded = routineForceEnded = True
        # has the Routine been forcibly ended?
        if End.forceEnded or routineForceEnded:
            break
        # has every Component finished?
        continueRoutine = False
        for thisComponent in End.components:
            if hasattr(thisComponent, "status") and thisComponent.status != FINISHED:
                continueRoutine = True
                break  # at least one component has not yet finished
        
        # refresh the screen
        if continueRoutine:  # don't flip if this routine is over or we'll get a blank screen
            win.flip()
    
    # --- Ending Routine "End" ---
    for thisComponent in End.components:
        if hasattr(thisComponent, "setAutoDraw"):
            thisComponent.setAutoDraw(False)
    # store stop times for End
    End.tStop = globalClock.getTime(format='float')
    End.tStopRefresh = tThisFlipGlobal
    thisExp.addData('End.stopped', End.tStop)
    # check responses
    if end_key.keys in ['', [], None]:  # No response was made
        end_key.keys = None
    thisExp.addData('end_key.keys',end_key.keys)
    if end_key.keys != None:  # we had a response
        thisExp.addData('end_key.rt', end_key.rt)
        thisExp.addData('end_key.duration', end_key.duration)
    thisExp.nextEntry()
    # the Routine "End" was not non-slip safe, so reset the non-slip timer
    routineTimer.reset()
    # Run 'End Experiment' code from init_code
    engine.clear_sound_cache()
    import time as _time
    _time.sleep(0.3)
    markers.close()
    
    
    # mark experiment as finished
    endExperiment(thisExp, win=win)


def saveData(thisExp):
    """
    Save data from this experiment
    
    Parameters
    ==========
    thisExp : psychopy.data.ExperimentHandler
        Handler object for this experiment, contains the data to save and information about 
        where to save it to.
    """
    filename = thisExp.dataFileName
    # these shouldn't be strictly necessary (should auto-save)
    thisExp.saveAsWideText(filename + '.csv', delim='auto')
    thisExp.saveAsPickle(filename)


def endExperiment(thisExp, win=None):
    """
    End this experiment, performing final shut down operations.
    
    This function does NOT close the window or end the Python process - use `quit` for this.
    
    Parameters
    ==========
    thisExp : psychopy.data.ExperimentHandler
        Handler object for this experiment, contains the data to save and information about 
        where to save it to.
    win : psychopy.visual.Window
        Window for this experiment.
    """
    # stop any playback components
    if thisExp.currentRoutine is not None:
        for comp in thisExp.currentRoutine.getPlaybackComponents():
            comp.stop()
    if win is not None:
        # remove autodraw from all current components
        win.clearAutoDraw()
        # Flip one final time so any remaining win.callOnFlip() 
        # and win.timeOnFlip() tasks get executed
        win.flip()
    # return console logger level to WARNING
    logging.console.setLevel(logging.WARNING)
    # mark experiment handler as finished
    thisExp.status = FINISHED
    # run any 'at exit' functions
    for fcn in runAtExit:
        fcn()
    logging.flush()


def quit(thisExp, win=None, thisSession=None):
    """
    Fully quit, closing the window and ending the Python process.
    
    Parameters
    ==========
    win : psychopy.visual.Window
        Window to close.
    thisSession : psychopy.session.Session or None
        Handle of the Session object this experiment is being run from, if any.
    """
    thisExp.abort()  # or data files will save again on exit
    # make sure everything is closed down
    if win is not None:
        # Flip one final time so any remaining win.callOnFlip() 
        # and win.timeOnFlip() tasks get executed before quitting
        win.flip()
        win.close()
    logging.flush()
    if thisSession is not None:
        thisSession.stop()
    # terminate Python process
    core.quit()


# if running this experiment as a script...
if __name__ == '__main__':
    # call all functions in order
    thisExp = setupData(expInfo=expInfo)
    logFile = setupLogging(filename=thisExp.dataFileName)
    win = setupWindow(expInfo=expInfo)
    setupDevices(expInfo=expInfo, thisExp=thisExp, win=win)
    run(
        expInfo=expInfo, 
        thisExp=thisExp, 
        win=win,
        globalClock='float'
    )
    saveData(thisExp=thisExp)
    quit(thisExp=thisExp, win=win)
