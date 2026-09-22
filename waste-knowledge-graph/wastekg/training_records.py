"""Atomic, run-scoped training progress; metrics remain tied to completed weights."""
from datetime import datetime, timezone
from uuid import uuid4
from .common import read_json, write_json


def save_record(path, value):
    temporary = path.with_name(path.name + '.tmp')
    write_json(temporary, value)
    temporary.replace(path)


def begin_run(directory, epochs, seed):
    previous = directory / 'training_run.json'
    count = read_json(previous).get('run_number', 0) if previous.exists() else 0
    run = {'run_id': uuid4().hex, 'run_number': count + 1,
           'started_at': datetime.now(timezone.utc).isoformat(),
           'status': 'running', 'epochs': epochs, 'completed_epochs': 0, 'seed': seed}
    # Publish the new run before touching old weights or history.
    save_record(previous, run)
    save_record(directory / 'history.json', [])
    return run


def record_epoch(directory, run, history):
    save_record(directory / 'history.json', history)
    run['completed_epochs'] = len(history)
    save_record(directory / 'training_run.json', run)


def finish_run(directory, run, result):
    run.update(status='completed', finished_at=datetime.now(timezone.utc).isoformat(),
               model_signature=result['model_signature'])
    result['training_run'] = dict(run)
    save_record(directory / 'metrics.json', result)
    save_record(directory / 'training_run.json', run)
