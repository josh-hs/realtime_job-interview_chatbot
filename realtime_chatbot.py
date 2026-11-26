#Run with:
#python -m streamlit run realtime_new.py

#SEE LINE 825
# API Key Needed for OpenAI Realtime API


#IMPORT#

import logging
from dotenv import load_dotenv
import time
import threading
import queue
import os

#Audio
import pyaudio
import base64

#Web Socket
import json
from websocket import create_connection, WebSocketConnectionClosedException

#Web Browser
from flask import Flask
from flask_socketio import SocketIO

#User Interface
import streamlit as st
from streamlit_autorefresh import st_autorefresh

#PDF IMPORT
import fitz

#Program Termination
import keyboard
import psutil

#---------------------#

#CONSTANTS#

TEACH_INTRO = ('''Briefly in English start by introducing yourself as ChatGPT and stating your role
               as a teacher teaching an autistic student (the user) about job interview conventions, 
               interview structure and interview expectations. Ask the student if they understand.''')

PRAC_INTRO = ('''Briefly in English start by introducing yourself as ChatGPT and stating your role 
              as an interviewer giving job interview questions to an autistic interviewee (the user) and that 
              you will guide the interviewee in answering the questions. Ask the interviewee if they understand.''')

REAL_INTRO = ('''Briefly in English start by introducing yourself as ChatGPT and stating your role
              as an interviewer that will conduct a realistic interview with an autistic interviewee (the user).
              Ask the interviewee if they understand.''')


#CHATBOT ROLE SECTION#

TEACHER_ROLE = (
'''
    Respond in English only.
    You are ChatGPT playing the role of a professional job interview teacher conducting a formal job interview 
    training session and talking about job interview conventions, interview structure and interview expectations.
    I will play the role of the student interviewee, an undergraduate with autism spectrum disorder.

    Start by briefly explaining each step of an interview, then give explicit explanations on interview conventions, 
    then interview structure then interview expectations then list the types of interview questions with a short 
    description of each, then the STAR (Situation, Task, Action, Result) method for answering behaviour-based 
    questions, and finally how to answer other questions apart from behaviour-based questions.

    Go into detail on each section. Do not suggest practising questions unless the user asks to.
    At the end ask if the student interviewee has any questions.
    When all the sections are covered suggest trying the practice mode.

    Keep the responses brief. Do not rush. Wait for my affirmation or response after each section before proceeding. 
    Ask for me to clarify unclear responses. Keep sections clear and concise. After each of my responses, continue with 
    the next appropriate section, adjusting based on the content of my answers.
    If the interviewee goes on too much of a tangent from the section then gently encourage them to return to the question.
    Remain fully in character as the teacher for the duration of the session.
'''
)

INTERVIEWER_ROLE = (
'''
Respond only in English.
You are ChatGPT acting as a professional interviewer conducting a formal job interview. I am the interviewee, an undergraduate with autism spectrum disorder.

Start by introducing yourself and stating the job and company. Ask the provided questions in order using clear, concise language.

Give brief follow-ups or simple affirmations. Encourage more detail if responses are under 30 seconds or 75 words. Ask for clarification when needed.

Keep responses short and paced. Wait for my reply before continuing, and choose the next appropriate question based on my answers.

If I go off-topic, gently guide me back to the question. Remain fully in character as the interviewer throughout the session.
'''
)


#MODE SELECTION#

PRACTICE_MODE = (
'''
* Guide the interviewee if their answer does not fully address the question.
* Begin with: “Introduce yourself” and then “Tell me about yourself.”
* Encourage more detail if answers are too brief, especially around experience and impact.
* Use supportive, encouraging language and avoid harsh criticism.
* Encourage step-by-step explanations rather than only final answers, and provide hints where needed.
* For behavioural questions, encourage use of the STAR (Situation, Task, Action, Result) method and explain how each section strengthens the answer.
* Provide scaffolded, step-by-step assistance if the interviewee struggles to answer fully.
* After all questions, ask the interviewee to self-reflect on their confidence and what they would improve next time.
* Then provide feedback on clarity, structure, impact, and STAR method performance, including one actionable suggestion for improvement.
'''
)

REALISTIC_MODE = (
'''
    Start the set of questions with asking the interviewee to "Tell me about yourself",
    and DO NOT ASSIST the interviewee with answering questions.

    Give little to no assistance to interviewee in answering questions.
    Reassure the interviewee that they can take their time.
'''
)


#PROMPT LISTING SECTION#
PROMPTS_STRUCTURE = (
'''
    The structure of information is as follows: the interviewee details, the interviewer details and the set of 
    questions.
'''
)


#SCORING CRITERIA/RUBRIC#
BEHAVIOUR_BASED_STAR_SCORING = (
"""
    For Behaviour-Based questions the STAR (Situation, Task, Action, Result) 
    method should be used. The weighting of time spent talking on each section 
    should be around 70% on the Action and 10% each on the Situation, Task and 
    Results. Give each response a STAR score and give the scores at the end of 
    the interview.
    \n Ask questions like "Tell me about a time when..." during these behaviour-based questions
    \n The scoring criteria is as follows:
    \n For an excellent score:
    Answer is well constructed.
    Logical, flowing response.
    Excellent clarity in all descriptions.
    STAR method is used appropriately drawing from relevant examples.
    Provides specific evidence for knowledge, skills and experience.
    Identifies transferable skills.
    Thoughtfully connects skills/experience to the organisation/role demonstrating research and self-reflection.
    Speech tone and diction is clear, coherent and well-paced.
    Body language appropriate and projecting self-assurance.
    Converses well with appropriate questions, introduction and closure.
"""
)


#INTERVIEW QUESTIONING#

OPENING_QUESTIONS = (
'''
    The first question should be "Tell me about yourself." followed by
    "Why did you apply to this internship?".\n
'''
)

RESUME_QUESTIONS = (
'''
    Develop and ask 2 questions about the interviewee's resume on previous experiences, projects or jobs.\n
'''
)

TECHNICAL_QUESTIONS = (
'''
    Develop and ask 2 technical questions for the interview based on the job description.\n
'''
)

BEHAVIOURAL_QUESTIONS = (
'''
    Develop and ask 2 behavioural questions for the interview based on the job description.\n
'''
)

#SITUATIONAL_QUESTIONS = (
#'''
#    Develop and ask 1 situational questions to assess decision-making and professional behaviour.\n
#'''
#)

COMPANY_QUESTIONS = (
'''
    Develop and ask 2 questions to assess interest in, alignment with and long-term potential employment at the company 
    based on the job description and resume.\n
'''
)

FINAL_QUESTION = (
'''
    This is the final question to ask for the interview, "Do you have any questions?".\n
'''
)


#FEEDBACK PROMPT#
STRENGTH_BASED_FEEDBACK = (
'''
    Based on the full conversation so far, provide feedback about the user:
    Identify the user's strengths presented in the interview such as their positive skills, traits and/or experiences.
    Consider how well these strengths match to their degree and discipline, and the job and job description.
    Map those strengths to relevant similar career paths to the interview job.
    Suggest improvements, preparation steps and interview strategies aligning to those career paths.
    Frame this advice positively around what the interviewee already does well.

    List two possible small improvements the interviewee could consider for future interviews.
'''
)

#---------------------#

#DECLARATIONS#

if 'is_started' not in st.session_state:
    st.session_state['is_started'] = False
if 'cb_mode' not in st.session_state:
    st.session_state.cb_mode = ''
if 'questions_type' not in st.session_state:
    st.session_state.questions_type = ''
if 'company' not in st.session_state:
    st.session_state.company = ''
if 'job_title' not in st.session_state:
    st.session_state.job_title = ''
if 'prompt' not in st.session_state:
    st.session_state.prompt = ''
if 'resume' not in st.session_state:
    st.session_state.resume = ''
if 'job_descri' not in st.session_state:
    st.session_state.job_descri = ''
if 'silence_time' not in st.session_state:
    st.session_state['silence_time'] = '1500'
if 'max_speech_time' not in st.session_state:
    st.session_state['max_speech_time'] = '30'
if 'degree' not in st.session_state:
    st.session_state.degree = ''
if 'discipline' not in st.session_state:
    st.session_state.discipline = ''
if 'year' not in st.session_state:
    st.session_state.year = None
if 'name' not in st.session_state:
    st.session_state.name = ''
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

#---------------------#

#STATE CHANGE VARIABLES

if st.session_state.cb_mode == 'Teaching':
    introduction_prompt = TEACH_INTRO
elif st.session_state.cb_mode == 'Practice':
    introduction_prompt = PRAC_INTRO
elif st.session_state.cb_mode == 'Realistic':
    introduction_prompt = REAL_INTRO

interviewee_details = (
'''
    The interviewee {} is a {} year student studying majoring in {} for a {} degree.
    \nThe interviewee's resume details are:
    \n{}
'''
).format(
    st.session_state.name,
    st.session_state.year,
    st.session_state.discipline,
    st.session_state.degree,
    st.session_state.resume
)

interviewer_details = (
'''
    Your are an interviewer for {} company and you are interviewing for the 
     the {} job postion.
    \n The following is the job description:
    \n {}
'''
).format(
    st.session_state.company,
    st.session_state.job_title,
    st.session_state.job_descri
)

questions1 = "Go through the following questions in order:\n" + OPENING_QUESTIONS
questions2 = COMPANY_QUESTIONS + FINAL_QUESTION
questions_set = ''
if st.session_state.questions_type == 'Technical':
    questions1 += RESUME_QUESTIONS
    questions_set = questions1 + TECHNICAL_QUESTIONS + questions2
elif st.session_state.questions_type == 'Behavioural':
    questions1 += RESUME_QUESTIONS
    questions_set = questions1 + BEHAVIOUR_BASED_STAR_SCORING + BEHAVIOURAL_QUESTIONS + questions2
elif st.session_state.questions_type == 'Both':
    questions_set = questions1 + BEHAVIOUR_BASED_STAR_SCORING + BEHAVIOURAL_QUESTIONS + TECHNICAL_QUESTIONS + questions2

interview_prompts = INTERVIEWER_ROLE + PROMPTS_STRUCTURE + interviewee_details + interviewer_details + questions_set
personality = ''
if st.session_state.cb_mode == 'Teaching':
    personality = TEACHER_ROLE
elif st.session_state.cb_mode == 'Practice':
    personality = PRACTICE_MODE + interview_prompts
elif st.session_state.cb_mode == 'Realistic':
    personality = REALISTIC_MODE + interview_prompts

#---------------------#

#CONSTANTS#

CHUNK_SIZE = 1024
RATE = 24000
REENGAGE_DELAY_MS = 300
#REENGAGE_DELAY_MS = 3000
FORMAT = pyaudio.paInt16

#---------------------#

#LOGGING#

logging.basicConfig(filename="realtime-participants.log",
                    format='%(asctime)s [%(levelname)s] - %(message)s',
                    filemode='a')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG) #dev diagnosis - detailed
#logger.setLevel(logging.INFO) #check - expected working behaviour

##OUTPUT to terminal
#logging.basicConfig(level=logging.INFO,
#                    format='%(asctime)s [%(levelname)s] %(message)s')

#---------------------#

#SETUPS#

#Load environment variables - API key
load_dotenv()

#WebBroswer - Flask setup - bi-directional comm.s
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

#---------------------#

#VARIABLES#

start_time = 0.0
stop_time = 0.0

#---------------------#

#FUNCTIONS#

def time_lap(record_state, fn_phrase):
    global start_time
    global stop_time

    if record_state == "start":
        start_time = time.time()
    elif record_state == "stop":
        stop_time = time.time()
        elapsed_time = stop_time - start_time
        print(f'{elapsed_time:.4f} seconds taken to {fn_phrase}.')
    else:
        logging.info("Incorrect state input for time lap function.")

#---------------------#

#CLASSES#

class Socket:
    def __init__(self, api_key, ws_url):
        self.api_key = api_key
        self.ws_url = ws_url
        self.ws = None
        self.on_msg = None
        self._stop_event = threading.Event()
        self.lock = threading.Lock()

    def connect(self):
        self.ws = create_connection(
            self.ws_url,
            header=[
                f"Authorization: Bearer {self.api_key}",
                "OpenAI-Beta: realtime=v1"
            ]
        )
        logging.info("Connected to OpenAI's WebSocket.")
        threading.Thread(target=self._receive_loop,
                         daemon=True,
                         name="ReceiveLoopThread").start()

    def _receive_loop(self):
        while not self._stop_event.is_set():
            try:
                raw = self.ws.recv()
                if raw and self.on_msg:
                    received = json.loads(raw)
                    #print("EVENT RECEIVED: ", received)
                    self.on_msg(received)
            except WebSocketConnectionClosedException:
                logging.error("WebSocket closed.")
                break
            except Exception as e:
                logging.error(f"Recv error: {e}")
        logging.info("Receiver stopped.")

    def send(self, obj):
        if not self.ws:
            logging.error("Cannot send - WebSocket not connected.")
            return
        try:
            payload = json.dumps(obj)
        except Exception as enc_err:
            logging.error(f"Failed to encode JSON: {enc_err}.")
            return
        
        try:
            with self.lock:
                self.ws.send(payload)
        except Exception as send_err:
            logging.error(f"Send error: {send_err}.")

    def close(self):
        self._stop_event.set()

        if hasattr(self, "receiver_thread"):
            self.receiver_thread.join(timeout=2)

        try:
            if self.ws:
                self.ws.send_close()
                self.ws.close()
        except Exception as e:
            logging.debug(f"Ignoring close error: {e}.")

        logging.info("WebSocket connection closed.")


class AudioIO:
    def __init__(self):
        self.audio_buffer = bytearray()
        self.mic_queue = queue.Queue()
        self.mic_active = False
        self.mic_on_at = 0
        self._stop_event = threading.Event()
        self.p = pyaudio.PyAudio()

    def _mic_cb(self, in_data, frame_count, time_info, status):
        now = time.time()
        if now > self.mic_on_at:
            if not self.mic_active:
                logging.info("Mic ON")
                self.mic_active = True
            self.mic_queue.put(in_data)
        else:
            if self.mic_active:
                logging.info("Mic OFF")
                self.mic_active = False
        return (None, pyaudio.paContinue)

    def _spk_cb(self, in_data, frame_count, time_info, status):
        needed = frame_count * 2
        if len(self.audio_buffer) >= needed:
            chunk = self.audio_buffer[:needed]
            self.audio_buffer = self.audio_buffer[needed:]
            self.mic_on_at = time.time() + REENGAGE_DELAY_MS / 1000
        else:
            chunk = self.audio_buffer + b"\x00" * (needed - len(self.audio_buffer))
            self.audio_buffer.clear()
        return (bytes(chunk), pyaudio.paContinue)

    def start(self):
        def make_stream(is_input, callback):
            return self.p.open(
                format=FORMAT,
                channels=1,
                rate=RATE,
                input=is_input,
                output=not is_input,
                frames_per_buffer=CHUNK_SIZE,
                stream_callback=callback
            )
        self.in_stream = make_stream(is_input=True, callback=self._mic_cb)
        self.out_stream = make_stream(is_input=False, callback=self._spk_cb)
        self.in_stream.start_stream()
        self.out_stream.start_stream()

    def stop(self):
        self._stop_event.set()
        if hasattr(self, "in_stream") and self.in_stream.is_active():
            try:
                self.in_stream.stop_stream()
            except Exception as e:
                logging.warning(f"Failed to stop input stream: {e}.")
            try:
                self.in_stream.close()
            except Exception as e:
                logging.warning(f"Failed to close input stream: {e}.")
        
        if hasattr(self, "out_stream") and self.out_stream.is_active():
            try:
                self.out_stream.stop_stream()
            except Exception as e:
                logging.warning(f"Failed to stop output stream: {e}.")
            try:
                self.out_stream.close()
            except Exception as e:
                logging.warning(f"Failed to close output stream: {e}.")

        if hasattr(self, "p"):
            try:
                self.p.terminate()
            except Exception as e:
                logging.warning(f"Failed to terminate PyAudio: {e}.")

        logging.info("AudioIO stopped successfully.")

    def send_mic(self, sock):
        while not self._stop_event.is_set():
            try:
                data = self.mic_queue.get(timeout=3)
#                data = self.mic_queue.get(timeout=0.5)
            except queue.Empty:
                logging.info("Mic Queue is empty.")
                continue
            except AttributeError as e:
                logging.error(f"Attribute error: {e}.")
            enc = base64.b64encode(data).decode()
            msg = {
                "type": "input_audio_buffer.append",
                "audio": enc
            }
            #enc = AUDIO of user
            try:
                sock.send(msg)
            except Exception as e:
                logging.warning(f"Failed to send mic data: {e}.")

    def push_back(self, audio_bytes):
        if not audio_bytes:
            return

        if not hasattr(self, "_buffer_lock"):
            self._buffer_lock = threading.Lock()
        
        with self._buffer_lock:
            self.audio_buffer.extend(audio_bytes)

        logging.debug(f"Pushed {len(audio_bytes)} bytes to audio buffer, new length: {len(self.audio_buffer)}.")

class Realtime:
    def __init__(self, key, url, max_speech_t, silence_t, cb_mode, msg_type):
        self.sock = Socket(key, url)
        self.audio = AudioIO()
        self.max_speech_time = max_speech_t
        self.silence_time = silence_t
        self.cb_mode = cb_mode
        self.msg_type = msg_type

        self.running = True
        self.speech_start = None
        self.prev_active = False
        self.sent_update = False

        self.interviewer_started = False    
        self.assistant_queue = queue.Queue()
        self.user_queue = queue.Queue()

    def start(self):
        if getattr(self, "_started", False):
            logging.info("RealtimeClient.start() called but already started.")
            return
        self._started = True
        self.sock.on_msg = self.on_msg
        self.sock.connect()
        self.audio.start()

        threading.Thread(target=self.audio.send_mic,
                         args=(self.sock,),
                         daemon=True,
                         name="RealtimeSendMicThread").start()

        threading.Thread(target=self._watch_silence,
                         daemon=True,
                         name="RealtimeWatchSilenceThread").start()

        logging.info("Realtime chatbot has fully started.")
        print("Realtime Chatbot has started.")

    def _watch_silence(self):
        while self.running:
            active = self.audio.mic_active

            if active and not self.prev_active:
                self.speech_start = time.time()

            if active and self.speech_start and (time.time() - self.speech_start) >= (self.max_speech_time + 0.1):
                logging.info(" Max speech duration reached - committing audio input.")
                self.sock.send({"type": "input_audio_buffer.commit"})
                self.speech_start = None

            if self.prev_active and not active:
                logging.info("Silence - committing audio input.")
                self.sock.send({"type": "input_audio_buffer.commit"})
                self.speech_start = None

            self.prev_active = active
            time.sleep(0.05)

    def on_msg(self, msg):
        typ = msg.get("type")
        #if typ == "response.audio_transcript.done" or typ == "response.audio_transcript.delta":
        #    print(msg)
        logging.info(f"Event: {typ}")

        def handle_session_created():
            #DOES SEND ON START
            if self.sent_update:
                return
            self.sent_update = True
            self.sock.send({
                "type": "session.update",
                "session": {
                    "voice": "alloy",
                    "instructions": personality,
                    "modalities": ["audio", "text"],
                    "input_audio_transcription": {
                        "model": "gpt-4o-mini-transcribe"
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": self.silence_time
                    }
                }
            })
            #turn_detection - allows User longer pauses between sentences before response

            #Voice Options
            #https://platform.openai.com/docs/guides/realtime-conversations#voice-options
            #https://www.openai.fm/

            #INTRODUCTION IS BEFORE & SEPARATE TO PERSONALITY (ChatGPT does not yet know its personality: role, details)
            if not self.interviewer_started:
                time.sleep(1)
                self.sock.send({
                        "type": "response.create",
                        "response": {
                            "modalities": ["audio", "text"],
                            "instructions": introduction_prompt
                        }
                    })
                logging.info("Prompted to speak first.")
                self.interviewer_started = True

        def handle_session_updated():
            logging.info("Session was updated.")

        def handle_audio_detected():
            logging.info("Speech detected.")

        def handle_audio_stopped():
            logging.info("Detected that speech stopped.")
            time_lap("start", "")

        def handle_input_committed():
            logging.info("Audio committed. Awaiting response...")
            self.sock.send({
                "type": "response.create",
                "response": {"modalities": ["audio", "text"]}
            })

        def handle_response_created():
            logging.info("Response created.")
            time_lap("stop", "create a response")

        def handle_audio_delta():
            data = base64.b64decode(msg["delta"])
            self.audio.push_back(data)

        def handle_audio_done():
            logging.info("Clearing audio buffer.")
            self.sock.send({"type": "input_audio_buffer.clear"})
        
        def handle_output_text_delta():
            ()  #Cleaner logging

        def handle_output_text_done():
            transcript = msg.get("transcript", "")
            if transcript:
                self.assistant_queue.put(transcript)
                #print("\n transcript \n", transcript)

        def handle_input_transcript_delta():
            ()  #Cleaner logging

        def handle_input_transcript_done():
            transcribed = msg.get("transcript", "")
            if transcribed:
               self.user_queue.put(transcribed) 
                #print(transcribed)
        
        def handle_audio_buffer_cleared():
            logging.info("Cleared audio buffer.")

        def handle_cic():
            ()  #Cleaner logging
        def handle_rlu():
            ()  #Cleaner logging
        def handle_rcpa():
            ()  #Cleaner logging
        def handle_rcpd():
            ()  #Cleaner logging 
        def handle_rd():
            ()  #Cleaner logging
        def handle_roia():
            ()  #Cleaner logging
        def handle_roid():
            ()  #Cleaner logging

        def handle_error():
            if('conversation_already_has_active_response' in str(msg.get('error'))):
                logging.info("Error - Chatbot is busy responding. Request after chatbot stops speaking.") 
#                Server error: {'type': 'invalid_request_error', 'code': 'conversation_already_has_active_response', 'message': 'Conversation already has an active response in progress: resp_DYatnCOvRSRbq2pRv2hDZ. Wait until the response is finished before creating a new one.', 'param': None, 'event_id': None}          
                    # Flagging does not handle keeping it to one response
            elif('input_audio_buffer_commit_empty' in str(msg.get('error'))):
                logging.info("Error - Committing audio too quickly, will retry now.")
#               Server error: {'type': 'invalid_request_error', 'code': 'input_audio_buffer_commit_empty', 'message': 'Error committing input audio buffer: buffer too small. Expected at least 100ms of audio, but buffer only has 0.00ms of audio.', 'param': None, 'event_id': None}
                    # Cannot find where the timing is an issue
            else:
                logging.error(f"Server error: {msg.get('error')}")

        handlers = {
            "session.created": handle_session_created,
            "session.updated": handle_session_updated,
            "input_audio_buffer.speech_started": handle_audio_detected,
            "input_audio_buffer.speech_stopped": handle_audio_stopped,
            "input_audio_buffer.committed": handle_input_committed,
            "response.created": handle_response_created,
            "response.audio.delta": handle_audio_delta,
            "response.audio.done": handle_audio_done,
            "response.audio_transcript.delta": handle_output_text_delta,
            "response.audio_transcript.done": handle_output_text_done,
            "conversation.item.input_audio_transcription.delta": handle_input_transcript_delta,
            "conversation.item.input_audio_transcription.completed": handle_input_transcript_done,
            "input_audio_buffer.cleared": handle_audio_buffer_cleared,

            "conversation.item.created": handle_cic,
            "rate_limits.updated": handle_rlu,
            "response.content_part.added": handle_rcpa,
            "response.content_part.done": handle_rcpd, 
            "response.done": handle_rd,
            "response.output_item.added": handle_roia,
            "response.output_item.done": handle_roid,
            "error": handle_error
        }

        handler = handlers.get(typ)
        if handler:
            handler()
        else:
            logging.debug(f"No handler for message type: {typ}.")

    def stop(self):
        self.running = False
        self.audio.stop()
        self.sock.close()
        logging.info("Chatbot is successfully closed.")
        print("Realtime Chatbot has stopped.")

#    def generate_feedback(self):
#        logging.info("Generating feedback...")
#        print("Generating interview feedback...")
#        self.sock.send({
#            "type": "conversation.item.create",
#            "item": {
#                "type": "message",
#                "role": "system",
#                "content": [
#                    {
#                        "type": "input_text",
#                        "text": (
#                            STRENGTH_BASED_FEEDBACK
#                        )
#                    }
#                ]
#            }
#        })

        self.sock.send({
            "type": "response.create",
            "response": {
                "modalities": ["audio", "text"]
            }
        })


#---------------------#

#MAIN FUNCTIONS#

stop_wb_event = threading.Event()

def start_browser():
    while not stop_wb_event.is_set():
        socketio.run(app, host="0.0.0.0", port=5000, log_output=False)

def stop_browser():
    stop_wb_event.set()

def main():
    wb_thread = threading.Thread(target=start_browser,
                    daemon=True,
                    name="WebBrowserThread")
    wb_thread.start()
    logging.info("Web browser thread created.")
    
    key = os.getenv("OPENAI_API_KEY", "[API KEY NEEDED]")
    #Differences in response handling
    #ROBUST
    #url = "wss://api.openai.com/v1/realtime?model=gpt-realtime"
    # EXPERIMENTAL
    url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview"

    max_speech_t = st.session_state.get('max_speech_time')
    silence_t = st.session_state.get('silence_time')
    cb_mode = str(st.session_state.get("cb_mode"))
    msg_type = st.session_state.get('msg_type')
    
    rt = Realtime(key, url, max_speech_t, silence_t, cb_mode, msg_type)
    st.session_state.rt = rt
    #start_time = time.time()
    time_lap("start", "")
    rt.start()
    time_lap("stop", "start Realtime program")
    logging.info("Chatbot is started.")
    #end_time = time.time()

def started():
    st.session_state['is_started'] = True
def stopped():
    st.session_state['is_started'] = False

def stop_cb():
    try:
        st.info('Stopping chatbot...')
        rt = st.session_state.get("rt")
        stopped()
        time.sleep(1)
        if rt:
            rt.stop()
            st.session_state.rt = None
        logging.info("Chatbot is stopped.")
        st.info('Chatbot stopped.')
        time.sleep(1)
    except:
        st.error('Error occurred stopping chatbot.')


uploaded_pdf = None
uploaded_txt = None

def pdf_to_string(pdf_file):
    text = ""
    with fitz.open(pdf_file) as doc:
        for page in doc:
            text += page.get_text()
    return text

if __name__ == "__main__":
    st.set_page_config(layout="wide")
    st.markdown("""
    <style>
    .big-font {
        font-size:18px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    main_col1, main_col2 = st.columns([2,3], width="stretch")
    with main_col1:
        st.title('Real-Time Job Interview Simulator')
        st.markdown('<p class="big-font">Practise for internship internviews in real-time with an AI chatbot that can '
        'provide tailored feedback.</p>', unsafe_allow_html=True)
        
        st.markdown("""
        <style>
        div.stButton > button:first-child {
            background-color: #616161;
            color: white;
        }
        div.stButton > button:hover {
            background-color: #B71C1C;
            color: white;
        }
        </style>
        """, unsafe_allow_html=True)

        col1, col2, col3, col4, col5 = st.columns(5)
        start_b = col1.button('Start chatbot', type="secondary")
        stop_b = col2.button('Stop chatbot')
        exit_b = col5.button('Exit program', type="secondary")

        st_autorefresh(interval=7000, key="realtime_refresh")        
#        st_autorefresh(interval=6000, key="realtime_refresh")        
#        st_autorefresh(interval=5000, key="realtime_refresh")   #Appropriate time for st.info messages
        if start_b:
            if not st.session_state['is_started']:
                if st.session_state.cb_mode in ['Teaching']:
                    started()
                    st.info("Starting chatbot...")
                    time.sleep(1)
                    main()
                    st.info('Chatbot started.')
                    time.sleep(1)
#                    time.sleep(2)
                elif (st.session_state.cb_mode in ['Practice','Realistic']):
                    if not (st.session_state.questions_type and st.session_state.name and st.session_state.degree and
                        st.session_state.discipline and st.session_state.year and
                        st.session_state.resume and st.session_state.company and
                        st.session_state.job_title and st.session_state.job_descri
                    ):
                        st.warning('Please fill in all the details required.')            
                    else:
                        started()
                        st.info("Starting chatbot...")
                        time.sleep(1)
                        main()
                        st.info('Chatbot started.')
                        time.sleep(1)
                else:
                    st.warning("Please select a chatbot mode.")
                    time.sleep(1)
            else:
                st.info("Chatbot already started.")
                time.sleep(1)

        if stop_b:
            if st.session_state['is_started']:
                stop_cb()
                time.sleep(0.5)
                threading.Event.set()
            elif not st.session_state['is_started']:
                st.warning('Please start the chatbot first.')
                time.sleep(1)

        if exit_b:
            if st.session_state['is_started']:
                stop_cb()
            else:
                ()
            try:
                st.info("Exiting program...")
                time.sleep(1)
                logging.info("Realtime program is closed.")
                keyboard.press_and_release('ctrl+w')
                logging.info("Realtime program is closed.")
                psutil.Process(os.getpid()).terminate()
            except:
                print("Error occurred with exiting.")
                st.error("Error occurred exiting.")
                time.sleep(1)

        if not st.session_state['is_started']:
            st.session_state.chat_history = [] #Clears
            st.divider()
            st.subheader('Configuration Options')
            st.write('')
            st.session_state.cb_mode = st.segmented_control('Select interview mode:', ['Teaching', 'Practice', 'Realistic'])
            est_time = ''
            mode_descri = ''
            if st.session_state.cb_mode == 'Teaching':
                mode_descri = "The chatbot teaches interview conventions, interview expectations and types of interview questions."
                est_time = '20-30 mins'
            elif st.session_state.cb_mode == 'Practice':
                mode_descri = "The chatbot practices answering questions with you while giving guidance on your answers " \
                "and it provides tailored feedback at the end."
                est_time = '20-25 mins'
            elif st.session_state.cb_mode == 'Realistic':
                mode_descri = "The chatbot simulates a realistic interview and provides tailored feedback at the end."
                est_time = '15-20 mins'
            st.write('')
            st.markdown('<p class="big-font">Description:</p>', unsafe_allow_html=True)
            st.markdown('<p class="big-font">{}</p>'.format(mode_descri), unsafe_allow_html=True)
            st.write('')
            st.markdown('<p class="big-font">Estimated time: {}</p>'.format(est_time), unsafe_allow_html=True)
            st.write('')
            st.session_state['max_speech_time'] = st.slider('Maximum duration ' \
            'the interviewee requires for each response (seconds)', 20, 60, 30, 5)
            st.session_state['silence_time'] = st.slider('Maximum duration of a pause ' \
            'before the chatbot will respond (milliseconds)', 1000, 3000, 1500, 250)
            if st.session_state.cb_mode in ['Practice','Realistic']:
                st.divider()
                st.subheader('Question Options')
                st.session_state.questions_type = st.segmented_control('Select questions type:', ['Technical', 'Behavioural', 'Both'])
                st.write('')
                st.write('')
                st.subheader('Your Details - Interviewee')
                st.session_state.name = st.text_input('Enter your full name:')
                st.session_state.degree = st.text_input('Enter the degree you are ' \
                'studying (e.g. Bachelor of Engineering):')
                st.session_state.discipline = st.text_input('Enter your displine ' \
                '(e.g. Mechatronic engineering):')
                st.session_state.year = st.selectbox("What year of your study are " \
                "you in:", ["First", "Second", "Third", "Fourth", "Fifth", "Graduate"], None)
                uploaded_pdf = st.file_uploader('Upload a .pdf file of your resume.', type="pdf")

                if uploaded_pdf is not None:
                    try:
                        st.session_state.resume = pdf_to_string(uploaded_pdf)
#                        if st.session_state.resume:
#                            print(st.session_state.resume)
                        #st.write(interviewee_details)
                    except:
                        st.warning('Failed to upload pdf file.')
                        time.sleep(1)
                st.write('')
                st.write('')
                st.write('')
                st.subheader('Company Details - Interviewer')
                st.session_state.company = st.text_input('Enter the name of the company ' \
                'you are interviewing for:')
                st.session_state.job_title = st.text_input('Enter the job title:')
                uploaded_txt = st.file_uploader('Upload a .txt file of the job description.', type="txt")
                if uploaded_txt is not None:
                    try:
                        st.session_state.job_descri = uploaded_txt.read().decode("utf-8")
                    except:
                        st.warning('Failed to upload txt file.')
                        time.sleep(1)

    with main_col2:
        if st.session_state.get("is_started"):
            st_autorefresh(interval=200, key="chat_refresh")
            #st_autorefresh(interval=500, key="chat_refresh")
#            st_autorefresh(interval=1000, key="chat_refresh")
            st.session_state.questions_type = ''

            st.subheader(st.session_state.cb_mode + ' Interview Mode')
            if st.session_state.cb_mode in 'Teaching':
                st.write("ChatGPT is playing the role of a professional trainer "
                "for job interviews.")
            else:
                st.write("ChatGPT is playing the role of a professional interviewer.")
                st.markdown(st.session_state.company + ' Company' )
                st.markdown(st.session_state.job_title + ' Job Position')

            rt = st.session_state.get("rt")
            if rt:
                chat_queues = [
                    (rt.assistant_queue, "assistant"),
                    (rt.user_queue, "user")
                ]

                for queue_msgs, role in chat_queues:
                    while not queue_msgs.empty():
                        st.session_state.chat_history.append((role, queue_msgs.get()))

            chat_window = st.container(border=True, height=700)
            with chat_window:
                for role, messsage in st.session_state.chat_history:
                    st.chat_message(role).write(messsage)
#            if st.session_state.cb_mode in ['Practice','Realistic']:
#                st.write("Press at the end of interview.")
#                feedback_b = st.button('Generate Feedback')
#                if feedback_b == True:
#                    ()
#                    rt = st.session_state.get("rt")
#                    if rt:
#                        rt.generate_feedback()
