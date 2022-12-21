import redis
import sys
import signal
import threading
import logging.handlers
import queue
import time
import multiprocessing
import uuid
import requests
import json
from time import sleep
from signal import SIGINT, SIGTERM, SIGQUIT
from functools import wraps
from dynaconf import settings
from exceptions import GenericExitOnSignal
from message_models import SystemEpochStatusReport
from redis_keys import epoch_detector_last_processed_epoch
from setproctitle import setproctitle
from rabbitmq_helpers import RabbitmqThreadedSelectLoopInteractor
from redis_conn import create_redis_conn, REDIS_CONN_CONF
from data_models import EpochInfo

def chunks(start_idx, stop_idx, n):
    """
    Yield tuples of indices representing chunks of a range.

    Arguments:
    start_idx -- the start index of the range
    stop_idx -- the stop index of the range
    chunk_size -- the size of each chunk
    """
    run_idx = 0
    for i in range(start_idx, stop_idx + 1, n):
        # Create an index range for l of n items:
        begin_idx = i  # if run_idx == 0 else i+1
        if begin_idx == stop_idx + 1:
            return
        end_idx = i + n - 1 if i + n - 1 <= stop_idx else stop_idx
        run_idx += 1
        yield begin_idx, end_idx, run_idx

def rabbitmq_and_redis_cleanup(fn):
    """
    A decorator that wraps the provided function and handles cleaning up RabbitMQ and Redis resources before exiting.
    """
    @wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            fn(self, *args, **kwargs)
        except (GenericExitOnSignal, KeyboardInterrupt):
            try:
                self._logger.debug('Waiting for RabbitMQ interactor thread to join...')
                self._rabbitmq_thread.join()
                self._logger.debug('RabbitMQ interactor thread joined.')
                if self._last_processed_epoch:
                    self._logger.debug('Saving last processed epoch to redis...')
                    with create_redis_conn(self._connection_pool) as r:
                        r.set(epoch_detector_last_processed_epoch, json.dumps(self._last_processed_epoch))
            except Exception as E:
                self._logger.error('Error while saving progress: %s', E)
        except Exception as E:
            self._logger.error('Error while running: %s', E)
        finally:
            self._logger.debug('Shutting down!')
            sys.exit(0)
    return wrapper


class EpochDetectorProcess(multiprocessing.Process):
    def __init__(self, name, **kwargs):
        """
        Initializes a new instance of the `EpochDetectorProcess` class.
        
        Arguments:
        name -- the name of the process
        """
        multiprocessing.Process.__init__(self, name=name, **kwargs)
        self._rabbitmq_thread: threading.Thread
        self._rabbitmq_queue = queue.Queue()
        self._shutdown_initiated = False
        self._connection_pool = redis.BlockingConnectionPool(**REDIS_CONN_CONF)

        self._logger = logging.getLogger(f'{name}|{settings.NAMESPACE}-{settings.INSTANCE_ID[:5]}')
        self._logger.setLevel(logging.DEBUG)
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.DEBUG)
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.ERROR)
        
        self._logger.handlers = [
            logging.handlers.SocketHandler(host=settings.get('LOGGING_SERVER.HOST','localhost'),
            port=settings.get('LOGGING_SERVER.PORT',logging.handlers.DEFAULT_TCP_LOGGING_PORT)),
            stdout_handler, 
            stderr_handler
        ]
        self._exchange = f'{settings.RABBITMQ.SETUP.CORE.EXCHANGE}:{settings.NAMESPACE}'
        self._routing_key = f'epoch-broadcast:{settings.NAMESPACE}:{settings.INSTANCE_ID}'


        self._last_processed_epoch = None
        setproctitle(name)


    def _interactor_wrapper(self, q: queue.Queue):  # run in a separate thread
        self._rabbitmq_interactor = RabbitmqThreadedSelectLoopInteractor(
            publish_queue=q, consumer_worker_name=self.name
        )
        self._rabbitmq_interactor.run()  # blocking

    def _generic_exit_handler(self, signum, sigframe):
        if signum in [SIGINT, SIGTERM, SIGQUIT] and not self._shutdown_initiated:
            self._shutdown_initiated = True
            self._rabbitmq_interactor.stop()
            raise GenericExitOnSignal

    def _broadcast_epoch(self, epoch:dict):
        """Broadcast epoch to the RabbitMQ queue and save update in redis."""
        report_obj = SystemEpochStatusReport(**epoch)
        self._logger.info('Broadcasting  epoch for callbacks: %s', report_obj)
        brodcast_msg = (report_obj.json().encode('utf-8'), self._exchange, self._routing_key)
        self._rabbitmq_queue.put(brodcast_msg)
        self._last_processed_epoch = epoch
        with create_redis_conn(self._connection_pool) as r:
            try:
                r.set(epoch_detector_last_processed_epoch, json.dumps(epoch))
                self._logger.info('DONE: Broadcasting finalized epoch for callbacks: %s',
                                report_obj)
            except:
                self._logger.error("Unable to save state in redis. Will try again on next epoch.")

    @rabbitmq_and_redis_cleanup
    def run(self):
        """
        The entry point for the process.
        """
        consensus_epoch_tracker_url = f'{settings.CONSENSUS.URL}{settings.CONSENSUS.EPOCH_TRACKER_PATH}'
        for signame in [signal.SIGINT, signal.SIGTERM, signal.SIGQUIT]:
            signal.signal(signame, self._generic_exit_handler)
        self._rabbitmq_thread = threading.Thread(target=self._interactor_wrapper, kwargs={'q': self._rabbitmq_queue})
        self._rabbitmq_thread.start()
        
        while True:
            try:
                response = requests.get(consensus_epoch_tracker_url)
                if response.status_code != 200:
                    self._logger.error('Error while fetching current epoch data: %s', response.status_code)
                    sleep(settings.CONSENSUS.POLLING_INTERVAL)
                    continue
            except:
                self._logger.error(f"Unable to fetch current epoch, sleeping for {settings.CONSENSUS.POLLING_INTERVAL} seconds.")
                sleep(settings.CONSENSUS.POLLING_INTERVAL)
                continue
            epoch_info = EpochInfo(**response.json())
            current_epoch = {"begin":epoch_info.epochStartBlockHeight, "end": epoch_info.epochEndBlockHeight, "broadcast_id": str(uuid.uuid4())}
            self._logger.info('Current epoch: %s', current_epoch)
            
            # Only use redis is state is not locally present
            if not self._last_processed_epoch:
                with create_redis_conn(self._connection_pool) as r:
                    last_processed_epoch_data = r.get(epoch_detector_last_processed_epoch)
                if last_processed_epoch_data:
                    self._last_processed_epoch = json.loads(last_processed_epoch_data)             

            if self._last_processed_epoch:
                if self._last_processed_epoch['end'] == current_epoch['end']:
                    self._logger.debug('Last processed epoch is same as current epoch, Sleeping for %d seconds...', settings.CONSENSUS.POLLING_INTERVAL)
                    sleep(settings.CONSENSUS.POLLING_INTERVAL)
                    continue

                else:
                    fall_behind_reset_threshold = settings.CONSENSUS.FALL_BEHIND_RESET_NUM_BLOCKS
                    if current_epoch['end'] - self._last_processed_epoch['end'] > fall_behind_reset_threshold:
                        # TODO: build automatic clean slate procedure, for now just issuing warning on every new epoch fetch
                        self._logger.error('Epochs are falling behind by more than %d blocks, consider reset state to continue.', fall_behind_reset_threshold)
                        raise GenericExitOnSignal
                    epoch_height = current_epoch['end']-current_epoch['begin']+1
                    
                    if self._last_processed_epoch['end']> current_epoch['end']:
                        self._logger.warning('Last processed epoch end is greater than current epoch end, something is wrong. Please consider resetting the state.')
                        raise GenericExitOnSignal

                    for epoch in chunks(self._last_processed_epoch['end'], current_epoch['end'], epoch_height):
                        epoch_from_chunk = {'begin': epoch[0], 'end': epoch[1], 'broadcast_id': str(uuid.uuid4())}
                        
                        self._broadcast_epoch(epoch_from_chunk)
                        self._logger.info('Sleeping for %d seconds...', settings.CONSENSUS.SLEEP_SECS_BETWEEN_CHUNKS)
                        sleep(settings.CONSENSUS.SLEEP_SECS_BETWEEN_CHUNKS)
            else:
                self._logger.debug('No last processed epoch found, processing current epoch')
                self._broadcast_epoch(current_epoch)
                
                self._logger.info('Sleeping for %d seconds...', settings.CONSENSUS.POLLING_INTERVAL)
                sleep(settings.CONSENSUS.POLLING_INTERVAL)