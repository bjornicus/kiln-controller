import threading,logging,json,time,datetime
from temp import display_profile_data
from mqttout import enabled as mqtt_enabled, MqttOut
log = logging.getLogger(__name__)

class OvenWatcher(threading.Thread):
    def __init__(self,oven):
        self.last_profile = None
        self.started = None
        self.observers = []
        # The status websocket is also the catch-up mechanism for a client
        # which connects after a firing has begun.  Keep one run in the
        # controller, rather than relying on an individual browser's cache.
        self.run_history = []
        self.history_run_id = None
        self.last_run_state = None
        self.history_lock = threading.Lock()
        threading.Thread.__init__(self)
        self.daemon = True
        self.oven = oven
        self.mqtt = MqttOut() if mqtt_enabled() else None
        self.start()

# FIXME - need to save runs of schedules in near-real-time
# FIXME - this will enable re-start in case of power outage
# FIXME - re-start also requires safety start (pausing at the beginning
# until a temp is reached)
# FIXME - re-start requires a time setting in minutes.  if power has been
# out more than N minutes, don't restart
# FIXME - this should not be done in the Watcher, but in the Oven class

    def run(self):
        while True:
            oven_state = self.oven.get_state()

            self.record_state(oven_state)

            if self.mqtt:
                self.mqtt.publish(oven_state)

            self.notify_all(oven_state)
            time.sleep(self.oven.time_step)

    def record(self, profile):
        with self.history_lock:
            self.last_profile = profile
            self.started = datetime.datetime.now()
            # ``record`` is called immediately after every supported start
            # path. Resetting here makes a new firing replace the previous
            # one even before its first control-loop sample is available.
            self.run_history = []
            self.history_run_id = self.oven.get_state().get('run_id')
            self.last_run_state = None

    def record_state(self, state):
        '''Keep the chart fields needed to replay the latest firing.

        Full oven states are comparatively large and contain data that does
        not vary per sample. This compact form retains the profile-time and
        clock-time chart inputs, including PID diagnostics for Details.
        '''
        run_start = state.get('run_start_time')
        if not run_start:
            return
        run_id = state.get('run_id')
        sample = {
            'run_start_time': run_start,
            'initial_runtime': state.get('initial_runtime', 0),
            'run_id': run_id,
            'runtime': state.get('runtime'),
            'temperature': state.get('temperature'),
            'clock_time': state.get('clock_time'),
            'catching_up': state.get('catching_up'),
            'temp_errors': state.get('temp_errors'),
            'pidstats': state.get('pidstats') or {},
        }
        with self.history_lock:
            if self.history_run_id != run_id:
                self.run_history = []
                self.history_run_id = run_id
            self.run_history.append(sample)
            self.last_run_state = sample

    def add_observer(self,observer):
        current = self.oven.get_state()
        with self.history_lock:
            if self.last_profile:
                p = {
                    "name": self.last_profile.name,
                    "data": display_profile_data(self.last_profile.data),
                    "type" : "profile"
                }
            else:
                p = None
            # After completion Oven.reset() clears its timing fields. The
            # retained last sample remains the authoritative chart context.
            context = current if current.get('run_start_time') else self.last_run_state
            context = context or current
            backlog = {
                'type': "backlog",
                'profile': p,
                'run_start_time': context.get('run_start_time'),
                'initial_runtime': context.get('initial_runtime', 0),
                'run_id': context.get('run_id'),
                'runtime': context.get('runtime'),
                'clock_time': context.get('clock_time'),
                'history': list(self.run_history),
            }
        backlog_json = json.dumps(backlog)
        try:
            observer.send(backlog_json)
        except:
            log.error("Could not send backlog to new observer")
        
        self.observers.append(observer)

    def notify_all(self,message):
        message_json = json.dumps(message)
        log.debug("sending to %d clients: %s"%(len(self.observers),message_json))

        # iterate over a copy: removing a dead socket mid-loop would
        # otherwise skip the socket right after it
        for wsock in list(self.observers):
            if wsock:
                try:
                    wsock.send(message_json)
                except:
                    log.error("could not write to socket %s"%wsock)
                    self.observers.remove(wsock)
            else:
                self.observers.remove(wsock)
