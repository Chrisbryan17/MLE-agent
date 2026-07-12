#!/usr/bin/env python3
from __future__ import annotations

from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import SGDClassifier

import document_closeout as base


def fit_sgd_text(train_texts, train_labels, test_texts, seed=20260712):
    vectorizer = HashingVectorizer(
        n_features=2**19,
        alternate_sign=False,
        norm='l2',
        lowercase=True,
        analyzer='word',
        ngram_range=(1, 2),
        token_pattern=r'(?u)\b\w+\b',
    )
    x_train = vectorizer.transform(train_texts)
    x_test = vectorizer.transform(test_texts)
    classifier = SGDClassifier(
        loss='log_loss', alpha=3e-6, max_iter=35, tol=1e-4,
        random_state=seed, class_weight='balanced',
    )
    classifier.fit(x_train, train_labels)
    return classifier.predict(x_test).tolist()


base.fit_sgd_text = fit_sgd_text

if __name__ == '__main__':
    base.main()
