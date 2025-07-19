#!/bin/bash
python -m nltk.downloader punkt stopwords averaged_perceptron_tagger wordnet maxent_ne_chunker words
python -m spacy download en_core_web_sm

