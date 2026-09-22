from wastekg.common import model_signature, read_json, write_json
from wastekg.training_records import begin_run, record_epoch, finish_run
from wastekg.server import App


def weights(path, content):
    for name in ('ner.weights.h5', 'relation.weights.h5', 'vocab.json'):
        (path/name).write_bytes(content)


def test_second_run_replaces_history_and_hides_previous_scores(tmp_path):
    app=App(tmp_path)
    weights(tmp_path,b'old')
    first=begin_run(tmp_path,2,42)
    record_epoch(tmp_path,first,[{'epoch':1,'val_ner_f1':.2},{'epoch':2,'val_ner_f1':.4}])
    finish_run(tmp_path,first,{'model_signature':model_signature(tmp_path),'ner':{'f1':.4}})
    write_json(tmp_path/'web_metrics.json',{'model_signature':model_signature(tmp_path),'f1':.3})
    assert app.metrics_snapshot()['available']
    second=begin_run(tmp_path,1,43)
    assert second['run_number']==2 and second['run_id']!=first['run_id']
    snapshot=app.metrics_snapshot()
    assert snapshot['history']==[] and not snapshot['available'] and snapshot['web'] is None
    weights(tmp_path,b'new')
    record_epoch(tmp_path,second,[{'epoch':1,'val_ner_f1':.8}])
    assert app.metrics_snapshot()['history']==[{'epoch':1,'val_ner_f1':.8}]
    finish_run(tmp_path,second,{'model_signature':model_signature(tmp_path),'ner':{'f1':.8}})
    snapshot=app.metrics_snapshot()
    assert snapshot['available'] and snapshot['metrics']['ner']['f1']==.8
    assert len(snapshot['history'])==1 and snapshot['web'] is None
    assert snapshot['training_run']['status']=='completed'
    assert read_json(tmp_path/'metrics.json')['training_run']['run_id']==second['run_id']


def test_incomplete_or_mismatched_run_never_exposes_old_metrics(tmp_path):
    weights(tmp_path,b'old')
    run=begin_run(tmp_path,2,42)
    finish_run(tmp_path,run,{'model_signature':model_signature(tmp_path)})
    run['run_id']='another-run'
    write_json(tmp_path/'training_run.json',run)
    assert not App(tmp_path).metrics_snapshot()['available']
