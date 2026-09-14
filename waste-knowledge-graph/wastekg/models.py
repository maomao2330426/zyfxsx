"""TensorFlow 2/Keras 3: BiLSTM-CRF 与带实体位置特征的 BiGRU-Attention。"""
import os
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
import numpy as np
import tensorflow as tf
from .common import TAGS, MAX_LEN, bio_tags


def constraints():
    trans = np.zeros((len(TAGS), len(TAGS)), np.float32)
    start = np.zeros(len(TAGS), np.float32)
    for j, tag in enumerate(TAGS):
        if tag.startswith('I-'):
            start[j] = -10000.
            for i, prev in enumerate(TAGS):
                if prev not in ('B-' + tag[2:], 'I-' + tag[2:]):
                    trans[i,j] = -10000.
    return tf.constant(trans), tf.constant(start)


class BiLSTMCRF(tf.keras.Model):
    def __init__(self, vocab_size, embedding=48, hidden=48):
        super().__init__()
        self.embed = tf.keras.layers.Embedding(vocab_size, embedding, mask_zero=True)
        self.encoder = tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(hidden, return_sequences=True))
        self.dropout = tf.keras.layers.Dropout(.15)
        self.proj = tf.keras.layers.Dense(len(TAGS))
        self.transitions = self.add_weight(name='transitions', shape=(len(TAGS),len(TAGS)), initializer='zeros')
        self.start_scores = self.add_weight(name='start_scores', shape=(len(TAGS),), initializer='zeros')
        self.end_scores = self.add_weight(name='end_scores', shape=(len(TAGS),), initializer='zeros')
        self.transition_mask, self.start_mask = constraints()

    def call(self, tokens, training=False):
        x = self.embed(tokens)
        x = self.encoder(x, mask=tokens != 0, training=training)
        return self.proj(self.dropout(x, training=training))

    def nll(self, emissions, tags, lengths):
        """Log-sum-exp 前向算法减去金标准路径分数；padding 不计入损失。"""
        tags = tf.convert_to_tensor(tags, dtype=tf.int32)
        lengths = tf.convert_to_tensor(lengths, dtype=tf.int32)
        transitions = self.transitions + self.transition_mask
        start = self.start_scores + self.start_mask
        mask = tf.sequence_mask(lengths, tf.shape(tags)[1], dtype=emissions.dtype)
        unary = tf.reduce_sum(emissions * tf.one_hot(tags, len(TAGS)), axis=-1)
        score = tf.reduce_sum(unary * mask, axis=1) + tf.gather(start, tags[:,0])
        pairs = tf.stack([tags[:,:-1], tags[:,1:]], axis=-1)
        score += tf.reduce_sum(tf.gather_nd(transitions, pairs) * mask[:,1:], axis=1)
        last_tags = tf.gather(tags, lengths-1, batch_dims=1)
        score += tf.gather(self.end_scores, last_tags)
        alpha = emissions[:,0,:] + start
        def step(t, alpha):
            next_alpha = tf.reduce_logsumexp(alpha[:,:,None] + transitions[None,:,:], axis=1) + emissions[:,t,:]
            return t+1, tf.where((t < lengths)[:,None], next_alpha, alpha)
        _, alpha = tf.while_loop(lambda t,a: t < tf.shape(emissions)[1], step, (tf.constant(1), alpha))
        log_partition = tf.reduce_logsumexp(alpha + self.end_scores, axis=1)
        return tf.reduce_mean(log_partition - score)

    def decode(self, emissions, lengths):
        trans = (self.transitions+self.transition_mask).numpy()
        start = (self.start_scores+self.start_mask).numpy()
        end = self.end_scores.numpy()
        paths = []
        for row, length in zip(np.asarray(emissions), lengths):
            score = row[0]+start
            backs = []
            for t in range(1, int(length)):
                candidates = score[:,None]+trans
                backs.append(candidates.argmax(axis=0))
                score = candidates.max(axis=0)+row[t]
            tag = int((score+end).argmax())
            path = [tag]
            for back in reversed(backs):
                tag = int(back[tag])
                path.append(tag)
            paths.append(list(reversed(path)))
        return paths


class BiGRUAttention(tf.keras.Model):
    def __init__(self, vocab_size, embedding=48, hidden=48):
        super().__init__()
        self.embed = tf.keras.layers.Embedding(vocab_size, embedding)
        self.head_pos = tf.keras.layers.Embedding(132, 12)
        self.tail_pos = tf.keras.layers.Embedding(132, 12)
        self.encoder = tf.keras.layers.Bidirectional(tf.keras.layers.GRU(hidden, return_sequences=True))
        self.attention_hidden = tf.keras.layers.Dense(hidden, activation='tanh')
        self.attention_score = tf.keras.layers.Dense(1, use_bias=False)
        self.dropout = tf.keras.layers.Dropout(.15)
        self.classifier = tf.keras.layers.Dense(3)

    def call(self, inputs, training=False, return_attention=False):
        tokens, head_pos, tail_pos = inputs
        mask = tokens != 0
        x = tf.concat([self.embed(tokens), self.head_pos(head_pos), self.tail_pos(tail_pos)], axis=-1)
        states = self.encoder(x, mask=mask, training=training)
        scores = tf.squeeze(self.attention_score(self.attention_hidden(states)), axis=-1)
        scores = tf.where(mask, scores, tf.constant(-1e9, scores.dtype))
        weights = tf.nn.softmax(scores, axis=1)
        context = tf.reduce_sum(states * weights[:,:,None], axis=1)
        logits = self.classifier(self.dropout(context, training=training))
        return (logits, weights) if return_attention else logits


def encode(samples, vocab):
    # 每批动态 padding 到该批最长句，减少无效循环计算。
    length = max(len(s['text']) for s in samples)
    if length > MAX_LEN:
        raise ValueError('句子超过最大长度，禁止静默截断实体')
    x = np.zeros((len(samples),length), np.int32)
    y = np.zeros_like(x)
    hp, tp = np.zeros_like(x), np.zeros_like(x)
    lengths = []
    for i,s in enumerate(samples):
        n = len(s['text'])
        lengths.append(n)
        x[i,:n] = [vocab.get(c,1) for c in s['text']]
        if s.get('entities'):
            if 'relation' in s:
                y[i,:n] = [TAGS.index(t) for t in bio_tags(s)]
            head = s['entities'][s.get('head',0)]
            tail = s['entities'][s.get('tail',1)]
            # 实体内位置为 0，外部是距实体边界的有符号距离。
            def positions(ent):
                return [int(np.clip(j-ent['start'] if j<ent['start'] else (j-ent['end']+1 if j>=ent['end'] else 0), -64,64))+66 for j in range(n)]
            hp[i,:n], tp[i,:n] = positions(head), positions(tail)
    return x,y,np.array(lengths,np.int32),hp,tp
