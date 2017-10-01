'''
Created on Sep 24, 2017

@author: kirk
'''
from six.moves import queue
import pyaudio
from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
from threading import Thread
from pyee import EventEmitter
from stringprep import b1_set
# Audio recording parameters
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms

class MicrophoneStream(object):
    """Opens a recording stream as a generator yielding the audio chunks."""
    def __init__(self, rate=RATE, chunk=CHUNK):
        self._rate = rate
        self._chunk = chunk

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True
        self.muted = False

    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            # The API currently only supports 1-channel (mono) audio
            # https://goo.gl/z757pE
            channels=1, rate=self._rate,
            input=True, frames_per_buffer=self._chunk,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
        )

        self.closed = False

        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()
        
    def close(self):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()
                
    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue
    
    def mute(self):
        self._audio_stream.stop_stream()
        self.muted = True

    def unmute(self):
        while self._buff.qsize()>0:
            print ("qsize %s" % self._buff.qsize() )
            self._buff.get()
        self._audio_stream.start_stream()
        self.muted = False
        
    def generator(self):
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b''.join(data)
# [END audio_stream]

class google_recognizer(EventEmitter):
    def __init__(self):
        super(google_recognizer, self).__init__()       
        self.mic = MicrophoneStream()
        
    def _listen_print_loop(self,responses):
        """Iterates through server responses and prints them.
    
        The responses passed is a generator that will block until a response
        is provided by the server.
    
        Each response may contain multiple results, and each result may contain
        multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
        print only the transcription for the top alternative of the top result.
    
        In this case, responses are provided for interim results as well. If the
        response is an interim one, print a line feed at the end of it, to allow
        the next result to overwrite it, until the response is a final one. For the
        final one, print a newline to preserve the finalized transcription.
        """

        for response in responses:
    
            if not response.results:
                continue
            result = response.results[0]
            if not result.alternatives:
                continue
    
            transcript = result.alternatives[0].transcript
    
            if result.is_final:
                self.emit("UtteranceDetected",transcript)
                return(True)
            
    def start(self):
        self.loop_thread = Thread(target=self._RecognizerLoop)
        self.loop_thread.setDaemon(True)
        self.loop_thread.start()
    
    def stop(self):
        self.mic.close()
            
    def _RecognizerLoop(self):
        mic = MicrophoneStream()
        language_code = 'en-US'  # a BCP-47 language tag
        client = speech.SpeechClient()
        config = types.RecognitionConfig(
            encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=RATE,
            language_code=language_code)
        streaming_config = types.StreamingRecognitionConfig(
            config=config,
            interim_results=True)
        with mic as stream:
            audio_generator = stream.generator()
            requests = (types.StreamingRecognizeRequest(audio_content=content)
                        for content in audio_generator)
    
            responses = client.streaming_recognize(streaming_config, requests)
    
            # Now, put the transcription responses to use.
            if (self._listen_print_loop(responses)):
                exit

    