'''
Created on Sep 24, 2017

@author: kirk
'''
from messagebus.client.ws import WebsocketClient
from messagebus.message import Message
from threading import Thread
from google_mic import google_recognizer

import snowboydecoder
import time
import signal

global listening

def signal_handler(signal, frame):
    global interrupted
    interrupted = True


def interrupt_callback():
    global interrupted
    return interrupted

def handle_open():
    print("connected to mycroft")
    

def handle_startlisten(msg):
    global gloop
    print("handle_startlisten")
    try:
        gloop.start()
    except Exception as e:
        print(e)
    
    ws.emit(Message('recognizer_loop:record_begin'))

def callback_wakeword():
    global detector
    global gloop 
    try:
        if gloop.loop_thread.isAlive():
            print("already listening")
    #        gloop.mic.mute()
            return
    except:
        pass
    print("handle_wakeword")
    payload = {
        'utterance': 'alexa',
        'session': 'ghomie_session',
    }
    ws.emit(Message("recognizer_loop:wakeword",payload))
    snowboydecoder.play_audio_file()
    
def mycroft_connect():
    ws.run_forever()

def detected_utterance(msg):
    global gloop
    global listening
    print("OK GOOGLE %s" % msg)
#    gloop.stop()
    ws.emit(Message("recognizer_loop:record_end"))
    listening = False
    if msg:
        ws.emit(Message("recognizer_loop:utterance",
                        data={'utterances': [msg]}))    
def main():
    global ws
    global gloop
    global detector
    global interrupted
    global listening
    interrupted=False
    listening=False

    model = "resources/alexa/alexa_02092017.umdl"
    
    ws = WebsocketClient('ws://localhost:8181/core')
    ws.on('open', handle_open)
    ws.on('recognizer_loop:wakeword', handle_startlisten)
    ws.on('StartListen', handle_startlisten)
    gloop=google_recognizer()
    gloop.on('UtteranceDetected',detected_utterance)
  
    event_thread = Thread(target=mycroft_connect)
    event_thread.setDaemon(True)
    event_thread.start()
    
    signal.signal(signal.SIGINT, signal_handler)
    detector = snowboydecoder.HotwordDetector(model, sensitivity=0.2)
    time.sleep(1)
    print('Listening...')
    detector.start(detected_callback=callback_wakeword,
           interrupt_check=interrupt_callback,
           sleep_time=0.05)

    detector.terminate()

    
if __name__ == '__main__':
    main()
