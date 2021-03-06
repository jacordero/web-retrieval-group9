#!/usr/bin/python3.5

import sys
import string
import requests
import socket
import json
import os
import pickle
import math

from typing import Union
from lxml import etree
from peewee import fn
from nltk.corpus import stopwords
from nltk.stem.wordnet import WordNetLemmatizer
from nltk.tokenize import RegexpTokenizer
# from nltk.stem.porter import PorterStemmer
# from nltk.stem.snowball import SnowballStemmer
from gensim import corpora
from gensim.models.ldamodel import LdaModel
from gensim.models.ldamulticore import LdaMulticore

sys.path.insert(0, '../')
from models import connect_to_db, Papers, Labels, Papers_labels

stop_words = set(stopwords.words('english'))
exclude = set(string.punctuation)
lemma = WordNetLemmatizer()
tokenizer = RegexpTokenizer(r'\w+')
# p_stemmer = PorterStemmer()
# s_stemmer = SnowballStemmer('english')


def clean(doc: str) -> list:
    """
    Cleans the document by normalizing the words to a certain format.
    The text is lowered, stop words are removed and the remainder is stemmed.
    Args:
        doc: corpus of a document in string format

    Returns: list with words from the document that are filtered and stemmed

    """
    raw = doc.lower()
    tokens = tokenizer.tokenize(raw)
    stopped_tokens = [i for i in tokens if i not in stop_words and not i.isdigit() and len(i) > 2]
    return [lemma.lemmatize(s) for s in stopped_tokens]
    # return [s_stemmer.stem(i) for i in stopped_tokens]


def train_classifier(papers: list, num_topics: int) -> LdaModel:
    """
    Trains the Lda model with selected documents.
    Training is done by cleaning the documents, index the words
    and train the model with a given number of topics
    Args:
        papers: list of papers, each item containing the corpus of a document
        num_topics: amount of topics that need to be trained

    Returns: Trained lda model

    """
    papers_clean = [clean(paper) for paper in papers]
    dictionary = corpora.Dictionary(papers_clean)
    doc_term_matrix = [dictionary.doc2bow(paper) for paper in papers_clean]
    models = []
    print("Start generating models")
    for x in range(13, 14):
        ldamodel = LdaMulticore(doc_term_matrix, num_topics=x, id2word=dictionary, passes=50)
        topic_words = [w[0] for x in range(ldamodel.num_topics) for w in ldamodel.show_topic(x)]
        unique_words = set(topic_words)
        models.append(ldamodel)
        print(x, len(unique_words), len(unique_words)/float(len(topic_words)))
    x = 1
    while True:
        try:
            x = int(input("Enter the model you want to train labels for:\n"))
        except ValueError:
            print("not an integer")
            continue
        if x > len(models) or x < 1:
            print("Model does not exist")
        else:
            break
    return models[x-1], dictionary


def geturl(url: str, headers: dict=None, tries: int=3, timeout: int=15) -> requests.Response:
    """
    Retrieves an url with the http or https protocol.
    On default it will try to retrieve the url within 3 times with each a max timeout for 15 seconds.
    Args:
        url: url of the content that needs to be retrieved
        headers: headers that will be sent with the request
        tries: amount of time the function will try to fetch the url
        timeout: timeout of each request attempt

    Returns:
        Response object, containing the content of the page amongst others

    """
    if headers is None:
        headers = {}
    if 'User-Agent' not in headers:
        headers['User-Agent'] = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 ' \
                                '(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
    while tries > 0:
        tries -= 1
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            break
        except requests.exceptions.Timeout:
            continue
        except requests.exceptions.TooManyRedirects:
            raise ValueError("Too many redirects")
        except requests.exceptions.RequestException as e:
            raise ValueError(str(e))
        except socket.timeout:
            continue
        except ConnectionResetError:
            continue
    else:
        raise ValueError("Socket timeout")
    return r


def get_wikipedia_titles(search_terms: list) -> list:
    """
    Searches a list of words on wikipedia and returns the titles of the found wikipedia articles.
    Args:
        search_terms: a list of terms.

    Returns:
        The titles of the 8 most relevant search results

    """
    print(search_terms)
    while True:
        used_index = input("enter id of the terms to work with separated by ,")
        used_index = [int(x)-1 for x in used_index.split(',')]
        used_terms = [search_terms[i] for i in used_index]
        search_qsp = "+".join(used_terms)
        search_url = "https://en.wikipedia.org/w/api.php?action=query&format=json&list=search&srsearch={search}"\
            .format(search=search_qsp)
        print(search_url)
        try:
            r = geturl(search_url)
            json_data = r.json()
        except json.decoder.JSONDecodeError as e:
            print(e)
            continue
        except ValueError as e:
            print(e)
            continue
        print([t['title'] for t in json_data['query']['search'][:8]])
        answer = input("Happy?")
        if answer in ['Y', 'y']:
            break
    return [t['title'] for t in json_data['query']['search'][:8]]  # Max 8 titles, could be less


def chunk(items: list) -> list:
    """
    From a set of items return all the possible bi-grams and uni-grams
    Args:
        items: list of terms

    Returns:
        All possible bi-grams and uni-grams

    """
    result = []
    for item in items:
        splits = item.split(" ")
        bigrams = ["{w1} {w2}".format(w1=splits[x], w2=splits[x+1]) for x in range(len(splits) - 1)]
        result.append(item)
        result.extend(splits)
        result.extend(bigrams)
    return set(result)


def retrieve_article(url: str) -> Union[str, None]:
    """
    Fetches the content of a wikipedia article
    Args:
        url: url of the wikipedia article

    Returns:
        Full content of the wikipedia article

    """
    try:
        r = requests.get(url)
    except ValueError:
        return None
    tree = etree.fromstring(r.content, parser=etree.HTMLParser(remove_comments=True))
    content = tree.xpath('//div[@id="mw-content-text"]')
    if len(content) > 0:
        content = content.pop()
    else:
        return None
    removals = ['ol[@class="references"]', 'table', 'ul', 'h2', 'sup']
    for removal in removals:
        matches = content.xpath('.//{r}'.format(r=removal))
        for match in matches:
            match.getparent().remove(match)
    text = [w.strip() for w in list(content.itertext()) if w.strip() not in ['\n', '']]
    return " ".join(text)


def retrieve_content(titles: list) -> dict:
    """
    Given a title, check if there is a wikipedia page about it.
    If so return its content and length
    Args:
        titles: list of titles

    Returns:
        list with tuples (content, length)
    """
    result = dict()
    for title in titles:
        url = "https://en.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch={search}&format=json&gsrprop" \
              "=snippet&prop=info&inprop=url".format(search=title)
        try:
            json_data = requests.get(url).json()
        except json.decoder.JSONDecodeError:
            continue
        except ValueError:
            continue
        for _, value in json_data['query']['pages'].items():
            if value['title'].lower() == title.lower():
                article_url = value['fullurl']
                break
        else:
            continue
        article_content = retrieve_article(article_url)
        if article_content is not None:
            result[title] = article_content
    return result


def extract_topics(model: LdaModel) -> list:
    """
    From the words in a topic deduce a topic name that covers the content of the words in that topic.
    This is done by selecting candidates from the wikipedia API and compare these terms according to the
    following paper: http://www.aclweb.org/anthology/P11-1154
    Args:f
        model: The trained Lda model

    Returns: List of topic labels ordered by topic cluster

    """
    topic_list = []
    for x in range(model.num_topics):
        words = model.show_topic(x, topn=10)
        titles = get_wikipedia_titles([w[0] for w in words])  # TODO alter?
        possible_labels = chunk(titles)
        print(possible_labels)
        labels_content = retrieve_content(possible_labels)
        best_topic = rate_labels(possible_labels, labels_content, words)
        print(best_topic, words)
        print('-' * 80)
        topic_list.append(best_topic)
    return topic_list


def rate_labels(names: list, content: dict, topic_words: list) -> str:
    """
    Rate each of the labels bases on the words they contain and the words in the topics
    Args:
        names: list of possible label names
        content: content of each possible label name
        topic_words: the topic words for a specific topic

    Returns: best matching label

    """
    best_label, best_score = "", 0
    possible_labels = []
    for name in names:
        score = 0
        if name in content:
            corpus = content[name].split(' ')
            # print(name, corpus)
            for word in corpus:
                for topic_word in topic_words:
                    if topic_word[0] in word:  # Because they are stemmed!
                        score += topic_word[1]
            norm_score = score / math.sqrt(len(corpus))
            possible_labels.append(name)
            print(norm_score, "\t", name)
    while True:
        try:
            index = int(input("Enter the label to select"))
            best_label = possible_labels[index-1]
        except (IndexError, ValueError):
            continue
        break

    return best_label


def label_documents(model: LdaModel, topic_labels: list, dictionary: corpora.Dictionary):
    """
    Labels the documents in the database including the documents not present in the training set
    Args:
        model: the trained ldaModel
        topic_labels: list with labels of the topics
        dictionary: dictionary that is used when scanning the training data

    """
    papers = Papers.select()
    for paper in papers:
        text, title, paper_id = paper.paper_text, paper.title, paper.id
        cleaned_text = clean(text)
        text_dict = dictionary.doc2bow(cleaned_text)
        topic_scores = model[text_dict]
        labels = []
        for topic_score in topic_scores:
            if topic_score[1] > 1/len(topic_scores):
                Papers_labels.get_or_create(paper_id=paper_id, label_id=topic_score[0])
                labels.append(topic_labels[topic_score[0]])
        print(title, labels)


def create_database_labels(labels: list):
    """
    Creates a table in the database with labels
    Args:
        labels: list of labels from the topic modeling

    """
    for label in labels:
        Labels.get_or_create(name=label)


def main():
    if not os.path.isfile('ldamodel.pkl'):
        papers = [p.paper_text for p in Papers.select().order_by(fn.Random()).limit(200)]
        ldamodel, dictionary = train_classifier(papers, 20)
        pickle.dump(ldamodel, open('ldamodel.pkl', 'wb'))
        pickle.dump(dictionary, open('dictionary.pkl', 'wb'))
    else:
        ldamodel = pickle.load(open('ldamodel.pkl', 'rb'))
        dictionary = pickle.load(open('dictionary.pkl', 'rb'))
    if not os.path.isfile('labels.txt'):
        topic_labels = extract_topics(ldamodel)
        with open('labels.txt', 'w') as f:
            f.write("\n".join(topic_labels))
    else:
        with open('labels.txt', 'r') as f:
            topic_labels = f.read().splitlines()
    create_database_labels(topic_labels)
    print(topic_labels)
    label_documents(ldamodel, topic_labels, dictionary)


if __name__ == '__main__':
    connect_to_db('../nips-papers.db')
    main()
