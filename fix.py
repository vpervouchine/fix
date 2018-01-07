
from enum import Enum
from collections import namedtuple


class FixSessionBase(object):

    Start       = namedtuple('Start',       [])
    Stop        = namedtuple('Stop',        [])
    Message     = namedtuple('Message',     ['msg_type', 'msg_seq_num', 'msg'])
    Connect     = namedtuple('Connect',     ['is_connected'])
    Login       = namedtuple('Login',       ['is_logged_in'])

    class State(object):
        def __init__(self, previous_state):
            if previous_state:
                self.__fix_session__ = previous_state.__fix_session__
            self.__previous_state_type__ = type(previous_state)
            self.__name__ = '%s' % type(self)

        def __str__(self):
            return self.__name__

        def on_event(self, event):
            raise RuntimeError('Unexpected event {event} at state {name}'.format(event=event, name=self.name))

        def on_enter(self):
            pass

        def on_exit(self):
            pass


    class InitialState(FixSession.State):
        def __init__(self, fix_session):
            super().__init__(None)
            self.__fix_session__ = fix_session

        def on_event(self, event):
            if type(event) == Start:
                return DisconnectedState(self, connect=True)

            else:
                return super().on_event(event)


    class FinalState(FixSession.State):
        def __init__(self, previous_state, reason):
            super().__init__(previous_state)
            print('Stopping: {reason}'.format(**locals()))


    class DisconnectedState(FixSession.State):
        def __init__(self, previous_state, connect):
            super().__init__(previous_state)
            self.__connect__ = connect

        def on_enter(self):
            if self.__connect__:
                self.__fix_session__.connect()
            else:
                self.__fix_session__.stop()

        def on_event(self, event):
            if type(event) == Connect:
                return ConnectedState(self) if event.is_connected else FinalState(self, 'not reconnecting')

            else:
                return super().on_event(event)

    
    class ConnectedState(FixSession.State):
        def on_enter(self):
            self.__fix_session__.send_login()

        def on_event(self, event):
            if type(event) == Message:
                if event.msg_type == MsgType.Logon:
                    if event.msg_seq_num == self.__fix_session__.next_inbound_seq_num():
                        return WorkingState(self)
                    else
                        return RecoveryState(self, event.msg_seq_num)

                elif event.msg_type == MsgType.Logout:
                    return LoggedOutState(self, relogin=False)

            elif type(event) == Connect and not event.is_connected:
                return DisconnectedState(self, reconnect=False)

            elif type(event) == Stop:
                return DisconnectingState(self)
                
            else:
                return super().on_event(event)

    
    class DisconnectingState(FixSession.State):
        def on_enter(self):
            self.__fix_session__.disconnect()

        def on_event(self, event):
            if type(event) == Connect and not event.is_connected:
                return DisconnectedState(self, reconnect=False)

            else:
                return super().on_event(event)

    
    class WorkingState(FixSession.State):
        def __init__(self, previous_state):
            super().__init__(previous_state)

        def on_event(self, event):
            if type(event) == Connect and not event.is_connected:
                return DisconnectedState(self, reconnect=True)

            elif type(event) == Stop:
                return LoggingOutState(self)

            elif type(event) == Message:
                if event.msg_seq_num == self.__fix_session__.next_inbound_seq_num():
                    return RecoveryState(self, event.msg_seq_num)
                else:
                    return self.__process_message__(event)

            else:
                return super().on_event(self)

        def __process_message__(self, event):
            pass # TODO


    class RecoveryState(FixSession.WorkingState):
        def __init__(self, previous_state, msg_seq_num):
            self.__msg_seq_num__ = msg_seq_num

        def on_enter(self):
            self.__fix_session__.send_resend_request(msg_seq_num)

        def on_event(self, event):
            if type(event) == Message:
                pass

            else:
                return super().on_event(event)


    class LoggingOutState(FixSession.WorkingState):
        def on_enter(self):
            self.__fix_session__.send_logout()

        def on_event(self, event):
            if type(event) == Message:
                if event.msg_type == MsgType.Logout:
                    return LoggedOutState(reconnect=False)

            elif type(event) == Connect and not event.is_connected:
                return DisconnectedState(reconnect=False)

            else:
                return super().on_event(event)


    class LoggedOutState(FixSession.State):
        def __init__(self, previous_state, reconnect):
            super().__init__(previous_state)
            self.__reconnect__ = reconnect

        def on_enter(self):
            self.__fix_session__.disconnect()

        def on_event(self):
            if type(event) == Connect and not event.is_connected:
                return DisconnectedState(self, self.__reconnect__)

            else:
                return super().on_event(event)


    def connect(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    def disconnect(self):
        raise NotImplementedError()

    def send_login(self):
        raise NotImplementedError()

    def next_inbound_seq_num(self):
        raise NotImplementedError()

    def send_resend_request(self, received_msg_seq_num):
        raise NotImplementedError()

    def send_logout(self):
        raise NotImplementedError()


