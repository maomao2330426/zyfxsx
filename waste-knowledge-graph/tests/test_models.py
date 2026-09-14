import itertools
import numpy as np
import pytest
tf=pytest.importorskip('tensorflow')
from wastekg.models import BiLSTMCRF,BiGRUAttention,encode
from wastekg.common import *
from wastekg.inference import baseline


def test_crf_partition_and_viterbi_against_exhaustive_paths():
    tf.keras.utils.set_random_seed(7)
    model=BiLSTMCRF(12)
    emissions=tf.constant(np.random.default_rng(7).normal(size=(1,3,len(TAGS))),tf.float32)
    model.transitions.assign(np.random.default_rng(8).normal(size=(len(TAGS),len(TAGS))))
    trans=(model.transitions+model.transition_mask).numpy()
    start=(model.start_scores+model.start_mask).numpy();end=model.end_scores.numpy()
    paths=list(itertools.product(range(len(TAGS)),repeat=3))
    scores=np.array([start[p[0]]+end[p[-1]]+sum(emissions.numpy()[0,t,p[t]] for t in range(3))+sum(trans[p[t-1],p[t]] for t in range(1,3)) for p in paths])
    gold=[0,1,2];score=scores[paths.index(tuple(gold))]
    expected=np.log(np.exp(scores-scores.max()).sum())+scores.max()-score
    actual=model.nll(emissions,np.array([gold],np.int32),np.array([3],np.int32))
    assert float(actual)==pytest.approx(float(expected),abs=1e-4)
    assert model.decode(emissions.numpy(),[3])[0]==list(paths[scores.argmax()])


def test_crf_padding_does_not_change_loss():
    model=BiLSTMCRF(12)
    e=tf.constant(np.random.default_rng(1).normal(size=(1,5,len(TAGS))),tf.float32)
    y=np.array([[1,2,0,0,0]],np.int32)
    assert float(model.nll(e,y,[3]))==pytest.approx(float(model.nll(e[:,:3],y[:,:3],[3])),abs=1e-5)


def test_attention_padding_is_zero_and_pair_direction_changes_features():
    m=BiGRUAttention(12)
    x=np.array([[1,2,3,0,0]],np.int32);pos=np.array([[66,66,67,0,0]],np.int32)
    _,a=m((x,pos,pos),return_attention=True)
    assert float(a.numpy()[0,3:].sum())==0.
    assert float(a.numpy().sum())==pytest.approx(1.)
    s={'text':'香蕉皮属于湿垃圾。','entities':[{'start':0,'end':3,'type':'ITEM','text':'香蕉皮'},{'start':5,'end':8,'type':'CATEGORY','text':'湿垃圾'}],'head':0,'tail':1}
    _,_,_,hp,tp=encode([s],{'<PAD>':0,'<UNK>':1})
    assert not np.array_equal(hp,tp)


@pytest.mark.parametrize('text',['香蕉皮不是干垃圾。','香蕉皮是否属于湿垃圾？','假如香蕉皮属于湿垃圾。'])
def test_baseline_does_not_create_positive_fact_from_negation_or_question(text):
    assert baseline(text)['triples']==[]


def test_baseline_positive_and_unknown():
    triples=baseline('香蕉皮属于湿垃圾。')['triples']
    assert triples[0]['tail']=='湿垃圾'
    assert baseline('火星岩石属于湿垃圾。')['triples']==[]


def test_gradients_flow_through_crf_transition_and_encoders():
    n=BiLSTMCRF(12);r=BiGRUAttention(12)
    x=np.array([[1,2,3]],np.int32);tags=np.array([[1,2,0]],np.int32);p=np.array([[66,66,67]],np.int32)
    with tf.GradientTape() as tape:loss=n.nll(n(x),tags,[3])
    grads=tape.gradient(loss,n.trainable_variables)
    assert all(g is not None for g in grads)
    assert all(bool(tf.reduce_all(tf.math.is_finite(tf.convert_to_tensor(g)))) for g in grads)
    with tf.GradientTape() as tape:loss=tf.reduce_sum(tf.nn.sparse_softmax_cross_entropy_with_logits(labels=[1],logits=r((x,p,p))))
    assert all(g is not None for g in tape.gradient(loss,r.trainable_variables))
